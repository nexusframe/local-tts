import pytest

from local_tts.protocol import Append, Begin, Cancel, End, Flush, ProtocolError, Speak, Status, encode_event, parse_request


def test_speak_with_only_text_uses_defaults():
    assert parse_request('{"cmd": "speak", "text": "Cześć."}') == Speak(text="Cześć.")


def test_speak_with_all_fields():
    line = '{"cmd": "speak", "text": "Hej.", "voice": "gosia", "interrupt": true, "id": "a1"}'
    assert parse_request(line) == Speak(text="Hej.", voice="gosia", interrupt=True, id="a1")


def test_speed_is_a_rate_multiplier_for_speak_and_begin():
    assert parse_request('{"cmd": "speak", "text": "Hej.", "speed": 0.8}') == Speak(text="Hej.", speed=0.8)
    assert parse_request('{"cmd": "begin", "speed": 2}') == Begin(speed=2.0)
    assert parse_request('{"cmd": "speak", "text": "Hej."}').speed == 1.0


def test_cancel_and_status_commands():
    assert parse_request(b'{"cmd": "cancel"}\n') == Cancel()
    assert parse_request('{"cmd": "status"}') == Status()


def test_begin_opens_a_stream_with_the_speak_options():
    assert parse_request('{"cmd": "begin"}') == Begin()
    line = '{"cmd": "begin", "voice": "gosia", "interrupt": true, "id": "s1"}'
    assert parse_request(line) == Begin(voice="gosia", interrupt=True, id="s1")


def test_append_keeps_the_text_as_sent_also_whitespace():
    assert parse_request('{"cmd": "append", "id": "s1", "text": "Dzień"}') == Append(id="s1", text="Dzień")
    assert parse_request('{"cmd": "append", "id": "s1", "text": " "}') == Append(id="s1", text=" ")


def test_end_closes_a_stream():
    assert parse_request('{"cmd": "end", "id": "s1"}') == End(id="s1")


def test_flush_names_a_stream():
    assert parse_request('{"cmd": "flush", "id": "s1"}') == Flush(id="s1")


@pytest.mark.parametrize(
    "line",
    [
        "not json",
        "[1, 2]",
        '{"text": "Brak komendy."}',
        '{"cmd": "dance"}',
        '{"cmd": "speak"}',
        '{"cmd": "speak", "text": "   "}',
        '{"cmd": "speak", "text": 5}',
        '{"cmd": "speak", "text": "Hej.", "voice": 1}',
        '{"cmd": "speak", "text": "Hej.", "interrupt": "yes"}',
        '{"cmd": "speak", "text": "Hej.", "id": 7}',
        '{"cmd": "begin", "interrupt": 1}',
        '{"cmd": "speak", "text": "Hej.", "speed": "slow"}',
        '{"cmd": "speak", "text": "Hej.", "speed": true}',
        '{"cmd": "speak", "text": "Hej.", "speed": 0.4}',
        '{"cmd": "begin", "speed": 2.1}',
        '{"cmd": "append", "text": "Hej"}',
        '{"cmd": "append", "id": "s1"}',
        '{"cmd": "append", "id": "s1", "text": 5}',
        '{"cmd": "end"}',
        '{"cmd": "flush"}',
        '{"cmd": "flush", "id": 3}',
    ],
)
def test_invalid_requests_raise_protocol_error(line):
    with pytest.raises(ProtocolError):
        parse_request(line)


def test_event_is_one_json_line_with_polish_letters_kept():
    assert encode_event("started", id="a1", text="Żółw") == b'{"event": "started", "id": "a1", "text": "\xc5\xbb\xc3\xb3\xc5\x82w"}\n'
