# "dz" phonemes and "ok"

Date: 2026-10-12. Branch: `fix-ok-dz`.

## 1. Problem

The user heard two errors in Polish speech (voices `zenski_wg_glos` and `jarvis_wg_glos`):

| Text | espeak-ng phonemes | The listener heard |
|---|---|---|
| Do widzenia. | `dɔ vidʑˈɛɲʲa.` | „widzienia” |
| Ok. | `ɔkˈɔwɔ.` | „około” |

- espeak-ng gives the same phoneme `dʑ` for "dz" (widzenia, dzwon, cudzy) and for "dzi"/"dź" (dzień, chodźmy). The model gets the same input for the two sounds. This is the same type of problem as "trz"/"cz" (see `trz-phonemes.md`).
- espeak-ng reads "ok" and "Ok" as the abbreviation "około". It reads "OK" as `ɔkˈɛj`.

## 2. Method

Listening test, 2026-10-12, 1 listener, native Polish speaker, both voices. Samples: 6 "ok"/"OK" sentences and 1 passage of 5 sentences with "dz", "dzi", "dź".

| Item | Variants | Pick |
|---|---|---|
| ok | A: espeak-ng; B: text "okej" | **B** |
| dz | V0: `dʑ` (espeak-ng); V1: `d` `z`; V2: `d` `z` `z` | **V1** |

## 3. Implementation

- `normalizer/abbreviations.py`: "ok", "Ok", "OK" become "okej" ("Okej" at the start of a sentence, because the splitter needs an uppercase letter after a sentence end). "ok." before a number stays "około".
- `backends/phonemes.py`, `fix_dz()`: the n-th `dʑ` belongs to the n-th "dz", "dzi" or "dź" in the text. For "dz", `dʑ` becomes `d` `z`. "dż" (`dʒ`) does not count. `PiperBackend` applies it after `lengthen_trz()` (option `fix_dz`, on by default).

## 4. Limits

- If the counts do not agree, the sentence keeps the espeak-ng phonemes. Known cases: "dz" at the end of a word before a pause or a voiceless sound ("wódz" is `vuts`), and "ć" before a voiced sound ("być dobrym" has `dʑ`).
- "dz" across a morpheme boundary ("odzew" = od-zew) also gets `d` `z`. This is correct for "odzew". "podzielić" is spelled "dzi", so it keeps `dʑ`; correct is `d` `ʑ`, so the difference is small.

## 5. Tests

`tests/test_phonemes.py` (fix_dz), `tests/test_piper_en.py` (real model, next to an English span), `tests/data/normalizer_cases.tsv` A13–A16.
