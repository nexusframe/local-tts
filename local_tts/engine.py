"""Speech engine: a queue of utterances, synthesis and playback.

Two threads:

- The synthesis thread takes utterances from the request queue, splits them
  into sentences and puts audio chunks into the audio queue. The text of an
  utterance comes in pieces: all at once for speak(), or in append() calls
  for a stream (begin, append, end). It does not wait
  for playback, so the next sentence and the next utterance are ready early.
- The playback thread writes the chunks to the player and sends the events.

Cancel uses an epoch counter. cancel() increments the epoch, so all work that
started in an older epoch is discarded at the next check. Each utterance gets
exactly one final event: done, cancelled or error.
"""

from __future__ import annotations

import collections
import itertools
import queue
import threading
from dataclasses import dataclass, field
from typing import Callable, Mapping

import numpy as np

from local_tts.backends.base import Backend
from local_tts.player import Player
from local_tts.pronunciation import PronunciationDictionary, apply_aliases
from local_tts.protocol import Begin, Speak
from local_tts.normalizer import normalize, normalize_english
from local_tts.splitter import SentenceStream, split_sentences
from local_tts.word_map import heard_prefix

EventSink = Callable[..., None]

# Audio goes to the player in parts of this length, so that the played time is
# known also during a long sentence, and a cancel stops the write sooner.
_WRITE_SECONDS = 0.1

_STOP = object()
# Last item in the piece queue of an utterance.
_END_OF_TEXT = object()
# Item in the piece queue: speak the text that waits for the end of its sentence.
_FLUSH = object()


@dataclass(frozen=True)
class _Utterance:
    id: str
    voice: str
    epoch: int
    early_first: bool
    # Text pieces, then _END_OF_TEXT.
    pieces: queue.Queue
    # Multiplier of the speech rate of the voice (the 'speed' field of the request).
    speed: float = 1.0
    # Set by abort(): this utterance only is cancelled.
    aborted: threading.Event = field(default_factory=threading.Event)


@dataclass(frozen=True)
class _Chunk:
    utterance: _Utterance
    pcm: np.ndarray
    sample_rate: int


@dataclass(frozen=True)
class _Words:
    """Word end times of one sentence of a segment. Comes before the last chunk of the sentence.

    ends: seconds from the start of the sentence, one for each word of the
    spoken text, or None when the backend gave no times. offset: seconds of
    the sentence that are before this item in the audio queue.
    """

    utterance: _Utterance
    text: str
    to_spoken: Callable[[str], str]
    ends: tuple[float, ...] | None
    offset: float


@dataclass
class _Partial:
    """The segment that plays now: its text and the end times of its spoken words."""

    text: str
    to_spoken: Callable[[str], str]
    ends: list[float] = field(default_factory=list)
    broken: bool = False


@dataclass(frozen=True)
class _SegmentEnd:
    """All audio of one segment is in the audio queue. The text is as the client sent it."""

    utterance: _Utterance
    text: str


@dataclass(frozen=True)
class _End:
    utterance: _Utterance
    error: str | None = None


