"""The daemon stops cleanly on SIGTERM and SIGINT: exit code 0, no socket file left.
Under systemd (Type=notify) it sends READY=1 when the socket listens, and STOPPING=1 at the stop.

The server runs in its own process with the fake model and sound card, because a
signal goes to the whole process.
"""

import os
import signal
import socket
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


def start_server(socket_path: Path, ignore_sigint: bool = False, env: dict | None = None) -> subprocess.Popen:
    code = SERVER.format(tests=str(Path(__file__).parent), socket=str(socket_path))
    # A shell starts a background job ("&") with SIGINT ignored. The child gets the same setting.
    preexec = (lambda: signal.signal(signal.SIGINT, signal.SIG_IGN)) if ignore_sigint else None
    process = subprocess.Popen(
        [sys.executable, "-c", code], preexec_fn=preexec, stderr=subprocess.PIPE, text=True, env=env
    )
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


def test_systemd_gets_ready_after_the_socket_listens_and_stopping_at_the_stop(tmp_path):
    socket_path = tmp_path / "tts.sock"
    notify = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    notify.bind(str(tmp_path / "notify"))
    notify.settimeout(10)
    process = start_server(socket_path, env={**os.environ, "NOTIFY_SOCKET": str(tmp_path / "notify")})
    try:
        assert notify.recv(256) == b"READY=1"
        assert socket_path.exists()
        process.send_signal(signal.SIGTERM)
        assert notify.recv(256) == b"STOPPING=1"
        assert process.wait(timeout=5) == 0
    finally:
        process.kill()
        notify.close()


def test_no_notify_socket_is_not_an_error(tmp_path):
    process = start_server(tmp_path / "tts.sock", env={k: v for k, v in os.environ.items() if k != "NOTIFY_SOCKET"})
    process.send_signal(signal.SIGTERM)
    assert process.wait(timeout=5) == 0, process.stderr.read()


def test_second_daemon_on_a_live_socket_stops_and_keeps_the_first_one(tmp_path):
    socket_path = tmp_path / "tts.sock"
    first = start_server(socket_path)
    try:
        code = SERVER.format(tests=str(Path(__file__).parent), socket=str(socket_path))
        second = subprocess.run([sys.executable, "-c", code], stderr=subprocess.PIPE, text=True, timeout=10)
        # 78 (EX_CONFIG): the unit file does not start it again.
        assert second.returncode == 78
        assert "already running" in second.stderr
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.connect(str(socket_path))
    finally:
        first.send_signal(signal.SIGTERM)
        first.wait(timeout=5)


def test_daemon_replaces_a_socket_file_that_nobody_listens_on(tmp_path):
    socket_path = tmp_path / "tts.sock"
    stale = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    stale.bind(str(socket_path))
    stale.close()
    process = start_server(socket_path)
    # The old file exists from the start: wait until the new server accepts a connection.
    deadline = time.monotonic() + 10
    while True:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            try:
                client.connect(str(socket_path))
                break
            except ConnectionRefusedError:
                if process.poll() is not None or time.monotonic() > deadline:
                    process.kill()
                    pytest.fail(f"server did not start: {process.communicate()[1]}")
                time.sleep(0.05)
    process.send_signal(signal.SIGTERM)
    assert process.wait(timeout=5) == 0


def test_sigterm_stops_the_server_also_with_a_connected_client(tmp_path):
    # A client such as the assistant keeps its connection open all the time.
    socket_path = tmp_path / "tts.sock"
    process = start_server(socket_path)
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.connect(str(socket_path))
        client.settimeout(5)
        process.send_signal(signal.SIGTERM)
        try:
            returncode = process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            pytest.fail("server did not stop while a client was connected")
        assert client.recv(1) == b""  # The server closed the connection.
    assert returncode == 0
