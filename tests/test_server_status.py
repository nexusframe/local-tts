"""The status event shows the memory and uptime of the daemon process and the results of the utterances."""

import json
import signal
import socket

from test_server_signals import start_server


def request(sock_file, sock, message: dict, until: str) -> dict:
    sock.sendall((json.dumps(message) + "\n").encode())
    while True:
        event = json.loads(sock_file.readline())
        if event["event"] == until:
            return event


def test_status_has_memory_uptime_and_result_counts(tmp_path):
    socket_path = tmp_path / "tts.sock"
    process = start_server(socket_path)
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.connect(str(socket_path))
            lines = sock.makefile("r", encoding="utf-8")
            request(lines, sock, {"cmd": "speak", "text": "Raz."}, until="done")
            status = request(lines, sock, {"cmd": "status"}, until="status")
    finally:
        process.send_signal(signal.SIGTERM)
        process.wait(timeout=5)

    assert status["voices"] == ["zenski"]  # The fields of the engine stay.
    assert 0 < status["rss_mb"] <= status["peak_rss_mb"]
    assert status["uptime_s"] >= 0
    assert status["results"] == {"done": 1, "cancelled": 0, "error": 0}
