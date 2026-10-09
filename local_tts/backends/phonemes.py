"""Phoneme corrections for Polish espeak-ng output.

espeak-ng gives the same phonemes "tʃ" for "trz" (trzy) and "cz" (czy), so
Piper reads "trzy" like "czy". A longer fricative ("tʃʃ") for "trz" made "trz"
clearer in a blind listening test (see docs/trz-phonemes.md).
"""

from __future__ import annotations

import re

_TSH = ["t", "ʃ"]
_TRZ = ["t", "ʃ", "ʃ"]
_TSH_SPELLING = re.compile(r"trz|cz", re.IGNORECASE)


def lengthen_trz(text: str, sentence_phonemes: list[list[str]]) -> list[list[str]]:
    """Replace "tʃ" with "tʃʃ" where the text has "trz".

    The n-th "tʃ" in the phonemes belongs to the n-th "trz" or "cz" in the text.
    If the counts do not agree, the phonemes are returned without change.
    """
    spellings = [m.group().lower() for m in _TSH_SPELLING.finditer(text)]
    found = sum(_count_tsh(sentence) for sentence in sentence_phonemes)
    if found != len(spellings) or "trz" not in spellings:
        return sentence_phonemes

    remaining = iter(spellings)
    result = []
    for sentence in sentence_phonemes:
        out: list[str] = []
        i = 0
        while i < len(sentence):
            if sentence[i : i + 2] == _TSH:
                out.extend(_TRZ if next(remaining) == "trz" else _TSH)
                i += 2
            else:
                out.append(sentence[i])
                i += 1
        result.append(out)
    return result


def _count_tsh(sentence: list[str]) -> int:
    return sum(1 for i in range(len(sentence) - 1) if sentence[i : i + 2] == _TSH)
