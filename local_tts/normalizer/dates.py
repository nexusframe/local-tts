"""Dates: 15.11.2026 r., 2026-11-15, 15.11, 1 maja, w 2026 r."""

from __future__ import annotations

import re

from local_tts.normalizer.grammar import previous_word
from local_tts.normalizer.numbers import ordinal

MONTHS_GENITIVE = [None, "stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca", "lipca",
                   "sierpnia", "września", "października", "listopada", "grudnia"]

# After these words the day is in the nominative: "dziś jest trzeci maja".
_NOMINATIVE_BEFORE = frozenset("jest był była było będzie".split())

_YEAR_SUFFIX = r"(?P<r>\s?r\.)?"
_FULL = re.compile(rf"(?<![\w.])(?P<d>[0-3]?\d)\.(?P<m>[01]\d)\.(?P<y>\d{{4}}){_YEAR_SUFFIX}(?![\w])")
_ISO = re.compile(r"(?<![\w-])(?P<y>\d{4})-(?P<m>[01]\d)-(?P<d>[0-3]\d)(?![\w-])")
_DAY_MONTH = re.compile(r"(?<![\w.,])(?P<d>[0-3]?\d)\.(?P<m>[01]\d)(?![\w]|\.\d)")
_DAY_MONTH_NAME = re.compile(rf"(?<![\w.,])(?P<d>[0-3]?\d)\s(?P<month>{'|'.join(MONTHS_GENITIVE[1:])})\b")
_YEAR = re.compile(rf"(?<![\w.,])(?P<y>\d{{4}})\s?r\.")
_SENTENCE_STARTS = re.compile(r"\s*(?:$|[A-ZĄĆĘŁŃÓŚŹŻ])")


def _valid(day: int, month: int) -> bool:
    return 1 <= day <= 31 and 1 <= month <= 12


def _day_case(text: str, position: int) -> str:
    return "nom" if previous_word(text, position) in _NOMINATIVE_BEFORE else "gen"


def _year_case(text: str, position: int) -> str:
    return "loc" if previous_word(text, position) in ("w", "we") else "gen"


def _roku(case: str) -> str:
    return {"gen": "roku", "loc": "roku", "nom": "rok"}[case]


def _abbreviation_end(text: str, end: int) -> str:
    """Keep a sentence end when the abbreviation "r." was also the last period of a sentence."""
    return "." if _SENTENCE_STARTS.match(text, end) else ""


def dates(text: str) -> str:
    def full(match: re.Match, with_r: bool) -> str | None:
        day, month, year = int(match["d"]), int(match["m"]), int(match["y"])
        if not _valid(day, month):
            return None
        words = f"{ordinal(day, _day_case(text, match.start()), 'm')} {MONTHS_GENITIVE[month]} {ordinal(year, 'gen', 'm')}"
        if with_r and match["r"]:
            words += " roku" + _abbreviation_end(text, match.end())
        return words

    def replace_full(match: re.Match) -> str:
        return full(match, with_r=True) or match.group()

    def replace_iso(match: re.Match) -> str:
        return full(match, with_r=False) or match.group()

    def replace_day_month(match: re.Match) -> str:
        day, month = int(match["d"]), int(match["m"])
        if not _valid(day, month):
            return match.group()
        return f"{ordinal(day, _day_case(text, match.start()), 'm')} {MONTHS_GENITIVE[month]}"

    def replace_day_month_name(match: re.Match) -> str:
        day = int(match["d"])
        if not 1 <= day <= 31:
            return match.group()
        return f"{ordinal(day, _day_case(text, match.start()), 'm')} {match['month']}"

    def replace_year(match: re.Match) -> str:
        case = _year_case(text, match.start())
        return f"{ordinal(int(match['y']), case, 'm')} {_roku(case)}{_abbreviation_end(text, match.end())}"

    for pattern, function in ((_FULL, replace_full), (_ISO, replace_iso), (_DAY_MONTH_NAME, replace_day_month_name),
                              (_YEAR, replace_year), (_DAY_MONTH, replace_day_month)):
        text = pattern.sub(function, text)
    return text
