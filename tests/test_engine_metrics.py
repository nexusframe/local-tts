"""One "metrics" log line for each utterance: times of synthesis and first audio, RTF, result."""

import json
import logging
import time

import pytest

from local_tts.engine import Engine
from local_tts.protocol import Begin, Speak

from fakes import EventLog, FakeBackend, FakePlayer


class SlowFakeBackend(FakeBackend):
    """Each sentence takes `delay` seconds to synthesize."""

    def __init__(self, delay: float, **kwargs) -> None:
        super().__init__(**kwargs)
        self.delay = delay

    def synthesize(self, text, word_ends=None, speed=1.0):
        time.sleep(self.delay)
        yield from super().synthesize(text, word_ends, speed)


@pytest.fixture
def log():
    return EventLog()


@pytest.fixture
def metrics(caplog):
    caplog.set_level(logging.INFO, logger="local_tts.engine")

    def lines(request_id):
        found = [json.loads(r.getMessage().removeprefix("metrics ")) for r in caplog.records if r.getMessage().startswith("metrics ")]
        return [m for m in found if m["id"] == request_id]

    return lines


def make_engine(log, backend):
    engine = Engine({"zenski": backend}, FakePlayer(), on_event=log, default_voice="zenski")
    engine.start()
    return engine


def test_done_utterance_has_one_metrics_line_with_times_and_rtf(log, metrics):
    engine = make_engine(log, SlowFakeBackend(0.05, name="zenski", chunk_seconds=0.5))
    text = "Raz. Dwa. Trzy."
    request_id = engine.speak(Speak(text=text))
    log.wait_for("done", id=request_id)
    engine.close()

    [line] = metrics(request_id)
    assert line["voice"] == "zenski"
    assert line["result"] == "done"
    assert line["chars"] == len(text)
    assert line["sentences"] == 3
    assert line["audio_s"] == pytest.approx(1.5, abs=0.001)
    assert line["synth_s"] >= 0.15
    assert line["rtf"] == pytest.approx(line["synth_s"] / line["audio_s"], abs=0.001)
    # The first sentence is synthesized before the first audio.
    assert 0.05 <= line["first_audio_s"] < line["synth_s"]


def test_first_audio_of_a_stream_counts_from_the_first_text_not_from_begin(log, metrics):
    engine = make_engine(log, FakeBackend("zenski"))
    stream = engine.begin(Begin())
    time.sleep(0.3)  # The LLM gives no text yet.
    engine.append(stream, "Dzień dobry.")
    engine.end(stream)
    log.wait_for("done", id=stream)
    engine.close()

    [line] = metrics(stream)
    assert line["first_audio_s"] < 0.2


def test_cancelled_and_error_utterances_have_their_result(log, metrics):
    backend = FakeBackend("zenski", fail_on="Zepsute")
    engine = make_engine(log, backend)
    broken = engine.speak(Speak(text="Zepsute zdanie."))
    log.wait_for("error", id=broken)
    stream = engine.begin(Begin())
    engine.cancel()
    log.wait_for("cancelled", id=stream)
    engine.close()

    assert [line["result"] for line in metrics(broken)] == ["error"]
    [cancelled] = metrics(stream)
    assert cancelled["result"] == "cancelled"
    # No audio: no first audio time and no RTF.
    assert cancelled["first_audio_s"] is None
    assert cancelled["rtf"] is None
