import pytest

from local_tts.engine import Engine
from local_tts.protocol import Begin, Speak

from fakes import EventLog, FakeBackend, FakePlayer, SlowBackend


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


def test_done_event_reports_the_played_audio_duration(log):
    engine = make_engine(log)
    request_id = engine.speak(Speak(text="Raz. Dwa."))
    done = log.wait_for("done", id=request_id)
    engine.close()
    # FakeBackend gives 10 samples for each sentence at 22050 Hz.
    assert done["audio_seconds"] == pytest.approx(20 / 22050)


def test_text_is_normalized_before_synthesis(log):
    backend = FakeBackend("zenski")
    engine = make_engine(log, zenski=backend)
    request_id = engine.speak(Speak(text="Kosztuje 5 zł. Dr Nowak wraca o 14:30."))
    log.wait_for("done", id=request_id)
    engine.close()
    assert backend.calls == ["Kosztuje pięć złotych.", "Doktor Nowak wraca o czternastej trzydzieści."]


def test_stream_plays_the_text_that_comes_in_pieces(log):
    player = FakePlayer()
    engine = make_engine(log, player)
    stream = engine.begin(Begin())
    for piece in ["Raz", ". Dwa", " i trzy", ". Cztery."]:
        engine.append(stream, piece)
    engine.end(stream)
    log.wait_for("done", id=stream)
    engine.close()
    assert player.played == ["zenski:Raz.", "zenski:Dwa i trzy.", "zenski:Cztery."]
    assert log.names(id=stream) == ["started", "done"]


def test_stream_starts_to_play_before_the_text_ends(log):
    player = FakePlayer()
    engine = make_engine(log, player)
    stream = engine.begin(Begin())
    engine.append(stream, "Jasne, już")

    log.wait_for("started", id=stream)
    wait_until(lambda: player.played == ["zenski:Jasne,"])

    engine.append(stream, " sprawdzam.")
    engine.end(stream)
    log.wait_for("done", id=stream)
    engine.close()
    assert player.played == ["zenski:Jasne,", "zenski:już sprawdzam."]


def test_cancel_ends_an_open_stream_and_later_pieces_are_ignored(log):
    player = FakePlayer()
    engine = make_engine(log, player)
    stream = engine.begin(Begin())
    engine.append(stream, "Raz. Dwa")
    log.wait_for("started", id=stream)

    engine.cancel()
    log.wait_for("cancelled", id=stream)
    # The LLM can send more tokens before the client sees the event.
    engine.append(stream, " i trzy.")
    engine.end(stream)

    after = engine.speak(Speak(text="Nowe."))
    log.wait_for("done", id=after)
    engine.close()
    assert player.played == ["zenski:Raz.", "zenski:Nowe."]
    assert log.names(id=stream) == ["started", "cancelled"]


def test_speak_waits_until_the_open_stream_ends(log):
    player = FakePlayer()
    engine = make_engine(log, player)
    stream = engine.begin(Begin())
    queued = engine.speak(Speak(text="Potem."))
    engine.append(stream, "Najpierw.")
    engine.end(stream)
    log.wait_for("done", id=queued)
    engine.close()
    assert player.played == ["zenski:Najpierw.", "zenski:Potem."]


def test_append_to_an_unknown_or_ended_stream_is_an_error(log):
    engine = make_engine(log)
    with pytest.raises(ValueError, match="nobody"):
        engine.append("nobody", "Hej.")
    stream = engine.begin(Begin())
    engine.end(stream)
    with pytest.raises(ValueError, match=stream):
        engine.append(stream, "Za późno.")
    engine.close()


def test_abort_cancels_only_that_stream(log):
    player = FakePlayer(blocking=True)
    engine = make_engine(log, player)
    stream = engine.begin(Begin())
    queued = engine.speak(Speak(text="Potem."))
    engine.append(stream, "Raz. Dwa")
    log.wait_for("started", id=stream)

    engine.abort(stream)

    log.wait_for("cancelled", id=stream)
    log.wait_for("done", id=queued)
    engine.close()
    assert player.played == ["zenski:Potem."]
    assert log.names(id=stream) == ["started", "cancelled"]


def test_interrupt_stops_the_synthesis_of_a_long_sentence(log):
    backend = SlowBackend("zenski")
    player = FakePlayer()
    engine = make_engine(log, player, zenski=backend)
    old = engine.speak(Speak(text="Krótkie. Długie zdanie."))
    log.wait_for("started", id=old)
    wait_until(lambda: "Długie zdanie." in backend.calls)

    new = engine.speak(Speak(text="Nowe.", interrupt=True))

    log.wait_for("done", id=new, timeout=1.0)
    engine.close()
    assert backend.interrupts >= 1
    assert log.names(id=old) == ["started", "cancelled"]
    assert player.played == ["zenski:Krótkie.", "zenski:Nowe."]


def test_abort_stops_the_synthesis_of_its_stream(log):
    backend = SlowBackend("zenski")
    engine = make_engine(log, zenski=backend)
    stream = engine.begin(Begin())
    engine.append(stream, "Długie zdanie. Dalej")
    wait_until(lambda: backend.calls == ["Długie zdanie."])

    engine.abort(stream)

    log.wait_for("cancelled", id=stream, timeout=1.0)
    engine.close()
    assert backend.interrupts == 1


def test_first_words_sets_the_word_limit_of_the_early_first_segment(log):
    player = FakePlayer()
    engine = Engine({"zenski": FakeBackend("zenski")}, player, on_event=log, default_voice="zenski", first_words=2)
    engine.start()
    stream = engine.begin(Begin())
    engine.append(stream, "Raz dwa trzy cztery")
    wait_until(lambda: player.played == ["zenski:Raz dwa"])
    engine.end(stream)
    log.wait_for("done", id=stream)
    engine.close()
    assert player.played == ["zenski:Raz dwa", "zenski:trzy cztery"]
