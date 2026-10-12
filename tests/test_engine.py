import pytest

from local_tts.engine import Engine
from local_tts.protocol import Begin, Speak

from fakes import EventLog, FakeBackend, FakeChunk, FakePlayer, SlowBackend


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
    assert engine.status() == {"voices": ["gosia", "zenski"], "languages": {"gosia": "pl", "zenski": "pl"},
                               "default_voice": "zenski", "speaking": None, "queued": []}

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


def test_english_voice_gets_no_polish_normalization(log):
    # espeak-ng en reads numbers and times itself. Markup and tags are still removed.
    backend = FakeBackend("en_male", language="en")
    engine = make_engine(log, zenski=FakeBackend("zenski"), en_male=backend)
    request_id = engine.speak(Speak(text="Meeting at 9:30, **Dr. Smith**. <en>Bring</en> 5 cups [pause] now.", voice="en_male"))
    log.wait_for("done", id=request_id)
    engine.close()
    assert backend.calls == ["Meeting at 9:30, Dr. Smith.", "Bring 5 cups now."]


def test_status_shows_the_language_of_each_voice(log):
    engine = make_engine(log, zenski=FakeBackend("zenski"), en_male=FakeBackend("en_male", language="en"))
    assert engine.status()["languages"] == {"en_male": "en", "zenski": "pl"}
    engine.close()


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


def test_cancelled_event_reports_the_sentences_that_were_played(log):
    player = FakePlayer(block_on="Trzy")
    engine = make_engine(log, player)
    request_id = engine.speak(Speak(text="Raz. Dwa. Trzy."))
    assert player.blocked.wait(2.0)

    engine.cancel()

    event = log.wait_for("cancelled", id=request_id)
    engine.close()
    assert event["spoken"] == "Raz. Dwa."


def test_a_sentence_still_in_the_output_buffer_is_not_spoken(log):
    player = FakePlayer(block_on="Trzy")
    engine = make_engine(log, player)
    request_id = engine.speak(Speak(text="Raz. Dwa. Trzy."))
    assert player.blocked.wait(2.0)
    # The audio of "Dwa." was written, but the listener did not hear it yet.
    player.queued = len(FakeChunk("zenski", "Dwa.")) / FakeBackend.sample_rate

    engine.cancel()

    event = log.wait_for("cancelled", id=request_id)
    engine.close()
    assert event["spoken"] == "Raz."


def test_a_queued_request_that_did_not_start_has_no_spoken_text(log):
    engine = make_engine(log, zenski=SlowBackend("zenski"))
    first = engine.speak(Speak(text="Raz. Długie zdanie."))
    # The synthesis waits in "Długie", so this request stays in the request queue.
    queued = engine.speak(Speak(text="Czekam."))
    log.wait_for("started", id=first)

    engine.cancel()

    events = {e: log.wait_for("cancelled", id=e) for e in (first, queued)}
    engine.close()
    assert events[first]["spoken"] == "Raz."
    assert events[queued]["spoken"] == ""


def test_spoken_text_of_a_stream_is_the_text_that_the_client_sent(log):
    player = FakePlayer(block_on="Koniec")
    engine = make_engine(log, player)
    stream_id = engine.begin(Begin())
    for piece in ["Mam 2 ", "koty", " i psa. ", "Koniec", " tekstu. ", "Dalej."]:
        engine.append(stream_id, piece)
    assert player.blocked.wait(2.0)

    engine.cancel()

    event = log.wait_for("cancelled", id=stream_id)
    engine.close()
    assert event["spoken"] == "Mam 2 koty i psa."


def test_error_event_reports_the_sentences_that_were_played(log):
    engine = make_engine(log, zenski=FakeBackend("zenski", fail_on="Błąd"))
    request_id = engine.speak(Speak(text="Raz. Błąd. Trzy."))

    event = log.wait_for("error", id=request_id)
    engine.close()
    assert event["spoken"] == "Raz."


def test_abort_reports_the_sentences_that_were_heard(log):
    player = FakePlayer(block_on="Trzy")
    engine = make_engine(log, player)
    stream_id = engine.begin(Begin())
    engine.append(stream_id, "Raz, dwa. Cztery. Trzy. Pięć.")
    assert player.blocked.wait(2.0)
    player.queued = len(FakeChunk("zenski", "Cztery.")) / FakeBackend.sample_rate

    engine.abort(stream_id)

    event = log.wait_for("cancelled", id=stream_id)
    engine.close()
    assert event["spoken"] == "Raz, dwa."


def test_flush_plays_the_incomplete_sentence_and_the_stream_stays_open(log):
    player = FakePlayer()
    engine = make_engine(log, player)
    stream_id = engine.begin(Begin())
    engine.append(stream_id, "Sprawdzam pogodę")

    engine.flush(stream_id)

    log.wait_for("started", id=stream_id)
    engine.append(stream_id, ". Jutro będzie słońce.")
    engine.end(stream_id)
    log.wait_for("done", id=stream_id)
    engine.close()
    assert player.played == ["zenski:Sprawdzam pogodę", "zenski:Jutro będzie słońce."]


def test_text_after_a_flush_starts_to_play_early_again(log):
    player = FakePlayer()
    engine = make_engine(log, player)
    stream_id = engine.begin(Begin())
    engine.append(stream_id, "Dobrze, sprawdzam pogodę.")
    engine.flush(stream_id)
    wait_until(lambda: player.played == ["zenski:Dobrze,", "zenski:sprawdzam pogodę."])

    engine.append(stream_id, " Jutro będzie ciepło ")

    wait_until(lambda: player.played[2:] == ["zenski:Jutro będzie"])
    engine.append(stream_id, "i słońce.")
    engine.end(stream_id)
    log.wait_for("done", id=stream_id)
    engine.close()
    assert player.played[-1] == "zenski:ciepło i słońce."


def test_flush_with_no_waiting_text_plays_nothing(log):
    player = FakePlayer()
    engine = make_engine(log, player)
    stream_id = engine.begin(Begin())
    engine.flush(stream_id)
    engine.append(stream_id, "Raz.")
    engine.end(stream_id)
    log.wait_for("done", id=stream_id)
    engine.close()
    assert player.played == ["zenski:Raz."]


def test_flush_of_a_cancelled_stream_is_ignored_and_of_an_unknown_stream_is_an_error(log):
    engine = make_engine(log)
    stream_id = engine.begin(Begin())
    engine.cancel()
    engine.flush(stream_id)
    with pytest.raises(ValueError, match="no open stream"):
        engine.flush("nobody")
    engine.close()
