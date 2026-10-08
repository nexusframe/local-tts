"""Normalizer cases from tests/data/normalizer_cases.tsv.

The expected forms were reviewed by a native Polish speaker. Categories are
enabled one at a time (TDD). Cases with priority "nice" may fail.
"""

import csv
from pathlib import Path

import pytest

from local_tts.normalizer import normalize

CASES = Path(__file__).parent / "data" / "normalizer_cases.tsv"
ENABLED = {"cleanup", "corpus-unchanged", "punctuation", "cardinal", "case", "currency", "unit", "percent", "time", "date", "abbreviation", "corpus", "ordinal"}


def load_cases():
    with CASES.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f, delimiter="\t", quoting=csv.QUOTE_NONE):
            if row["category"] not in ENABLED:
                continue
            marks = [pytest.mark.xfail(reason="nice to have", strict=False)] if row["priority"] == "nice" else []
            yield pytest.param(row["input"].replace("\\n", "\n"), row["expected"], id=row["id"], marks=marks)


@pytest.mark.parametrize(("text", "expected"), load_cases())
def test_normalize(text, expected):
    assert normalize(text) == expected
