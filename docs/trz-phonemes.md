# "trz" phonemes for Piper

Date: 2026-10-09. Branch: `fix-trz-phonemes`. Data: `bench/results/trz/`.

## 1. Problem

The listener heard „trzy” as „czy” (M2 listening test). espeak-ng, the phonemizer of Piper, gives the same phonemes for the two spellings:

| Word | espeak-ng phonemes |
|---|---|
| trzy | `tʃˈɨ` |
| czy | `tʃɨ` |
| trzech | `tʃˈɛx` |
| czech | `tʃˈɛx` |

The model gets the same input for both words, so it cannot make a difference. This agrees with piper1-gpl issue #267.

## 2. Method

The daemon changes the phonemes of "trz" before synthesis. Piper accepts phonemes directly (`phonemes_to_ids`, `phoneme_ids_to_audio`). The model phoneme map contains `ʂ`, `ʰ` and `ː`, so 5 variants were possible:

| Variant | Phonemes for „trzy” |
|---|---|
| V0 default | `tʃɨ` |
| V1 long sz | `tʃʃɨ` |
| V2 retroflex | `tʂɨ` |
| V3 aspiration | `tʰʃɨ` |
| V4 long t | `tːʃɨ` |

Round 1: 1 sentence, all 5 variants, blind order. Round 2: 2 passages of about 12 s, variants V0, V1 and V3, 6 WAV files with blind names. 1 listener, native Polish speaker, scale 1-5.

## 3. Measured facts

„trz clear” score (1 = sounds like „cz”, 5 = clear „trz”):

| Variant | Round 1 | Round 2 P1 | Round 2 P2 | Naturalness (round 2) |
|---|---:|---:|---:|---|
| V0 default | 1 | 1 | 2 | 3, 3 |
| **V1 long sz** | 4 | 2 | **4** | 3, **4** |
| V2 retroflex | 1 | — | — | 1 (round 1) |
| V3 aspiration | **5** | 1 | 3 | 3, 3 |
| V4 long t | 2 | — | — | — |

- V1 was better than V0 in all 3 comparisons. Its naturalness was never lower than V0.
- V3 had the highest score in round 1 and a low score in round 2.
- In the texts of the test cases and the corpus, 23 sentences contain "trz". The correction was applied in 23 of 23.

## 4. Decision

Use V1 (`tʃʃ` for "trz"). It is on by default. The option `--no-trz-fix` turns it off.

Implementation: `local_tts/backends/phonemes.py` (`lengthen_trz`). The n-th `tʃ` in the phonemes belongs to the n-th "trz" or "cz" in the text. When the counts do not agree, the phonemes do not change. The Piper backend wraps `phonemize()` of its voice, so the audio processing of Piper stays the same.

## 5. Limits

1. 1 listener, 3 comparisons. The direction is the same in all 3, but the sample is small.
2. The naturalness criterion was not defined before round 2. Most scores are 3 („typical synthesizer”).
3. Only "trz" is corrected. "drz" (drzwi) and other spellings can have the same problem. They are not tested.
4. Tested with `zenski_wg_glos` only. The correction is also active for `gosia`.
