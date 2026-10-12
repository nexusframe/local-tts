"""The daemon stops cleanly on SIGTERM and SIGINT: exit code 0, no socket file left.

The server runs in its own process with the fake model and sound card, because a
signal goes to the whole process.
"""

import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

SERVER = """
import asyncio, sys
from pathlib import Path
sys.path.insert(0, {tests!r})
from fakes import FakeBackend, FakePlayer
from local_tts.engine import Engine
from local_tts.server import Server
server = Server(lambda on_event: Engine({{"zenski": FakeBackend("zenski")}}, FakePlayer(), on_event, "zenski"), Path({socket!r}))
asyncio.run(server.serve_forever())
"""


def start_server(socket_path: Path, ignore_sigint: bool = False) -> subprocess.Popen:
    code = SERVER.format(tests=str(Path(__file__).parent), socket=str(socket_path))
    # A shell starts a background job ("&") with SIGINT ignored. The child gets the same setting.
    preexec = (lambda: signal.signal(signal.SIGINT, signal.SIG_IGN)) if ignore_sigint else None
    process = subprocess.Popen([sys.executable, "-c", code], preexec_fn=preexec, stderr=subprocess.PIPE, text=True)
    deadline = time.monotonic() + 10
    while not socket_path.exists():
        if process.poll() is not None or time.monotonic() > deadline:
            process.kill()
            pytest.fail(f"server did not start: {process.communicate()[1]}")
        time.sleep(0.05)
    return process


@pytest.mark.parametrize(
    ("sig", "ignore_sigint"),
    [(signal.SIGTERM, False), (signal.SIGINT, False), (signal.SIGINT, True)],
    ids=["sigterm", "sigint", "sigint-background-job"],
)
def test_signal_stops_server_and_removes_socket(tmp_path, sig, ignore_sigint):
    socket_path = tmp_path / "tts.sock"
    process = start_server(socket_path, ignore_sigint)

    process.send_signal(sig)
    try:
        returncode = process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        pytest.fail("server did not stop")

    assert returncode == 0, process.stderr.read()
    assert not socket_path.exists()
