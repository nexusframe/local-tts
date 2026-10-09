"""Measure the running daemon with text that comes in pieces, like LLM tokens (M4).

Start the daemon first: python -m local_tts
Then run: python scripts/measure_m4.py --out bench/results/m4/measure.json

The script plays audio for about 5 minutes.

Method:
- A sender thread sends the raw text of a corpus item in "append" commands at
  a fixed rate (tokens per second). One token is up to 3 characters of a word,
  with the space before the word in the first token. This is an assumption for
  Polish text with LLM tokenizers, not a measured tokenizer.
- TTFA is the time from the first "append" to the "started" event. "started"
  is the first audio write to pw-cat (see measure_m1.py, limit 1). M1
  measured approximately 50 ms more for pw-cat to start the sound.
- "first_sentence_s" is calculated from the send schedule: the time when the
  first character of the second sentence (or "end") is sent. Before this time
  the daemon cannot know that the first sentence is complete, so it is the
  lowest TTFA without the early first segment.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from local_tts.config import REPO_DIR, default_socket_path  # noqa: E402
from local_tts.splitter import split_sentences  # noqa: E402
from measure_m1 import Client, rss_mb, summary  # noqa: E402

CORPUS = REPO_DIR / "bench" / "corpus.json"
TTFA_TEXTS = ["S1", "M1", "M3", "M5", "L1"]
RATES = [20, 40, 80]


def corpus_raw(item_id: str) -> str:
    """The raw text, as an LLM writes it. The daemon normalizes it."""
    items = {item["id"]: item for item in json.loads(CORPUS.read_text(encoding="utf-8"))["items"]}
    return items[item_id]["raw"]


def tokens(text: str) -> list[str]:
    """Split the text into pieces of up to 3 characters. A piece never contains two words."""
    pieces = []
    for word in re.findall(r"\s*\S+", text):
        pieces.extend(word[i : i + 3] for i in range(0, len(word), 3))
    return pieces


def first_sentence_s(pieces: list[str], rate: float) -> float:
    """Time when the daemon can know that the first sentence is complete (see the module doc)."""
    text = "".join(pieces)
    sentences = split_sentences(text)
    if len(sentences) < 2:
        return len(pieces) / rate
    second_start = text.index(sentences[1], len(sentences[0]))
    sent_chars = 0
    for index, piece in enumerate(pieces):
        sent_chars += len(piece)
        if sent_chars > second_start:
            return index / rate
    raise AssertionError("second sentence not found")


class StreamClient(Client):
    def __init__(self, path: Path) -> None:
        super().__init__(path)
        self._send_lock = threading.Lock()

    def send(self, message: dict) -> float:
        with self._send_lock:
            return super().send(message)

    def stream(self, stream_id: str, pieces: list[str], rate: float, interrupt: bool = False) -> tuple[float, threading.Event, threading.Thread]:
        """Open a stream and start a thread that sends the pieces. Return the time of the first append."""
        begin: dict = {"cmd": "begin", "id": stream_id}
        if interrupt:
            begin["interrupt"] = True
        self.send(begin)
        self.wait_for("accepted", stream_id)
        stop = threading.Event()
        first = self.send({"cmd": "append", "id": stream_id, "text": pieces[0]})

        def sender() -> None:
            for index, piece in enumerate(pieces[1:], start=1):
                delay = first + index / rate - time.perf_counter()
                if stop.wait(max(delay, 0)):
                    return
                self.send({"cmd": "append", "id": stream_id, "text": piece})
            self.send({"cmd": "end", "id": stream_id})

        thread = threading.Thread(target=sender, daemon=True)
        thread.start()
        return first, stop, thread

    def cancel_and_wait(self, stream_id: str, stop: threading.Event, thread: threading.Thread) -> None:
        stop.set()
        thread.join()
        self.send({"cmd": "cancel"})
        while True:
            _, message = self.next_event()
            if message.get("id") == stream_id and message["event"] in ("cancelled", "done"):
                return


_ids = iter(range(1, 1_000_000))


def new_id(prefix: str) -> str:
    return f"{prefix}{next(_ids)}"


def measure_ttfa(client: StreamClient, item: str, rate: float, runs: int) -> dict:
    """TTFA of a stream. Cancel after the first audio, so that long texts do not play to the end."""
    pieces = tokens(corpus_raw(item))
    ttfa = []
    for _ in range(runs):
        stream_id = new_id("t")
        first, stop, thread = client.stream(stream_id, pieces, rate)
        started, _ = client.wait_for("started", stream_id)
        ttfa.append(started - first)
        client.cancel_and_wait(stream_id, stop, thread)
    return {
        "text": item,
        "rate_tok_s": rate,
        "tokens": len(pieces),
        "first_sentence_s": round(first_sentence_s(pieces, rate), 4),
        "ttfa_s": summary(ttfa),
    }


def measure_gaps(client: StreamClient, item: str, rate: float, runs: int) -> dict:
    """Play the full stream. (done - started) - audio contains the gaps plus the pw-cat start and drain."""
    pieces = tokens(corpus_raw(item))
    extra, audio = [], []
    for _ in range(runs):
        stream_id = new_id("g")
        _, _, thread = client.stream(stream_id, pieces, rate)
        started, _ = client.wait_for("started", stream_id)
        done, message = client.wait_for("done", stream_id)
        thread.join()
        audio.append(message["audio_seconds"])
        extra.append((done - started) - message["audio_seconds"])
    return {"text": item, "rate_tok_s": rate, "audio_s": summary(audio), "playback_minus_audio_s": summary(extra)}


def measure_speak_gaps(client: StreamClient, item: str, runs: int) -> dict:
    """Reference for measure_gaps: the same text in one speak command."""
    extra, audio = [], []
    for _ in range(runs):
        _, request_id = client.speak(corpus_raw(item))
        started, _ = client.wait_for("started", request_id)
        done, message = client.wait_for("done", request_id)
        audio.append(message["audio_seconds"])
        extra.append((done - started) - message["audio_seconds"])
    return {"text": item, "speak": True, "audio_s": summary(audio), "playback_minus_audio_s": summary(extra)}


def measure_interrupt(client: StreamClient, delays: list[float]) -> dict:
    """Barge-in as in M1: speak L1, wait, then speak S1 with interrupt=true. Several delays hit other sentences of L1."""
    to_started = []
    for after in delays:
        _, old = client.speak(corpus_raw("L1"))
        client.wait_for("started", old)
        time.sleep(after)
        sent = client.send({"cmd": "speak", "text": corpus_raw("S1"), "interrupt": True})
        _, accepted = client.wait_for("accepted")
        started, _ = client.wait_for("started", accepted["id"])
        client.wait_for("done", accepted["id"])
        to_started.append(started - sent)
    return {"delays_s": delays, "interrupt_to_new_started_s": summary(to_started), "values_s": [round(v, 4) for v in to_started]}


def measure_stream_interrupt(client: StreamClient, delays: list[float], rate: float) -> dict:
    """Barge-in with streams: L1 is streaming, then a new stream with interrupt=true starts. TTFA of the new stream."""
    old_pieces, new_pieces = tokens(corpus_raw("L1")), tokens(corpus_raw("S2"))
    ttfa = []
    for after in delays:
        old_id = new_id("o")
        _, old_stop, old_thread = client.stream(old_id, old_pieces, rate)
        client.wait_for("started", old_id)
        time.sleep(after)
        old_stop.set()
        old_thread.join()
        stream_id = new_id("n")
        first, stop, thread = client.stream(stream_id, new_pieces, rate, interrupt=True)
        started, _ = client.wait_for("started", stream_id)
        ttfa.append(started - first)
        client.wait_for("done", stream_id)
        thread.join()
    return {"rate_tok_s": rate, "delays_s": delays, "ttfa_s": summary(ttfa)}


def measure_cancel(client: StreamClient, delays: list[float]) -> dict:
    """Time from the cancel command to the cancelled event, during a long text."""
    to_event = []
    for after in delays:
        _, request_id = client.speak(corpus_raw("L1"))
        client.wait_for("started", request_id)
        time.sleep(after)
        sent = client.send({"cmd": "cancel"})
        cancelled, _ = client.wait_for("cancelled", request_id)
        to_event.append(cancelled - sent)
    return {"delays_s": delays, "cancel_to_event_s": summary(to_event)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Measure the running local TTS daemon with streamed text.")
    parser.add_argument("--socket", type=Path, default=default_socket_path(), help="Path of the Unix socket. Default: %(default)s")
    parser.add_argument("--out", type=Path, help="Write the results as JSON to this file.")
    parser.add_argument("--quick", action="store_true", help="Use fewer runs.")
    parser.add_argument("--only", choices=["ttfa"], help="Measure only this part.")
    parser.add_argument("--label", help="A note for the results, for example the daemon options.")
    args = parser.parse_args()

    client = StreamClient(args.socket)
    client.send({"cmd": "status"})
    _, status = client.wait_for("status")
    runs = 2 if args.quick else 5
    delays = [0.1, 0.3, 0.5, 0.8, 1.2] * (1 if args.quick else 2)
    results: dict = {
        "date": time.strftime("%Y-%m-%d %H:%M:%S"),
        "label": args.label,
        "daemon_pid": client.daemon_pid,
        "status": status,
        "rss_before": rss_mb(client.daemon_pid),
    }
    results["ttfa"] = [measure_ttfa(client, item, rate, runs) for rate in RATES for item in TTFA_TEXTS]
    if args.only == "ttfa":
        return finish(results, client, args.out)
    results["gaps"] = [measure_gaps(client, item, rate, 1 if args.quick else 3) for item in ["S1", "M1"] for rate in (20, 80)]
    results["gaps"].append(measure_gaps(client, "L1", 20, 1))
    results["gaps"] += [measure_speak_gaps(client, item, 1 if args.quick else 3) for item in ["S1", "M1"]]
    results["interrupt"] = measure_interrupt(client, delays)
    results["stream_interrupt"] = measure_stream_interrupt(client, delays, 40)
    results["cancel"] = measure_cancel(client, delays)
    return finish(results, client, args.out)


def finish(results: dict, client: StreamClient, out: Path | None) -> int:
    results["rss_after"] = rss_mb(client.daemon_pid)
    text = json.dumps(results, ensure_ascii=False, indent=2)
    print(text)
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
