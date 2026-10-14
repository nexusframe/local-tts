"""English voices: number ranges, units and currency symbols to words.

espeak-ng en reads numbers itself, but it reads "15-20°C" as "fifteen dash twenty
degrees C" and "5 km" as "five K M" (measured 2026-10-13). The numbers stay digits.
"""

from __future__ import annotations

import re

_NUMBER = r"\d+(?:\.\d+)?"
# Units: (singular, plural). Longer symbols first, so that "km/h" wins before "km".
_UNITS = {
    "km/h": ("kilometer per hour", "kilometers per hour"),
    "m/s": ("meter per second", "meters per second"),
    "kWh": ("kilowatt hour", "kilowatt hours"),
    "km": ("kilometer", "kilometers"),
    "cm": ("centimeter", "centimeters"),
    "mm": ("millimeter", "millimeters"),
    "kg": ("kilogram", "kilograms"),
    "mg": ("milligram", "milligrams"),
    "ml": ("milliliter", "milliliters"),
    "m": ("meter", "meters"),
    "g": ("gram", "grams"),
    "l": ("liter", "liters"),
}
_CURRENCIES = {"$": ("dollar", "dollars"), "€": ("euro", "euros"), "£": ("pound", "pounds")}

# A range is two numbers with a hyphen or an en dash. Not a part of a longer chain
# such as the ISO date "2026-10-13".
_RANGE = re.compile(rf"(?<![\w.\-–])({_NUMBER})\s*[-–]\s*({_NUMBER})(?!\d|[-–]\d)")
_CURRENCY = re.compile(rf"([$€£])\s?({_NUMBER}(?: to {_NUMBER})?)(?![\d])")
_DEGREES = re.compile(rf"(-?{_NUMBER})\s*°\s*([CF](?![\w]))?")
_UNIT = re.compile(
    rf"(?<![\w.])(-?{_NUMBER})\s?({'|'.join(re.escape(u) for u in _UNITS)})(?![\w/])"
)


def _name(amount: str, names: tuple[str, str]) -> str:
    return names[0] if amount.lstrip("-") == "1" else names[1]


def _currency(match: re.Match) -> str:
    amount = match[2]
    return f"{amount} {_name(amount, _CURRENCIES[match[1]])}"


def _degrees(match: re.Match) -> str:
    scale = {"C": " Celsius", "F": " Fahrenheit", None: ""}[match[2]]
    return f"{match[1]} {_name(match[1], ('degree', 'degrees'))}{scale}"


def _unit(match: re.Match) -> str:
    return f"{match[1]} {_name(match[1], _UNITS[match[2]])}"


def english_units(text: str) -> str:
    # Ranges first, so that "$5-10" and "15-20°C" have the last number before the unit.
    text = _RANGE.sub(r"\1 to \2", text)
    text = _CURRENCY.sub(_currency, text)
    text = _DEGREES.sub(_degrees, text)
    return _UNIT.sub(_unit, text)
