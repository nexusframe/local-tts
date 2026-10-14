"""English voices: number ranges, units and currency in normalize_english().

espeak-ng en reads "15-20°C" as "fifteen dash twenty degrees C" (measured 2026-10-13).
"""

import pytest

from local_tts.normalizer import normalize_english


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("It will be 15-20°C today.", "It will be 15 to 20 degrees Celsius today."),
        ("It will be 15–20 °C today.", "It will be 15 to 20 degrees Celsius today."),
        ("Wait 10-15 minutes.", "Wait 10 to 15 minutes."),
        ("Read pages 10–12.", "Read pages 10 to 12."),
        ("The 2024-2025 season.", "The 2024 to 2025 season."),
        ("From -5 to 3°C.", "From -5 to 3 degrees Celsius."),
        ("It is 3.5-4.5 km.", "It is 3.5 to 4.5 kilometers."),
    ],
)
def test_number_range_is_read_with_to(text, expected):
    assert normalize_english(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Set the oven to 350°F.", "Set the oven to 350 degrees Fahrenheit."),
        ("It is -5°C outside.", "It is -5 degrees Celsius outside."),
        ("It is 1°C.", "It is 1 degree Celsius."),
        ("Turn it 90°.", "Turn it 90 degrees."),
    ],
)
def test_temperature_and_degrees(text, expected):
    assert normalize_english(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Walk 5 km.", "Walk 5 kilometers."),
        ("Walk 1 km.", "Walk 1 kilometer."),
        ("Add 5 kg and 200 g.", "Add 5 kilograms and 200 grams."),
        ("Take 500 mg.", "Take 500 milligrams."),
        ("Use 100 ml or 2 l.", "Use 100 milliliters or 2 liters."),
        ("It is 30 cm, 4 mm and 2 m.", "It is 30 centimeters, 4 millimeters and 2 meters."),
        ("Drive at 50 km/h.", "Drive at 50 kilometers per hour."),
        ("Wind of 10 m/s.", "Wind of 10 meters per second."),
        ("It used 3 kWh.", "It used 3 kilowatt hours."),
        ("It is 1.5 km.", "It is 1.5 kilometers."),
        ("Walk 5km.", "Walk 5 kilometers."),
    ],
)
def test_metric_units(text, expected):
    assert normalize_english(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("It costs $20.", "It costs 20 dollars."),
        ("It costs $1.", "It costs 1 dollar."),
        ("It costs €15 or £10.", "It costs 15 euros or 10 pounds."),
        ("It costs $5-10.", "It costs 5 to 10 dollars."),
    ],
)
def test_currency_symbol_goes_after_the_number(text, expected):
    assert normalize_english(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "The m and the g are letters.",  # A unit without a number does not change.
        "I am 5 and she is 7.",  # "am" is not a unit.
        "The 3G network.",
        "On 2026-10-13.",  # ISO date: out of scope, no "to".
        "Number: 5 5 5, 1 2 3, 4 5 6.",  # The documented phone number format.
    ],
)
def test_other_text_does_not_change(text):
    assert normalize_english(text) == text
