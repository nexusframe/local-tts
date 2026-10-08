import pytest

from local_tts.protocol import Cancel, ProtocolError, Speak, Status, encode_event, parse_request


def test_speak_with_only_text_uses_defaults():
    assert parse_request('{"cmd": "speak", "text": "Cześć."}') == Speak(text="Cześć.")


def test_speak_with_all_fields():
    line = '{"cmd": "speak", "text": "Hej.", "voice": "gosia", "interrupt": true, "id": "a1"}'
    assert parse_request(line) == Speak(text="Hej.", voice="gosia", interrupt=True, id="a1")


def test_cancel_and_status_commands():
    assert parse_request(b'{"cmd": "cancel"}\n') == Cancel()
    assert parse_request('{"cmd": "status"}') == Status()


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
    ],
)
def test_invalid_requests_raise_protocol_error(line):
    with pytest.raises(ProtocolError):
        parse_request(line)


def test_event_is_one_json_line_with_polish_letters_kept():
    assert encode_event("started", id="a1", text="Żółw") == b'{"event": "started", "id": "a1", "text": "\xc5\xbb\xc3\xb3\xc5\x82w"}\n'
