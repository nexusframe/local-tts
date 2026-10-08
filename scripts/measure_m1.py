"""Measure the running daemon through its socket (M1 acceptance check).

Start the daemon first: python -m local_tts
Then run: python scripts/measure_m1.py --out bench/results/m1/measure.json

The script plays audio for about 5 minutes.

Limits of the method:
- "started" is the time when the daemon wrote the first audio to pw-cat. The
  time until the sound comes out of the speaker (pw-cat start, PipeWire
  latency) is not included.
- A gap in playback is not detected directly. The script uses
  (done - started) - audio_seconds. This value contains the gaps, plus the
  time for pw-cat to start and to drain.
"""

from __future__ import annotations

import argparse
import json
import socket
import statistics
import struct
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from local_tts.config import REPO_DIR, default_socket_path  # noqa: E402

CORPUS = REPO_DIR / "bench" / "corpus.json"


def corpus_text(item_id: str) -> str:
    items = {item["id"]: item for item in json.loads(CORPUS.read_text(encoding="utf-8"))["items"]}
    item = items[item_id]
    return item.get("normalized") or item["raw"]


class Client:
    def __init__(self, path: Path) -> None:
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.connect(str(path))
        self.lines = self.sock.makefile("r", encoding="utf-8")
        creds = self.sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
        self.daemon_pid = struct.unpack("3i", creds)[0]

    def send(self, message: dict) -> float:
        sent = time.perf_counter()
        self.sock.sendall((json.dumps(message, ensure_ascii=False) + "\n").encode("utf-8"))
        return sent

    def next_event(self) -> tuple[float, dict]:
        line = self.lines.readline()
        if not line:
            raise ConnectionError("daemon closed the connection")
        return time.perf_counter(), json.loads(line)

    def wait_for(self, event: str, request_id: str | None = None) -> tuple[float, dict]:
        while True:
            at, message = self.next_event()
            if message["event"] == "error":
                raise RuntimeError(f"daemon error: {message}")
            if message["event"] == event and (request_id is None or message.get("id") == request_id):
                return at, message

    def speak(self, text: str, voice: str | None = None) -> tuple[float, str]:
        message = {"cmd": "speak", "text": text}
        if voice:
            message["voice"] = voice
        sent = self.send(message)
        _, accepted = self.wait_for("accepted")
        return sent, accepted["id"]


def rss_mb(pid: int) -> dict[str, float]:
    fields = {}
    for line in Path(f"/proc/{pid}/status").read_text().splitlines():
        key, _, value = line.partition(":")
        if key in ("VmRSS", "VmHWM"):
            fields[key] = int(value.split()[0]) / 1024
    return {"rss_mb": round(fields["VmRSS"], 1), "peak_rss_mb": round(fields["VmHWM"], 1)}


def summary(values: list[float]) -> dict[str, float]:
    return {
        "n": len(values),
        "median": round(statistics.median(values), 4),
        "min": round(min(values), 4),
        "max": round(max(values), 4),
    }


def measure_short(client: Client, runs: int) -> dict:
    """Time from speak to the first audio write, for S1."""
    text = corpus_text("S1")
    ttfa = []
    for _ in range(runs):
        sent, request_id = client.speak(text)
        started, _ = client.wait_for("started", request_id)
        client.wait_for("done", request_id)
        ttfa.append(started - sent)
    return {"text": "S1", "ttfa_s": summary(ttfa)}


def measure_long(client: Client, runs: int) -> dict:
    """Time to first audio and the time above the audio length, for L1."""
    text = corpus_text("L1")
    ttfa, extra, audio = [], [], []
    for _ in range(runs):
        sent, request_id = client.speak(text)
        started, _ = client.wait_for("started", request_id)
        done, message = client.wait_for("done", request_id)
        ttfa.append(started - sent)
        audio.append(message["audio_seconds"])
        extra.append((done - started) - message["audio_seconds"])
    return {"text": "L1", "ttfa_s": summary(ttfa), "audio_s": summary(audio), "playback_minus_audio_s": summary(extra)}


def measure_cancel(client: Client, runs: int, after: float) -> dict:
    """Time from the cancel command to the reply and to the cancelled event."""
    text = corpus_text("L1")
    to_ack, to_event = [], []
    for _ in range(runs):
        _, request_id = client.speak(text)
        client.wait_for("started", request_id)
        time.sleep(after)
        sent = client.send({"cmd": "cancel"})
        acked, _ = client.wait_for("ack")
        cancelled, _ = client.wait_for("cancelled", request_id)
        to_ack.append(acked - sent)
        to_event.append(cancelled - sent)
    return {"after_s": after, "cancel_to_ack_s": summary(to_ack), "cancel_to_event_s": summary(to_event)}


def measure_interrupt(client: Client, runs: int, after: float) -> dict:
    """Barge-in: time from a speak with interrupt=true to the first audio of the new text."""
    to_started = []
    for _ in range(runs):
        _, old = client.speak(corpus_text("L1"))
        client.wait_for("started", old)
        time.sleep(after)
        sent = client.send({"cmd": "speak", "text": corpus_text("S1"), "interrupt": True})
        _, accepted = client.wait_for("accepted")
        started, _ = client.wait_for("started", accepted["id"])
        client.wait_for("done", accepted["id"])
        to_started.append(started - sent)
    return {"after_s": after, "interrupt_to_new_started_s": summary(to_started)}


def measure_dialogue(client: Client, runs: int, voices: tuple[str, str]) -> dict:
    """Silence between two queued utterances with different voices."""
    gaps = []
    for _ in range(runs):
        _, first = client.speak(corpus_text("S1"), voices[0])
        _, second = client.speak(corpus_text("S2"), voices[1])
        first_done, _ = client.wait_for("done", first)
        second_started, _ = client.wait_for("started", second)
        client.wait_for("done", second)
        gaps.append(second_started - first_done)
    return {"voices": list(voices), "gap_done_to_next_started_s": summary(gaps)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Measure the running local TTS daemon.")
    parser.add_argument("--socket", type=Path, default=default_socket_path(), help="Path of the Unix socket. Default: %(default)s")
    parser.add_argument("--out", type=Path, help="Write the results as JSON to this file.")
    parser.add_argument("--quick", action="store_true", help="Use fewer runs and no long text.")
    args = parser.parse_args()

    client = Client(args.socket)
    sent = client.send({"cmd": "status"})
    _, status = client.wait_for("status")
    voices = status["voices"]
    results: dict = {
        "date": time.strftime("%Y-%m-%d %H:%M:%S"),
        "daemon_pid": client.daemon_pid,
        "status": status,
        "rss_before": rss_mb(client.daemon_pid),
    }
    results["short"] = measure_short(client, 3 if args.quick else 10)
    if not args.quick:
        results["long"] = measure_long(client, 3)
    results["cancel"] = measure_cancel(client, 2 if args.quick else 5, after=1.0 if args.quick else 2.0)
    results["interrupt"] = measure_interrupt(client, 2 if args.quick else 5, after=0.3)
    if len(voices) >= 2:
        results["dialogue"] = measure_dialogue(client, 2 if args.quick else 5, (status["default_voice"], next(v for v in voices if v != status["default_voice"])))
    results["rss_after"] = rss_mb(client.daemon_pid)

    text = json.dumps(results, ensure_ascii=False, indent=2)
    print(text)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
