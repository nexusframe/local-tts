"""Polish numerals in words, with grammatical case and gender.

Cases: nom, gen, dat, acc, ins, loc.
Genders: m (masculine, not personal), f (feminine), n (neuter).
"""

from __future__ import annotations

CASES = ("nom", "gen", "dat", "acc", "ins", "loc")

# 0-19 for cases other than nominative and accusative. Index = number.
_SMALL = {
    "nom": ["zero", "jeden", "dwa", "trzy", "cztery", "pięć", "sześć", "siedem", "osiem", "dziewięć",
            "dziesięć", "jedenaście", "dwanaście", "trzynaście", "czternaście", "piętnaście",
            "szesnaście", "siedemnaście", "osiemnaście", "dziewiętnaście"],
    "gen": ["zera", "jednego", "dwóch", "trzech", "czterech", "pięciu", "sześciu", "siedmiu", "ośmiu", "dziewięciu",
            "dziesięciu", "jedenastu", "dwunastu", "trzynastu", "czternastu", "piętnastu",
            "szesnastu", "siedemnastu", "osiemnastu", "dziewiętnastu"],
    "dat": ["zeru", "jednemu", "dwóm", "trzem", "czterem", "pięciu", "sześciu", "siedmiu", "ośmiu", "dziewięciu",
            "dziesięciu", "jedenastu", "dwunastu", "trzynastu", "czternastu", "piętnastu",
            "szesnastu", "siedemnastu", "osiemnastu", "dziewiętnastu"],
    "ins": ["zerem", "jednym", "dwoma", "trzema", "czterema", "pięcioma", "sześcioma", "siedmioma", "ośmioma", "dziewięcioma",
            "dziesięcioma", "jedenastoma", "dwunastoma", "trzynastoma", "czternastoma", "piętnastoma",
            "szesnastoma", "siedemnastoma", "osiemnastoma", "dziewiętnastoma"],
    "loc": ["zerze", "jednym", "dwóch", "trzech", "czterech", "pięciu", "sześciu", "siedmiu", "ośmiu", "dziewięciu",
            "dziesięciu", "jedenastu", "dwunastu", "trzynastu", "czternastu", "piętnastu",
            "szesnastu", "siedemnastu", "osiemnastu", "dziewiętnastu"],
}
_SMALL["acc"] = _SMALL["nom"]

# Feminine and neuter forms of 1 and 2 where they differ from masculine.
_ONE = {
    "f": {"nom": "jedna", "gen": "jednej", "dat": "jednej", "acc": "jedną", "ins": "jedną", "loc": "jednej"},
    "n": {"nom": "jedno", "acc": "jedno"},
}
_TWO_F = {"nom": "dwie", "acc": "dwie", "ins": "dwiema"}

# Tens 20-90. Index = tens digit.
_TENS = {
    "nom": [None, None, "dwadzieścia", "trzydzieści", "czterdzieści", "pięćdziesiąt", "sześćdziesiąt",
            "siedemdziesiąt", "osiemdziesiąt", "dziewięćdziesiąt"],
    "gen": [None, None, "dwudziestu", "trzydziestu", "czterdziestu", "pięćdziesięciu", "sześćdziesięciu",
            "siedemdziesięciu", "osiemdziesięciu", "dziewięćdziesięciu"],
    "ins": [None, None, "dwudziestoma", "trzydziestoma", "czterdziestoma", "pięćdziesięcioma", "sześćdziesięcioma",
            "siedemdziesięcioma", "osiemdziesięcioma", "dziewięćdziesięcioma"],
}
_TENS["acc"] = _TENS["nom"]
_TENS["dat"] = _TENS["loc"] = _TENS["gen"]

# Hundreds 100-900. Index = hundreds digit.
_HUNDREDS = {
    "nom": [None, "sto", "dwieście", "trzysta", "czterysta", "pięćset", "sześćset", "siedemset", "osiemset", "dziewięćset"],
    "gen": [None, "stu", "dwustu", "trzystu", "czterystu", "pięciuset", "sześciuset", "siedmiuset", "ośmiuset", "dziewięciuset"],
    "ins": [None, "stu", "dwustoma", "trzystoma", "czterystoma", "pięciuset", "sześciuset", "siedmiuset", "ośmiuset", "dziewięciuset"],
}
_HUNDREDS["acc"] = _HUNDREDS["nom"]
_HUNDREDS["dat"] = _HUNDREDS["loc"] = _HUNDREDS["gen"]

# Scale nouns: singular forms by case, then plural forms by case.
# Plural "nom" is the form after 2-4; after 5+ the genitive plural is used.
_SCALES = [
    (10**9, {"nom": "miliard", "gen": "miliarda", "dat": "miliardowi", "acc": "miliard", "ins": "miliardem", "loc": "miliardzie"},
            {"nom": "miliardy", "gen": "miliardów", "dat": "miliardom", "acc": "miliardy", "ins": "miliardami", "loc": "miliardach"}),
    (10**6, {"nom": "milion", "gen": "miliona", "dat": "milionowi", "acc": "milion", "ins": "milionem", "loc": "milionie"},
            {"nom": "miliony", "gen": "milionów", "dat": "milionom", "acc": "miliony", "ins": "milionami", "loc": "milionach"}),
    (10**3, {"nom": "tysiąc", "gen": "tysiąca", "dat": "tysiącowi", "acc": "tysiąc", "ins": "tysiącem", "loc": "tysiącu"},
            {"nom": "tysiące", "gen": "tysięcy", "dat": "tysiącom", "acc": "tysiące", "ins": "tysiącami", "loc": "tysiącach"}),
]


