"""Phoneme corrections for Polish espeak-ng output.

espeak-ng gives the same phonemes "tʃ" for "trz" (trzy) and "cz" (czy), so
Piper reads "trzy" like "czy". A longer fricative ("tʃʃ") for "trz" made "trz"
clearer in a blind listening test (see docs/trz-phonemes.md).

espeak-ng also gives the same phonemes "dʑ" for "dz" (widzenia) and for "dzi"/"dź"
(dzień). The phonemes "d" "z" for "dz" were better in a listening test (2026-10-12).

The zenski voice reads "iɡˈɛ" (inteligencji) like "gie". The stress mark before
"ɡ" ("iˈɡɛ") was better in a listening test (2026-10-12).
"""

from __future__ import annotations

import re
from typing import Callable

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


_DZJ = "dʑ"
# "dż" is "dʒ" and does not count.
_DZ_SPELLING = re.compile(r"dź|dzi|dz(?![żź])", re.IGNORECASE)


def fix_dz(text: str, sentence_phonemes: list[list[str]]) -> list[list[str]]:
    """Replace "dʑ" with "d" "z" where the text has "dz" (not "dzi" or "dź").

    As in lengthen_trz(), the n-th "dʑ" belongs to the n-th spelling. If the counts
    do not agree ("wódz" is "vuts", "być dobrym" has a "dʑ"), there is no change.
    """
    spellings = [m.group().lower() for m in _DZ_SPELLING.finditer(text)]
    found = sum("".join(sentence).count(_DZJ) for sentence in sentence_phonemes)
    if found != len(spellings) or "dz" not in spellings:
        return sentence_phonemes

    remaining = iter(spellings)
    result = []
    for sentence in sentence_phonemes:
        out: list[str] = []
        i = 0
        while i < len(sentence):
            if "".join(sentence[i : i + 2]) == _DZJ:
                out.extend(["d", "z"] if next(remaining) == "dz" else ["d", "ʑ"])
                i += 2
            else:
                out.append(sentence[i])
                i += 1
        result.append(out)
    return result


_I_G_STRESS = ["i", "ɡ", "ˈ", "ɛ"]
_I_STRESS_G = ["i", "ˈ", "ɡ", "ɛ"]


def stress_before_g(text: str, sentence_phonemes: list[list[str]]) -> list[list[str]]:
    """Replace "iɡˈɛ" with "iˈɡɛ". The text is not used."""
    result = []
    for sentence in sentence_phonemes:
        out = list(sentence)
        for i in range(len(out) - 3):
            if out[i : i + 4] == _I_G_STRESS:
                out[i : i + 4] = _I_STRESS_G
        result.append(out)
    return result


def _count_tsh(sentence: list[str]) -> int:
    return sum(1 for i in range(len(sentence) - 1) if sentence[i : i + 2] == _TSH)


# English phonemes (espeak-ng en-us) that the Polish voices did not learn, and the
# nearest Polish phonemes. Diphthongs first. A listening test (2026-10-10) found this
# better than raw English IPA and better than English words in Polish spelling.
_ENGLISH_TO_POLISH = [
    ("eɪ", "ɛj"), ("aɪ", "aj"), ("ɔɪ", "ɔj"), ("oʊ", "ɔw"), ("aʊ", "aw"), ("ɚ", "ɛr"),
    ("æ", "ɛ"), ("ð", "d"), ("θ", "f"), ("ɐ", "a"), ("ɑ", "a"), ("ə", "ɛ"), ("ɜ", "ɛ"),
    ("ɪ", "ɨ"), ("ᵻ", "ɨ"), ("ɹ", "r"), ("ɾ", "t"), ("ʊ", "u"), ("ʌ", "a"), ("ː", ""),
    ("h", "x"), ("e", "ɛ"), ("o", "ɔ"),
]


def to_polish_phonemes(ipa: str) -> str:
    """Change English IPA into phonemes that the Polish voices know."""
    for english, polish in _ENGLISH_TO_POLISH:
        ipa = ipa.replace(english, polish)
    return ipa


Phonemizer = Callable[[str], list[list[str]]]
# The normalizer gives paired tags. re.split puts the English parts at odd indexes.
_ENGLISH_SPAN = re.compile(r"<en>(.*?)</en>", re.DOTALL)
# espeak-ng gives no phonemes for punctuation before the first word of a part.
_LEADING_PUNCTUATION = re.compile(r"^[.,!?;:]+")


