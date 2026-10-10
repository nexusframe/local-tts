# Voices

## How to select a voice

| Where | How |
|---|---|
| Default voice set | `DEFAULT_VOICES` in `local_tts/config.py` |
| Daemon start | `--voice NAME=MODEL`, one time for each voice. The first voice is the default voice. |
| One request | the `voice` field of `speak` and `begin`. Client: `python -m local_tts.client speak --voice en_male "Hello."` |

`MODEL` is a directory name in `bench/models/piper/` (`--models-dir` changes the directory).
Download the models with `python3 bench/fetch_models.py --backend piper`.

Example: a Polish male voice and English voices:

```
.venv/bin/python -m local_tts --first-words 2 \
  --voice meski=pl_PL-meski_wg_glos-medium \
  --voice en_male=en_GB-alan-medium \
  --voice en_female=en_GB-cori-medium
```

Each loaded voice adds about 140 MB RSS after load. The prototype target is daemon RSS ≤ 1.5 GB.

## Voice language

The daemon gets the language of a voice from the espeak-ng voice in the model config (`pl`, `en-us`, `en-gb-x-rp`).
`status` shows it in `languages`.

| | Polish voice (`pl`) | English voice (`en`) |
|---|---|---|
| Normalizer | Polish rules: numbers, dates, times, units, abbreviations | markup only: Markdown, emoji, `[...]` tags, `<en>` tags. espeak-ng reads numbers and times. |
| `<en>` tags and `commit'a` | English phonemes with the Polish phoneme map (see `docs/en-tags.md`) | tags are removed, all text is English |
| "trz" fix | yes | no |

The assistant selects the voice. For a full English answer, send it with an English voice.
A Polish voice does not read full English sentences well (listening test, 2026-10-10).

## Measured voices

Piper 1.8.0, i5-8365U, 4 threads (`t4c4`), Polish benchmark corpus. Full data: `bench/results/report.md`.
For the English voices, the corpus is Polish text, so only speed and memory are comparable.
F0 is the median pitch of the listening samples (female voices 149–221 Hz, male voices 93–133 Hz).

| Model | Gender (F0) | Mean RTF | TTFA S1 | Peak RSS | Dataset license |
|---|---|---:|---:|---:|---|
| `pl_PL-zenski_wg_glos-medium` | female (170 Hz) | 0.055 | 62 ms | 419 MB | MIT (model repo) |
| `pl_PL-gosia-medium` | female (206 Hz) | 0.055 | 96 ms | 566 MB | see MODEL_CARD |
| `pl_PL-meski_wg_glos-medium` | male (118 Hz) | 0.060 | 65 ms | 548 MB | MIT (model repo) |
| **`pl_PL-jarvis_wg_glos-medium`** ✓ | male (113 Hz) | 0.062 | 70 ms | 590 MB | MIT (model repo) |
| `pl_PL-darkman-medium` | male (114 Hz) | 0.062 | 110 ms | 602 MB | CC0 |
| `pl_PL-mc_speech-medium` | male (111 Hz) | 0.068 | 155 ms | 431 MB | CC0 |
| **`en_US-lessac-medium`** ✓ | female (199 Hz) | 0.057 | 106 ms | 709 MB | Blizzard 2013 (non-commercial) |
| `en_US-amy-medium` | female (193 Hz) | 0.088 * | 105 ms | 708 MB | Mycroft, see URL |
| `en_US-kristin-medium` | female (149 Hz) | 0.067 * | 103 ms | 602 MB | public domain |
| **`en_US-hfc_female-medium`** ✓ | female (221 Hz) | 0.060 | 91 ms | 486 MB | CC BY-NC-SA 4.0 |
| **`en_GB-cori-medium`** ✓ | female (214 Hz) | 0.059 | 108 ms | 485 MB | public domain |
| `en_US-joe-medium` | male (93 Hz) | 0.070 * | 113 ms | 613 MB | CC0 |
| `en_US-john-medium` | male (114 Hz) | 0.071 * | 155 ms | 613 MB | public domain |
| **`en_US-bryce-medium`** ✓ | male (133 Hz) | 0.059 | 108 ms | 705 MB | public domain |
| **`en_US-hfc_male-medium`** ✓ | male (120 Hz) | 0.061 | 102 ms | 460 MB | CC BY-NC-SA 4.0 |
| `en_GB-alan-medium` | male (96 Hz) | 0.059 | 97 ms | 746 MB | Mycroft, see URL |

✓ Selected in the listening test (2026-10-10): Polish male `jarvis_wg_glos`; English female `lessac`, `hfc_female`, `cori`; English male `bryce`, `hfc_male`.
The Polish male voices `darkman` and `mc_speech` are kept for other roles.
The voices `lessac`, `hfc_female` and `hfc_male` have non-commercial dataset licenses.

\* Other processes used 0.6–0.9 CPU cores (median) during these runs. All medium models have the same
network size, so the real RTF is probably near 0.06. This is an assumption, not a measurement.

`pl_PL-bass-high` (male) is not recommended: RTF 0.309, TTFA 636 ms, playback underruns (see `docs/m0-decision.md`).

Listening samples (not in git): `scripts/listen_male_voices.py` (Polish male voices), `scripts/listen_en_voices.py` (English voices).

## Limits

- espeak-ng en reads some amounts in a wrong order: `$25` → "dollar twenty five".
- The splitter knows Polish abbreviations and the English titles `Mr.`, `Mrs.`, `Ms.`, `vs.` only.
- The daemon does not select the language itself. The assistant selects the voice.