def plural_form(n: int) -> str:
    """Return "one", "few" or "many": the noun form that agrees with n in the nominative."""
    if n == 1:
        return "one"
    if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
        return "few"
    return "many"


def scale_word(count: int, case: str, scale: int) -> str:
    """The form of tysiąc/milion/miliard after `count` in `case`."""
    for value, singular, plural in _SCALES:
        if value == scale:
            if count == 1:
                return singular[case]
            if case in ("nom", "acc"):
                return plural["nom"] if plural_form(count) == "few" else plural["gen"]
            return plural[case]
    raise ValueError(f"unknown scale {scale}")


def _below_1000(n: int, case: str, gender: str, last_group: bool) -> list[str]:
    words = []
    hundreds, rest = divmod(n, 100)
    if hundreds:
        words.append(_HUNDREDS[case][hundreds])
    if rest >= 20:
        tens, units = divmod(rest, 10)
        words.append(_TENS[case][tens])
        if units == 1:
            # In compound numbers "jeden" does not change: dwudziestu jeden.
            words.append("jeden")
        elif units:
            words.append(_unit(units, case, gender if last_group else "m"))
    elif rest:
        words.append(_unit(rest, case, gender if last_group else "m") if (hundreds == 0 or rest != 1) else "jeden")
    return words


def _unit(n: int, case: str, gender: str) -> str:
    if n == 1 and gender in _ONE and case in _ONE[gender]:
        return _ONE[gender][case]
    if n == 2 and gender == "f" and case in _TWO_F:
        return _TWO_F[case]
    return _SMALL[case][n]


def cardinal(n: int, case: str = "nom", gender: str = "m") -> str:
    if case not in CASES:
        raise ValueError(f"unknown case {case!r}")
    if n < 0:
        return "minus " + cardinal(-n, case, gender)
    if n == 0:
        return _SMALL[case][0]
    if n >= 10**12:
        # Too large for the scale words: read the digits one by one.
        return " ".join(_SMALL["nom"][int(d)] for d in str(n))
    words: list[str] = []
    rest = n
    for scale, _, _ in _SCALES:
        count, rest = divmod(rest, scale)
        if count:
            if count != 1:
                words.extend(_below_1000(count, case, "m", last_group=False))
            words.append(scale_word(count, case, scale))
    if rest:
        words.extend(_below_1000(rest, case, gender, last_group=True))
    return " ".join(words)


# Ordinal stems. Index = number. The stem class gives the ending set.
_ORD_UNITS = ["", "pierwsz", "drug", "trzec", "czwart", "piąt", "szóst", "siódm", "ósm", "dziewiąt",
              "dziesiąt", "jedenast", "dwunast", "trzynast", "czternast", "piętnast",
              "szesnast", "siedemnast", "osiemnast", "dziewiętnast"]
_ORD_TENS = [None, None, "dwudziest", "trzydziest", "czterdziest", "pięćdziesiąt", "sześćdziesiąt",
             "siedemdziesiąt", "osiemdziesiąt", "dziewięćdziesiąt"]
_ORD_HUNDREDS = [None, "setn", "dwusetn", "trzysetn", "czterysetn", "pięćsetn", "sześćsetn", "siedemsetn",
                 "osiemsetn", "dziewięćsetn"]

_HARD_ENDINGS = {
    "m": {"nom": "y", "gen": "ego", "dat": "emu", "acc": "y", "ins": "ym", "loc": "ym"},
    "f": {"nom": "a", "gen": "ej", "dat": "ej", "acc": "ą", "ins": "ą", "loc": "ej"},
    "n": {"nom": "e", "gen": "ego", "dat": "emu", "acc": "e", "ins": "ym", "loc": "ym"},
}


def _ordinal_word(stem: str, case: str, gender: str) -> str:
    ending = _HARD_ENDINGS[gender][case]
    if stem == "trzec":
        # Soft stem: i before every ending (trzeci, trzecia, trzeciego).
        return stem + "i" + ending.replace("y", "", 1) if ending.startswith("y") else stem + "i" + ending
    if stem == "drug":
        # After g: i instead of y, and i before e (drugi, drugiego, druga).
        if ending.startswith("y"):
            return stem + "i" + ending[1:]
        if ending.startswith("e"):
            return stem + "i" + ending
    return stem + ending


def ordinal(n: int, case: str = "nom", gender: str = "m") -> str:
    """Ordinal numeral. Only the tens and units change; higher parts stay cardinal (dwa tysiące dwudziesty).

    For numbers without a supported ordinal form, the cardinal is returned.
    """
    if n <= 0 or n >= 10**12:
        return cardinal(n)
    high, low = divmod(n, 100)
    words = []
    if low == 0:
        thousands, hundreds = divmod(high, 10)
        if hundreds:
            if thousands:
                words.append(cardinal(thousands * 1000))
            words.append(_ordinal_word(_ORD_HUNDREDS[hundreds], case, gender))
            return " ".join(words)
        if thousands == 1:
            return _ordinal_word("tysięczn", case, gender)
        if thousands == 2:
            return _ordinal_word("dwutysięczn", case, gender)
        return cardinal(n)
    if high:
        words.append(cardinal(high * 100))
    if low < 20:
        words.append(_ordinal_word(_ORD_UNITS[low], case, gender))
    else:
        tens, units = divmod(low, 10)
        words.append(_ordinal_word(_ORD_TENS[tens], case, gender))
        if units:
            words.append(_ordinal_word(_ORD_UNITS[units], case, gender))
    return " ".join(words)