class Engine:
    def __init__(
        self,
        backends: Mapping[str, Backend],
        player: Player,
        on_event: EventSink,
        default_voice: str,
        first_words: int = 2,
        pronunciation: PronunciationDictionary | None = None,
    ) -> None:
        self._backends = dict(backends)
        self._pronunciation = pronunciation
        # Word limit of the early first segment of a stream (see SentenceStream).
        self._first_words = first_words
        self._player = player
        self._on_event = on_event
        self._default_voice = default_voice
        self._requests: queue.Queue = queue.Queue()
        self._audio: queue.Queue = queue.Queue()
        self._ids = itertools.count(1)
        self._epoch = 0
        self._cancel_lock = threading.Lock()
        # Ids of utterances without a final event, in request order.
        self._pending: dict[str, None] = {}
        self._speaking: str | None = None
        # Audio seconds that the player had not played yet when stop() cut an utterance.
        self._unheard: dict[str, float] = {}
        # The utterance whose sentence the backend synthesizes now.
        self._synthesizing: _Utterance | None = None
        # Streams that have no end() yet.
        self._streams: dict[str, _Utterance] = {}
        # Streams that cancel() closed. The client can still send pieces for
        # them until it gets the cancelled event, so these are ignored.
        self._cancelled_streams: collections.deque[str] = collections.deque(maxlen=64)
        self._state_lock = threading.Lock()
        # Held while the playback thread writes audio. cancel() takes it to be
        # sure that no audio of the old epoch reaches the player after stop().
        self._write_lock = threading.Lock()
        self._threads = [
            threading.Thread(target=self._synthesis_loop, name="synthesis", daemon=True),
            threading.Thread(target=self._playback_loop, name="playback", daemon=True),
        ]

    def start(self) -> None:
        for thread in self._threads:
            thread.start()

    def close(self) -> None:
        self.cancel()
        self._requests.put(_STOP)
        for thread in self._threads:
            thread.join()

    def speak(self, request: Speak) -> str:
        utterance = self._enqueue(request, early_first=False)
        utterance.pieces.put(request.text)
        utterance.pieces.put(_END_OF_TEXT)
        return utterance.id

    def begin(self, request: Begin) -> str:
        """Open a stream. The first part of the first sentence is synthesized early."""
        utterance = self._enqueue(request, early_first=True, stream=True)
        return utterance.id

    def append(self, stream_id: str, text: str) -> None:
        if (utterance := self._open_stream(stream_id)) is not None:
            utterance.pieces.put(text)

    def flush(self, stream_id: str) -> None:
        if (utterance := self._open_stream(stream_id)) is not None:
            utterance.pieces.put(_FLUSH)

    def end(self, stream_id: str) -> None:
        with self._state_lock:
            utterance = self._streams.pop(stream_id, None)
        if utterance is not None:
            utterance.pieces.put(_END_OF_TEXT)
        else:
            self._open_stream(stream_id)  # Raises, if the stream was not cancelled.

    def abort(self, stream_id: str) -> None:
        """Cancel one open stream, for example when its client disconnects. Other utterances continue."""
        with self._state_lock:
            utterance = self._streams.pop(stream_id, None)
            if utterance is None:
                return
            self._cancelled_streams.append(stream_id)
            utterance.aborted.set()
        self._interrupt_synthesis(lambda current: current is utterance)
        utterance.pieces.put(_END_OF_TEXT)
        # Like cancel(): the first stop() unblocks a write() that holds the write lock.
        if self._note_unheard(lambda speaking: speaking == stream_id):
            self._player.stop()
        with self._write_lock:
            if self._speaking == stream_id:
                self._player.stop()

    def _interrupt_synthesis(self, matches: Callable[[_Utterance], bool]) -> None:
        """Stop the sentence that the backend synthesizes now, so that new text does not wait for it.

        If the interrupt comes just before the backend starts the run, the run is
        not stopped. Then the new text waits for one sentence, as in M1.
        """
        with self._state_lock:
            utterance = self._synthesizing
            if utterance is not None and matches(utterance):
                self._backends[utterance.voice].interrupt()

    def _note_unheard(self, matches: Callable[[str], bool]) -> bool:
        """Before stop(): keep the audio seconds that the listener did not hear. Return True if it matched."""
        with self._state_lock:
            speaking = self._speaking
            if speaking is None or not matches(speaking):
                return False
            self._unheard[speaking] = self._player.queued_seconds()
            return True

    def _open_stream(self, stream_id: str) -> _Utterance | None:
        """Return the open stream, or None for a cancelled stream. Raise for other ids."""
        with self._state_lock:
            utterance = self._streams.get(stream_id)
            if utterance is None and stream_id not in self._cancelled_streams:
                raise ValueError(f"no open stream {stream_id!r}")
        return utterance

    def _enqueue(self, request: Speak | Begin, early_first: bool, stream: bool = False) -> _Utterance:
        voice = request.voice or self._default_voice
        if voice not in self._backends:
            raise ValueError(f"unknown voice {voice!r}, available: {sorted(self._backends)}")
        request_id = request.id or f"u{next(self._ids)}"
        if request.interrupt:
            self.cancel()
        utterance = _Utterance(request_id, voice, self._epoch, early_first, queue.Queue(), speed=request.speed)
        with self._state_lock:
            self._pending[request_id] = None
            if stream:
                self._streams[request_id] = utterance
        self._requests.put(utterance)
        return utterance

    def cancel(self) -> None:
        with self._cancel_lock:
            self._epoch += 1
            self._interrupt_synthesis(lambda utterance: True)
            self._note_unheard(lambda speaking: True)
            self._player.stop()
            with self._write_lock:
                self._player.stop()
            with self._state_lock:
                streams, self._streams = self._streams, {}
                self._cancelled_streams.extend(streams)
            for utterance in streams.values():
                # Wake the synthesis thread if it waits for a piece. The epoch check discards it.
                utterance.pieces.put(_END_OF_TEXT)
            while True:
                try:
                    item = self._requests.get_nowait()
                except queue.Empty:
                    break
                if item is _STOP:
                    self._requests.put(_STOP)
                    break
                self._emit("cancelled", id=item.id, spoken="", spoken_partial="")

    def status(self) -> dict:
        with self._state_lock:
            return {
                "voices": sorted(self._backends),
                "languages": {name: backend.language for name, backend in sorted(self._backends.items())},
                "default_voice": self._default_voice,
                "speaking": self._speaking,
                "queued": [i for i in self._pending if i != self._speaking],
            }

    def _emit(self, event: str, id: str, **fields: object) -> None:
        with self._state_lock:
            if event == "started":
                self._speaking = id
            else:
                self._pending.pop(id, None)
                if self._speaking == id:
                    self._speaking = None
        self._on_event(event, id=id, **fields)

    def _current(self, utterance: _Utterance) -> bool:
        return utterance.epoch == self._epoch and not utterance.aborted.is_set()

    def _synthesis_loop(self) -> None:
        while (utterance := self._requests.get()) is not _STOP:
            self._audio.put(self._synthesize(utterance))
        self._audio.put(_STOP)

    def _synthesize(self, utterance: _Utterance) -> _End:
        """Put the audio chunks of one utterance into the audio queue. Return its end marker."""
        backend = self._backends[utterance.voice]
        normalize_text = normalize if backend.language == "pl" else normalize_english
        # Read for each utterance, so that a changed file is used from the next one.
        aliases = self._pronunciation.aliases(backend.language) if self._pronunciation else {}

        def to_spoken(text: str) -> str:
            return normalize_text(apply_aliases(text, aliases))

        stream = SentenceStream(early_first=utterance.early_first, first_words=self._first_words)
        try:
            while True:
                piece = utterance.pieces.get()
                if not self._current(utterance):
                    return _End(utterance)
                segments = stream.flush() if piece is _END_OF_TEXT or piece is _FLUSH else stream.feed(piece)
                for segment in segments:
                    if not any(char.isalnum() for char in segment):
                        continue  # Only punctuation, for example the "." that comes after a flush.
                    # The normalizer can make new sentence ends, so split again.
                    for sentence in split_sentences(to_spoken(segment)):
                        with self._state_lock:
                            if not self._current(utterance):
                                return _End(utterance)
                            self._synthesizing = utterance
                        word_ends: list[float] = []
                        offset = 0.0
                        try:
                            for pcm in backend.synthesize(sentence, word_ends=word_ends, speed=utterance.speed):
                                if not self._current(utterance):
                                    return _End(utterance)
                                if word_ends:  # The last chunk of the sentence.
                                    ends = tuple(word_ends) if len(word_ends) == len(sentence.split()) else None
                                    self._audio.put(_Words(utterance, segment, to_spoken, ends, offset))
                                self._audio.put(_Chunk(utterance, pcm, backend.sample_rate))
                                offset += len(pcm) / backend.sample_rate
                        finally:
                            with self._state_lock:
                                self._synthesizing = None
                        if not word_ends:
                            self._audio.put(_Words(utterance, segment, to_spoken, None, offset))
                    self._audio.put(_SegmentEnd(utterance, segment))
                if piece is _END_OF_TEXT:
                    break
        except Exception as exc:
            if not self._current(utterance):
                return _End(utterance)  # interrupt() stopped the backend.
            return _End(utterance, error=f"{type(exc).__name__}: {exc}")
        return _End(utterance)

    def _playback_loop(self) -> None:
        # Seconds of audio written for each started utterance.
        played: dict[str, float] = {}
        # For each utterance: the segments that were written, with the audio seconds
        # at their end and their word times.
        segments: dict[str, list[tuple[float, str, _Partial | None]]] = {}
        # For each utterance: the segment that plays now (no _SegmentEnd yet).
        partials: dict[str, _Partial] = {}
        while (item := self._audio.get()) is not _STOP:
            utterance = item.utterance
            if isinstance(item, _Words):
                if self._current(utterance):
                    partial = partials.setdefault(utterance.id, _Partial(item.text, item.to_spoken))
                    if item.ends is None:
                        partial.broken = True
                    else:
                        start = played.get(utterance.id, 0.0) - item.offset
                        partial.ends.extend(start + end for end in item.ends)
                continue
            if isinstance(item, _SegmentEnd):
                # After a cancel, the cut segment stays for the final event.
                if self._current(utterance):
                    words = partials.pop(utterance.id, None)
                    segments.setdefault(utterance.id, []).append((played.get(utterance.id, 0.0), item.text, words))
                continue
            if isinstance(item, _Chunk):
                with self._write_lock:
                    if not self._current(utterance):
                        continue
                    if utterance.id not in played:
                        played[utterance.id] = 0.0
                        self._emit("started", id=utterance.id)
                    step = max(1, round(item.sample_rate * _WRITE_SECONDS))
                    for start in range(0, len(item.pcm), step):
                        part = item.pcm[start : start + step]
                        self._player.write(part, item.sample_rate)
                        # After stop() the part was not played.
                        if not self._current(utterance):
                            break
                        played[utterance.id] += len(part) / item.sample_rate
                continue

            # End marker: wait until the audio of this utterance was played.
            if self._current(utterance):
                self._player.drain()
            audio_seconds = played.pop(utterance.id, 0.0)
            heard = audio_seconds - self._unheard.pop(utterance.id, 0.0)
            written = segments.pop(utterance.id, [])
            # A segment counts only when the listener heard all of it.
            heard_segments = [text for end, text, _ in written if end <= heard + 1e-9]
            spoken = " ".join(heard_segments)
            # The cut segment: the first written segment that was not heard completely,
            # else the segment that was not written completely.
            cut = written[len(heard_segments)][2] if len(heard_segments) < len(written) else partials.get(utterance.id)
            partials.pop(utterance.id, None)
            spoken_partial = self._spoken_partial(cut, heard)
            if not self._current(utterance):
                self._emit("cancelled", id=utterance.id, spoken=spoken, spoken_partial=spoken_partial)
            elif item.error is not None:
                self._emit("error", id=utterance.id, message=item.error, spoken=spoken, spoken_partial=spoken_partial)
            else:
                self._emit("done", id=utterance.id, audio_seconds=audio_seconds)

    @staticmethod
    def _spoken_partial(partial: _Partial | None, heard: float) -> str:
        """The words of the cut segment that the listener heard completely, in the text of the client."""
        if partial is None or partial.broken:
            return ""
        heard_words = sum(1 for end in partial.ends if end <= heard + 1e-9)
        return heard_prefix(partial.text, heard_words, partial.to_spoken)
