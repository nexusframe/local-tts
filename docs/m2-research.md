# M2 research: existing Polish text normalizers

Date: 2026-10-08. Method: GitHub repository and code search (`gh search repos`, `gh search code`), README and source reading, and a local test of `num2words` in a separate venv.

## Measured facts

| Candidate | Status | Polish result |
|---|---|---|
| `num2words` 0.5.14 (`savoirfairelinux/num2words`, LGPL-2.1, 970 stars, last release 2024-12-16) | Tested locally | Cardinals in nominative only: `3` → „trzy”, `2026` → „dwa tysiące dwadzieścia sześć”. Ordinals in nominative masculine only: `15` → „piętnasty”. `to="year"` gives the cardinal. **`-3` raises `ValueError`.** No grammatical case parameter. |
| `NVIDIA/NeMo-text-processing` (Apache-2.0, 511 stars) | Directory list read | No Polish text normalization (no `pl` directory). |
| `DrMikeMaik/polish-text-normalizer` (MIT, 0 stars, 11 commits, last push 2026-03-09) | README and source read | Has modules for abbreviations (80+), currency, dates, time, Roman numerals, URLs. Cardinals in nominative only; ordinal table only for 1-31. Its own README examples have case errors: „około dwa dolary” (correct: „około dwóch dolarów”), „od osiem do szesnaście”. Requires Python 3.10-3.11. |
| `NeonFeline/polish-whisper-normalizer` (MIT, 2 stars) | README read | Opposite direction: it normalizes ASR transcripts for WER (words to digits), with Morfeusz2. Not a TTS normalizer. |
| `scrapinghub/number-parser` (BSD-3-Clause, 131 stars, last push 2026-10-03) | Found by code search | Opposite direction: it parses Polish number words (many inflected forms) to numbers. |

Code search for inflected forms („dwudziestoma”, „czterdziestu”, „czternastej”) found no other TTS normalizer with case inflection.

## Observations

1. No maintained Polish TTS normalizer with case inflection was found.
2. `num2words` covers only the nominative. It also adds an LGPL dependency and has a bug for negative numbers.
3. `number-parser` can be a test oracle for number values: the normalizer output parsed back must give the same number. It cannot check the grammatical case.
4. `polish-whisper-normalizer` can be useful later for ASR-based WER evaluation (M0 open item), not for M2.

## Decision (proposal)

1. Write our own Polish numeral module with inflection tables: cardinals in 7 cases, ordinals for case and gender. No `num2words` dependency.
2. Use the abbreviation list of `polish-text-normalizer` (MIT) as a reference for the abbreviation table. Write the table ourselves and check each entry.
3. Optional: `number-parser` as a test-only dependency for a round-trip value check. Decide in step 3.
