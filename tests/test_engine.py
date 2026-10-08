import pytest

from local_tts.engine import Engine
from local_tts.protocol import Speak

from fakes import EventLog, FakeBackend, FakePlayer


@pytest.fixture
def log():
    return EventLog()


def make_engine(log, player=None, **backends):
    backends = backends or {"zenski": FakeBackend("zenski")}
    engine = Engine(backends, player or FakePlayer(), on_event=log, default_voice=next(iter(backends)))
    engine.start()
    return engine


def test_speak_plays_each_sentence_in_order(log):
    player = FakePlayer()
    engine = make_engine(log, player)
    request_id = engine.speak(Speak(text="Raz. Dwa. Trzy."))
    log.wait_for("done", id=request_id)
    engine.close()
    assert player.played == ["zenski:Raz.", "zenski:Dwa.", "zenski:Trzy."]
    assert log.names(id=request_id) == ["started", "done"]


def test_voice_selects_the_backend_and_queued_requests_play_in_order(log):
    player = FakePlayer()
    engine = make_engine(log, player, zenski=FakeBackend("zenski"), gosia=FakeBackend("gosia"))
    engine.speak(Speak(text="Pytanie?"))
    last = engine.speak(Speak(text="Odpowiedź.", voice="gosia"))
    log.wait_for("done", id=last)
    engine.close()
    assert player.played == ["zenski:Pytanie?", "gosia:Odpowiedź."]


def test_unknown_voice_is_rejected_at_once(log):
    engine = make_engine(log)
    with pytest.raises(ValueError, match="nobody"):
        engine.speak(Speak(text="Hej.", voice="nobody"))
    engine.close()


def test_cancel_stops_current_speech_and_clears_the_queue(log):
    player = FakePlayer(blocking=True)
    engine = make_engine(log, player)
    first = engine.speak(Speak(text="Raz. Dwa."))
    queued = engine.speak(Speak(text="Czekam."))
    log.wait_for("started", id=first)

    engine.cancel()

    log.wait_for("cancelled", id=first)
    log.wait_for("cancelled", id=queued)
    after = engine.speak(Speak(text="Nowe."))
    log.wait_for("done", id=after)
    engine.close()
    assert player.played == ["zenski:Nowe."]
    assert log.names(id=first) == ["started", "cancelled"]
    assert log.names(id=queued) == ["cancelled"]


def test_interrupt_cuts_current_speech_and_plays_the_new_request(log):
    player = FakePlayer(blocking=True)
    engine = make_engine(log, player)
    old = engine.speak(Speak(text="Długa odpowiedź."))
    log.wait_for("started", id=old)

    new = engine.speak(Speak(text="Nowe pytanie.", interrupt=True))

    log.wait_for("done", id=new)
    engine.close()
    assert player.played == ["zenski:Nowe pytanie."]
    assert log.names(id=old) == ["started", "cancelled"]


def test_backend_error_is_reported_and_the_engine_continues(log):
    player = FakePlayer()
    engine = make_engine(log, player, zenski=FakeBackend("zenski", fail_on="Zepsute"))
    broken = engine.speak(Speak(text="Dobre. Zepsute. Nieczytane."))
    after = engine.speak(Speak(text="Dalej."))
    error = log.wait_for("error", id=broken)
    log.wait_for("done", id=after)
    engine.close()
    assert "Zepsute" in error["message"]
    assert log.names(id=broken) == ["started", "error"]
    assert player.played == ["zenski:Dobre.", "zenski:Dalej."]


def test_next_request_is_synthesized_while_the_current_one_plays(log):
    backend = FakeBackend("zenski")
    player = FakePlayer(blocking=True)
    engine = make_engine(log, player, zenski=backend)
    first = engine.speak(Speak(text="Raz. Dwa."))
    second = engine.speak(Speak(text="Trzy."))
    log.wait_for("started", id=first)

    wait_until(lambda: backend.calls == ["Raz.", "Dwa.", "Trzy."])
    assert player.played == []

    player.release()
    log.wait_for("done", id=second)
    engine.close()
    assert player.played == ["zenski:Raz.", "zenski:Dwa.", "zenski:Trzy."]
    assert log.names() == ["started", "done", "started", "done"]


def wait_until(condition, timeout=2.0):
    import time

    deadline = time.monotonic() + timeout
    while not condition():
        assert time.monotonic() < deadline, "condition not met in time"
        time.sleep(0.005)


def test_status_shows_voices_current_speech_and_queue(log):
    player = FakePlayer(blocking=True)
    engine = make_engine(log, player, zenski=FakeBackend("zenski"), gosia=FakeBackend("gosia"))
    assert engine.status() == {"voices": ["gosia", "zenski"], "default_voice": "zenski", "speaking": None, "queued": []}

    first = engine.speak(Speak(text="Raz."))
    second = engine.speak(Speak(text="Dwa.", voice="gosia"))
    log.wait_for("started", id=first)
    assert engine.status()["speaking"] == first
    assert engine.status()["queued"] == [second]

    player.release()
    log.wait_for("done", id=second)
    assert engine.status()["speaking"] is None
    assert engine.status()["queued"] == []
    engine.close()