def phonemize_mixed(text: str, polish: Phonemizer, english: Phonemizer) -> list[list[str]]:
    """Phonemes for text with <en>...</en> spans, grouped by sentence.

    Each part goes to its own phonemizer. The first sentence of a part continues
    the last sentence of the part before it, as in the [[ ]] blocks of piper-tts.
    A space between the parts in the text gives a space phoneme. Punctuation
    right after a span stays, because the intonation of the sentence needs it.
    """
    if "<en>" not in text:
        return polish(text)
    parts = _ENGLISH_SPAN.split(text)
    result: list[list[str]] = []
    space = False
    preposition = ""
    for i, part in enumerate(parts):
        is_english = i % 2 == 1
        punctuation = _LEADING_PUNCTUATION.match(part)
        if punctuation and result:
            # Keep it as espeak-ng does: punctuation is a phoneme, with a space after , ; :
            result[-1].extend(punctuation.group())
            part = part[punctuation.end():]
            if punctuation.group()[-1] in ",;:":
                result[-1].append(" ")
                part = part.lstrip()
        if not is_english and i + 1 < len(parts):
            match = _LAST_PREPOSITION.search(part)
            if match:
                preposition = match.group(1).lower()
                part = part[: match.start(1)]
        if not part.strip():
            space = space or bool(part)
            continue
        attached = bool(result) and not (space or part[0].isspace())
        lone_y = attached and not is_english and _LONE_Y.match(part)
        if lone_y:
            part = "t" + part
        sentences = [s for s in (english if is_english else polish)(part.strip()) if s]
        if lone_y and sentences and "t" in sentences[0]:
            sentences[0].remove("t")
        if not sentences:
            continue
        if is_english and preposition:
            sentences[0] = [*_preposition_phonemes(preposition, sentences[0]), " ", *sentences[0]]
            preposition = ""
        elif attached:
            sentences[0] = _without_first_word_stress(sentences[0])
        if result:
            if not attached:
                result[-1].append(" ")
            junction = len(result[-1])
            result[-1].extend(sentences[0])
            result.extend(sentences[1:])
            if attached and not is_english:
                _stress_word_at(result[-1], junction)
        else:
            result.extend(sentences)
        space = part[-1].isspace()
    return result


# Alone, espeak-ng reads "w" and "z" as letter names ("vɨ", "zɨ"). In a sentence it
# gives "f"/"w" and "s"/"z": voiceless before a voiceless phoneme.
_LAST_PREPOSITION = re.compile(r"(?:^|\s)([wWzZ])\s*$")
_PREPOSITIONS = {"w": ("f", "w"), "z": ("s", "z")}
# Alone, espeak-ng reads "y" as "ˈiɡrɛk". The ending "<en>commit</en>y" goes as "ty",
# then the "t" phoneme is removed.
_LONE_Y = re.compile(r"[yY](?!\w)")
_VOICELESS = frozenset("ptkfsʃxθhɕ")
_STRESS = frozenset("ˈˌ")


def _preposition_phonemes(preposition: str, next_phonemes: list[str]) -> list[str]:
    first = next((p.lower() for p in next_phonemes if p not in _STRESS), "")
    voiceless, voiced = _PREPOSITIONS[preposition]
    return [voiceless if first in _VOICELESS else voiced]


_VOWELS = frozenset("aɛiɨɔu")


def _stress_word_at(phonemes: list[str], position: int) -> None:
    """Polish stress for the word at position: the second-to-last vowel.

    An English stem with a Polish ending ("<en>push</en>ować") is one Polish word.
    espeak-ng puts the stress mark right before the vowel.
    """
    start = position
    while start > 0 and phonemes[start - 1] != " ":
        start -= 1
    end = position
    while end < len(phonemes) and phonemes[end] != " ":
        end += 1
    word = [p for p in phonemes[start:end] if p not in _STRESS]
    vowels = [i for i, p in enumerate(word) if p in _VOWELS]
    if len(vowels) >= 2:
        word.insert(vowels[-2], "ˈ")
    phonemes[start:end] = word


def _without_first_word_stress(phonemes: list[str]) -> list[str]:
    """A Polish ending right after a span ("<en>Python</en>ie") is not stressed."""
    end = phonemes.index(" ") if " " in phonemes else len(phonemes)
    return [p for p in phonemes[:end] if p not in _STRESS] + phonemes[end:]
