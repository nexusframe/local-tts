"""The streaming path must speak the same words as the batch path.

Batch path (M1, M2): split_sentences(normalize(text)).
Speak path (engine): SentenceStream gets all the text in one piece.
Streaming path (M4): SentenceStream gets the text in pieces, then each segment
is normalized alone and split again, because the normalizer can make new
sentence ends (for example from ";" or a removed tag). The inputs are the reviewed normalizer cases, alone and
joined in groups of 4.

A line end is a segment boundary, so the speak path can have more sentences
than the batch path ("- mleko\n- chleb"), but the words are the same.
"""

import csv
from pathlib import Path

import pytest

from local_tts.normalizer import normalize
from local_tts.splitter import SentenceStream, split_sentences

CASES = Path(__file__).parent / "data" / "normalizer_cases.tsv"


def load_texts() -> list[str]:
    with CASES.open(encoding="utf-8", newline="") as f:
        inputs = [row["input"].replace("\\n", "\n") for row in csv.DictReader(f, delimiter="\t", quoting=csv.QUOTE_NONE)]
    return inputs + [" ".join(inputs[i : i + 4]) for i in range(0, len(inputs), 4)]


def stream_segments(text: str, early_first: bool) -> list[str]:
    """Feed the text one character at a time, like the worst case of LLM tokens."""
    stream = SentenceStream(early_first=early_first)
    segments = [segment for char in text for segment in stream.feed(char)]
    return segments + stream.flush()


def speak_sentences(text: str) -> list[str]:
    stream = SentenceStream(early_first=False)
    segments = stream.feed(text) + stream.flush()
    return [s for segment in segments for s in split_sentences(normalize(segment))]


@pytest.mark.parametrize("text", load_texts())
def test_streamed_sentences_are_the_speak_sentences(text):
    streamed = [s for segment in stream_segments(text, early_first=False) for s in split_sentences(normalize(segment))]
    assert streamed == speak_sentences(text)


@pytest.mark.parametrize("text", load_texts())
def test_speak_path_does_not_change_the_spoken_words(text):
    assert " ".join(speak_sentences(text)) == " ".join(split_sentences(normalize(text)))


@pytest.mark.parametrize("text", load_texts())
def test_early_first_segment_does_not_change_the_spoken_words(text):
    streamed = [s for segment in stream_segments(text, early_first=True) for s in split_sentences(normalize(segment))]
    assert " ".join(streamed) == " ".join(split_sentences(normalize(text)))
