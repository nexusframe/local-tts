# M2 results: Polish text normalizer

Date: 2026-10-09. Branch: `m2-normalizer`. Data: `tests/data/normalizer_cases.tsv`, `bench/results/m2/listening.json`. Research: `docs/m2-research.md`.

## 1. What M2 contains

The daemon normalizes each text before the sentence splitter (`local_tts/engine.py`). Steps, in order (`local_tts/normalizer/__init__.py`):

| Step | File | Examples |
|---|---|---|
| Cleanup | `cleanup.py` | markdown, URLs (domain only), emoji, lector tags `[pauza]` are removed and not read |
| Abbreviations | `abbreviations.py` | np., m.in., dr, hab., ul. (ulica/ulicy), godz. (godzina/godzinie), ok. (only before a number) |
| Dates | `dates.py` | 15.11.2026 r., 2026-11-15, 15.11, 1 maja, w 2026 r. |
| Times | `times.py` | o 14:30, od 8:00 do 16:00, 14:00-15:30 |
| Units, currency, percent | `units.py` | -3°C, 45 km/h, 5,99 zł, 3,5 mln zł, 30%, $20 |
| Numbers | `numerals.py`, `numbers.py`, `grammar.py` | case from the preposition, gender from the noun, decimals, półtora |
| Leftover digits | `numerals.py` | every digit that no rule changed is read as a number |
| Punctuation | `punctuation.py` | — to comma, ; to period, … to ..., i/lub, parentheses |

The numeral tables (`numbers.py`) have cardinals in 6 cases (nominative, genitive, dative, accusative, instrumental, locative) and 3 genders, and ordinals for the same cases and genders. The vocative is not necessary for numbers in this use.

## 2. Measured facts

| Metric | Target | Result | Status |
|---|---|---|---|
| Reviewed test cases, priority "must" | all pass | 102 of 102 | pass |
| Reviewed test cases, priority "nice" | — | 8 of 9 (not done: N19 „3. miejsce”) | — |
| Random texts (300 seeds): no exception, no digit in the output | all pass | 300 of 300 | pass |
| Normalization time, L1 (1022 characters) | < 5 ms | 0.6 ms | pass |
| Blind A/B listening, raw against normalized (5 pairs, 1 listener) | normalized better | normalized preferred in 5 of 5 pairs | pass |
| Daemon end to end („Wrócę za 5 min, ok. 14:30.”) | done event | done, 2.96 s of audio | pass |
| All unit tests | all pass | 433 passed, 1 expected failure (N19), 8 nice cases pass | pass |

The expected forms of the test cases were written by the developer and reviewed by a native Polish speaker. The M2, M3, M4 and M6 references come from the hand-written M0 corpus.

## 3. Observations

1. **Piper reads „trzy” like „czy”.** espeak-ng gives the same phonemes for both words: `t ʃ ɨ`. „trzech” and „czech” also have the same phonemes. The model gets the same input, so it cannot make a difference. The normalizer does not cause this: before M2, espeak-ng also read the digit 3 as „trzy”. This agrees with piper1-gpl issue #267, and it shows that the problem is not only in isolated words. The listener heard a weak „t” in „trzydzieści”.
2. The random test found 2 crash types and 3 output errors before the fix: `IndexError` for numbers ≥ 10^12, `ValueError` for the ordinal of 3000, digits left after dot decimals and invalid dates, „jeden i pół miliona” instead of „półtora miliona”, „zero i pół złotego” instead of „pięćdziesiąt groszy”.

## 4. Limits

1. Case selection uses the preposition before the number. For `z`, `w` and `po`, the ending of the next word selects the case. This is a heuristic for common phrases, not a full grammar.
2. Units store only nominative and genitive forms. Dative, instrumental and locative use the genitive: „przed 5 km” becomes „przed pięcioma kilometrów” (correct: „kilometrami”). These phrases are rare in assistant answers.
3. Ordinals for years from 3000 give the cardinal („trzy tysiące roku”).
4. Masculine personal nouns are not supported („dwóch lekarzy” becomes „dwa lekarzy”).
5. Roman numerals and phone numbers are not supported.
6. 1 listener and 5 pairs. The differences were large, so the result is clear, but small quality differences are not measured.

## 5. Recommendations

1. **„trzy”/„czy” (observation 1):** examine a phoneme-level fix in the Piper backend, for example a different phoneme sequence for „trz”. The model did not see such sequences in training, so a listening test is necessary. Do this as a separate task.
2. Add new test cases from real assistant answers when a client exists (`research.md` M2 asked for 100 examples from assistant logs; no logs exist yet).
