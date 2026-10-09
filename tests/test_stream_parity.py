"""The streaming path must speak the same words as the batch path.

Batch path (M1, M2): split_sentences(normalize(text)).
Streaming path (M4): SentenceStream gets the text in pieces, then each segment
is normalized alone and split again, because the normalizer can make new
sentence ends (for example from ";" or a removed tag). The inputs are the reviewed normalizer cases, alone and
joined in groups of 4.
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


@pytest.mark.parametrize("text", load_texts())
def test_streamed_sentences_are_the_batch_sentences(text):
    streamed = [s for segment in stream_segments(text, early_first=False) for s in split_sentences(normalize(segment))]
    assert streamed == split_sentences(normalize(text))


@pytest.mark.parametrize("text", load_texts())
def test_early_first_segment_does_not_change_the_spoken_words(text):
    streamed = [s for segment in stream_segments(text, early_first=True) for s in split_sentences(normalize(segment))]
    assert " ".join(streamed) == " ".join(split_sentences(normalize(text)))
