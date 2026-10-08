"""Speech engine: a queue of utterances, synthesis and playback.

Two threads:

- The synthesis thread takes utterances from the request queue, splits them
  into sentences and puts audio chunks into the audio queue. It does not wait
  for playback, so the next sentence and the next utterance are ready early.
- The playback thread writes the chunks to the player and sends the events.

Cancel uses an epoch counter. cancel() increments the epoch, so all work that
started in an older epoch is discarded at the next check. Each utterance gets
exactly one final event: done, cancelled or error.
"""

from __future__ import annotations

import itertools
import queue
import threading
from dataclasses import dataclass
from typing import Callable, Mapping

import numpy as np

from local_tts.backends.base import Backend
from local_tts.player import Player
from local_tts.protocol import Speak
from local_tts.normalizer import normalize
from local_tts.splitter import split_sentences

EventSink = Callable[..., None]

_STOP = object()


@dataclass(frozen=True)
class _Utterance:
    id: str
    text: str
    voice: str
    epoch: int


@dataclass(frozen=True)
class _Chunk:
    utterance: _Utterance
    pcm: np.ndarray
    sample_rate: int


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
    ) -> None:
        self._backends = dict(backends)
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
        voice = request.voice or self._default_voice
        if voice not in self._backends:
            raise ValueError(f"unknown voice {voice!r}, available: {sorted(self._backends)}")
        request_id = request.id or f"u{next(self._ids)}"
        if request.interrupt:
            self.cancel()
        with self._state_lock:
            self._pending[request_id] = None
        self._requests.put(_Utterance(request_id, request.text, voice, self._epoch))
        return request_id

    def cancel(self) -> None:
        with self._cancel_lock:
            self._epoch += 1
            self._player.stop()
            with self._write_lock:
                self._player.stop()
            while True:
                try:
                    item = self._requests.get_nowait()
                except queue.Empty:
                    break
                if item is _STOP:
                    self._requests.put(_STOP)
                    break
                self._emit("cancelled", id=item.id)

    def status(self) -> dict:
        with self._state_lock:
            return {
                "voices": sorted(self._backends),
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
        return utterance.epoch == self._epoch

    def _synthesis_loop(self) -> None:
        while (utterance := self._requests.get()) is not _STOP:
            self._audio.put(self._synthesize(utterance))
        self._audio.put(_STOP)

    def _synthesize(self, utterance: _Utterance) -> _End:
        """Put the audio chunks of one utterance into the audio queue. Return its end marker."""
        backend = self._backends[utterance.voice]
        try:
            for sentence in split_sentences(normalize(utterance.text)):
                for pcm in backend.synthesize(sentence):
                    if not self._current(utterance):
                        return _End(utterance)
                    self._audio.put(_Chunk(utterance, pcm, backend.sample_rate))
        except Exception as exc:
            return _End(utterance, error=f"{type(exc).__name__}: {exc}")
        return _End(utterance)

    def _playback_loop(self) -> None:
        # Seconds of audio written for each started utterance.
        played: dict[str, float] = {}
        while (item := self._audio.get()) is not _STOP:
            utterance = item.utterance
            if isinstance(item, _Chunk):
                with self._write_lock:
                    if not self._current(utterance):
                        continue
                    if utterance.id not in played:
                        played[utterance.id] = 0.0
                        self._emit("started", id=utterance.id)
                    self._player.write(item.pcm, item.sample_rate)
                    played[utterance.id] += len(item.pcm) / item.sample_rate
                continue

            # End marker: wait until the audio of this utterance was played.
            if self._current(utterance):
                self._player.drain()
            audio_seconds = played.pop(utterance.id, 0.0)
            if not self._current(utterance):
                self._emit("cancelled", id=utterance.id)
            elif item.error is not None:
                self._emit("error", id=utterance.id, message=item.error)
            else:
                self._emit("done", id=utterance.id, audio_seconds=audio_seconds)
