"""Small command line client for the daemon socket.

Examples:
    python -m local_tts.client speak "Dzień dobry."
    python -m local_tts.client speak --voice jarvis --interrupt "Stop."
    python -m local_tts.client cancel
    python -m local_tts.client status
"""

from __future__ import annotations

import argparse
import json
import socket
import sys
from pathlib import Path

from local_tts.config import default_socket_path

FINAL_EVENTS = {"done", "cancelled", "error"}


def connect(path: Path) -> socket.socket:
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.connect(str(path))
    return sock


def events(sock: socket.socket):
    """Yield the JSON messages from the daemon, one for each line."""
    for line in sock.makefile("r", encoding="utf-8"):
        yield json.loads(line)


def send(sock: socket.socket, message: dict) -> None:
    sock.sendall((json.dumps(message, ensure_ascii=False) + "\n").encode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m local_tts.client", description="Send one command to the local TTS daemon.")
    parser.add_argument("--socket", type=Path, default=default_socket_path(), help="Path of the Unix socket. Default: %(default)s")
    sub = parser.add_subparsers(dest="cmd", required=True)
    speak = sub.add_parser("speak", help="Speak the text and wait until the speech ends.")
    speak.add_argument("text")
    speak.add_argument("--voice")
    speak.add_argument("--interrupt", action="store_true", help="Stop the current speech first.")
    speak.add_argument("--no-wait", action="store_true", help="Do not wait until the speech ends.")
    sub.add_parser("cancel", help="Stop the current speech and clear the queue.")
    sub.add_parser("status", help="Show the voices, the current speech and the queue.")
    args = parser.parse_args()

    with connect(args.socket) as sock:
        message: dict = {"cmd": args.cmd}
        if args.cmd == "speak":
            message.update(text=args.text, interrupt=args.interrupt)
            if args.voice:
                message["voice"] = args.voice
        send(sock, message)
        request_id = None
        for event in events(sock):
            print(json.dumps(event, ensure_ascii=False))
            if args.cmd != "speak" or event["event"] == "error" and event.get("id") in (None, request_id):
                return 0 if event["event"] != "error" else 1
            if event["event"] == "accepted":
                request_id = event["id"]
                if args.no_wait:
                    return 0
            elif event.get("id") == request_id and event["event"] in FINAL_EVENTS:
                return 0 if event["event"] == "done" else 1
    return 1


if __name__ == "__main__":
    sys.exit(main())
