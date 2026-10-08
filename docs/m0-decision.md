# M0 decision: TTS backend for the Polish assistant

Status: **decided (provisional)**. Primary: Piper `pl_PL-zenski_wg_glos-medium`. Pocket PL is not primary, because the listening test did not show that it is better than Piper `wg_glos` (see [section 8](#8-listening-test-and-decision)).

Date of the benchmark: 2026-10-08. Data: `bench/results/report.md` and `bench/results/raw/`.

## 1. Scope and method

The benchmark compares 3 backends on one machine with the same 11 texts:

- Pocket TTS 3.3.0 with `shefowl/pocket-tts-polish-6l`: fp32, int8 with `torch.ao`, int8 with `torchao`.
- Piper 1.8.0: `pl_PL-zenski_wg_glos-medium`, `pl_PL-gosia-medium`, `pl_PL-bass-high`.
- Supertonic 3: voice styles F1 and M1, `lang=pl`.

Machine: Intel Core i5-8365U (4 cores, 8 threads, AVX2, no AVX-512), 15 GiB RAM, Ubuntu 24.04, AC power, governor `powersave` with EPP `performance`. Other processes used a median of 0.02-0.15 CPU cores during the measured runs.

The method is in `bench/README.md`. The full run had 0 failed runs.

## 2. Measured facts

All values are for the best thread configuration of each target. RTF is the median of 110 runs (11 texts, 10 runs each). TTFA is for S1 ("Jasne, już sprawdzam.").

| Target | Best config | RTF | TTFA S1 | Cold start to first audio | Peak RSS | Streaming |
|---|---|---:|---:|---:|---:|---|
| Piper `zenski_wg_glos-medium` | 4 threads | 0.055 | 62 ms | 1.58 s | 419 MB | per sentence |
| Piper `gosia-medium` | 4 threads | 0.055 | 96 ms | 1.45 s | 566 MB | per sentence |
| Piper `bass-high` | 4 threads | 0.308 | 636 ms | 2.17 s | 492 MB | per sentence |
| Pocket PL int8 (`torch.ao`) | 1 thread | 0.212 | 52 ms | 5.88 s | 1204 MB | inside a sentence, 80 ms chunks |
| Pocket PL fp32 | 1 thread | 0.329 | 106 ms | 5.22 s | 1201 MB | inside a sentence, 80 ms chunks |
| Pocket PL int8 (`torchao`) | 4 threads | 0.718 | 273 ms | 7.33 s | 1206 MB | inside a sentence, 80 ms chunks |
| Supertonic 3 F1 | 2 threads | 0.302 | 762 ms | 1.65 s | 721 MB | no (one block per text chunk) |
| Supertonic 3 M1 | 2 threads | 0.298 | 825 ms | 1.68 s | 721 MB | no (one block per text chunk) |

Streaming and cancel (L1, about 60-80 s of audio):

| Target | TTFA L1 | Longest wait between chunks | Underrun in playback simulation | Cancel latency |
|---|---:|---:|---|---:|
| Piper `zenski_wg_glos` | 45 ms | 0.56 s | 0 of 3 runs | 0 ms (between sentences) |
| Piper `bass-high` | 292 ms | 3.09 s | **3 of 3 runs** (worst 0.18 s) | 0 ms (between sentences) |
| Pocket int8 (`torch.ao`) | 102 ms | 0.11 s | 0 of 3 runs | 31 ms |
| Supertonic F1, official helper | 5077 ms | 6.12 s | 0 of 3 runs | 0 ms (between chunks) |
| Supertonic F1, split at sentence ends | 722 ms | 3.28 s | 0 of 3 runs | 0 ms (between sentences) |

Stability over 100 consecutive syntheses of M1 and M8:

- No target had errors or warnings during synthesis.
- Piper, Supertonic, Pocket fp32 and Pocket int8 (`torch.ao`): RSS changed by less than 3 MB per 100 runs. Time did not drift.
- Pocket int8 (`torchao`): RSS increased by 111 MB per 100 runs for M1 and by 41 MB per 100 runs for M8.

Thread scaling:

- Pocket is fastest with 1 intra-op thread. More threads make it slower (int8 `torch.ao`: RTF 0.212 with 1 thread, 0.282 with 8 threads). Pocket uses 1.7-1.9 CPU cores with 1 intra-op thread, because generation and audio decoding run in two threads.
- Piper is fastest with 4 threads on 4 physical cores. 8 threads (with hyper-threads) are slower.
- Supertonic is fastest with 2 threads.

## 3. Observations

These need confirmation by listening or by an ASR.

1. **Pocket and Supertonic probably skip digits and symbols.** For M2 ("-3°C ... 45 km/h"), the raw text gave 4.16 s of audio with Pocket int8 and 5.23 s with Supertonic F1. The normalized text gave 8.24 s and 8.41 s. Piper gave 5.15 s and 6.36 s, so espeak-ng reads digits in some form. A Polish text normalizer is necessary for all backends. It is critical for Pocket and Supertonic.
2. **Pocket audio length varies between runs.** For M3 (date and time, raw), the duration was 5.04-9.44 s over 10 runs with the same text. 4-5 of 10 runs had a speech rate below 1.0 word/s. This can be long pauses, repeated words or extra audio. Pocket uses random sampling, so some variation is normal. Piper and Supertonic vary by less than 10%.
3. **Pocket memory is mostly PyTorch, not weights.** int8 does not decrease peak RSS: 1204 MB with int8 and 1201 MB with fp32. Import of `pocket_tts` and torch takes about 2.9 s of the cold start.
4. **Piper RSS increases with long sentences.** After load, Piper uses 136-192 MB. After L1, RSS stays at 360-520 MB. The probable cause is the ONNX Runtime memory arena, which keeps memory after the longest input.
5. **The machine became hot.** The CPU package temperature was 50 °C at the start and 87 °C at the end. Targets that ran later (Supertonic, Pocket int8 `torchao`) can be slower because of thermal throttling. Pocket fp32 and int8 (`torch.ao`) ran first. The order of the runs can change the result by an unknown amount.

## 4. Differences from research.md

| Claim in research.md | Source label | Measured on this machine |
|---|---|---|
| Pocket PL RTF 0.21 (fp32), 0.11 (int8) | [A] | 0.329 (fp32), 0.212 (int8 `torch.ao`), 0.718 (int8 `torchao`) |
| Pocket int8 is 1.8x faster than fp32 | [A] | 1.55x with `torch.ao`. With `torchao` (the path of `pocket-tts[quantize]`), int8 is 2.2x **slower** than fp32 |
| Pocket model load 0.6-0.8 s | [A] | 2.2-2.9 s load, plus 2.9 s import; 5.2-5.9 s from process start to first audio |
| Pocket 125 MB (int8) / 341 MB (fp32) in RAM | [A] | These are weights only. Process peak RSS is about 1.2 GB for both |
| Pocket streaming, about 200 ms to first chunk | [A] | Confirmed: 52-106 ms to the first 80 ms chunk, no underrun, cancel in about 30 ms |
| "2 cores are sufficient" for Pocket | [A] | Confirmed: 1 intra-op thread on 2 CPUs is the best configuration |
| Piper RTF about 0.15-0.2 | [S] | 0.055 for medium voices; 0.308 for `bass-high` |
| Piper `high` is about 2x slower than `medium` | [W] | 5.6x slower; TTFA S1 636 ms is above the 500 ms limit of research.md |
| Piper process about 0.15-0.3 GB | [W] | 0.14-0.19 GB after load; 0.42-0.57 GB peak |
| `zenski_wg_glos` is one of the Piper voices | [Z] | It is not in the official `rhasspy/piper-voices` catalog. Source: `WitoldG/polish_piper_models` (MIT) |
| Supertonic RTF 0.172 | [A] | 0.298-0.302 |
| Supertonic peak memory 2.0 GiB | [A] | 0.72 GB |
| Supertonic TTFA about 0.3-0.8 s for a short sentence | [W] | 762-825 ms |
| Supertonic has no streaming | [W] | Confirmed. The official helper gives the first audio of L1 after 5.1 s. Sentence splitting in the daemon decreases this to 0.72 s |

## 5. Uncertainties

1. **Polish quality is not measured.** No local ASR is installed, and no person has listened to the samples yet. This is the most important open item.
2. **One machine only.** The results are for an i5-8365U with AVX2. On CPUs with AVX-512 VNNI or on ARM, the `torchao` int8 path can be faster.
3. **The fast int8 path of Pocket uses a deprecated API.** PyTorch 2.14 shows "torch.ao.quantization is deprecated". A future PyTorch release can remove it. Then only fp32 (RTF 0.329) or the slow `torchao` path stays available.
4. **One Pocket voice.** All Pocket results use `reference.wav` from the model repository. The model card states that the reference clip changes WER by up to 3x.
5. **Possible memory leak in Pocket int8 (`torchao`).** 100 runs are not sufficient to show if the RSS increase stops. This target is not recommended, so the effect is not important for the decision.
6. **Thermal state and run order** (see observation 5).
7. **Cold start with a warm file cache.** The first start after a reboot is slower. The benchmark cannot drop caches without root.

## 6. Recommendation

The decision rule of the project is: use Pocket as primary only if its Polish quality is clearly better than Piper `wg_glos` and it is inside the CPU budget. Otherwise, use Piper.

What the benchmark shows for this rule:

- **CPU budget.** Both candidates are inside the limits of research.md (RTF ≤ 0.5, TTFA ≤ 500 ms). Pocket int8 (`torch.ao`): RTF 0.212, TTFA 52 ms. Piper `wg_glos`: RTF 0.055, TTFA 62 ms. Speed does not decide between them.
- **Quality.** It is not measured. So the condition "clearly better" is not satisfied yet.

Recommendation:

1. **Do not select the primary backend yet.** Do the blind listening test first. It takes about 30-40 minutes for one listener: `python3 bench/listening_kit.py`, then rate `bench/results/listening/ratings.csv`. Then run `python3 bench/listening_kit.py --score`.
2. **If Pocket is clearly better in the listening test:** primary = Pocket PL int8 with `torch.ao`, 1 intra-op thread. Pin `torch==2.14.1`. Fallback = Piper `zenski_wg_glos-medium`.
3. **If Pocket is not clearly better:** primary = Piper `zenski_wg_glos-medium` (4 threads), or `gosia-medium` if listeners prefer it. Pocket stays an option for a cloned voice.
4. **Fallback in both cases: Piper.** It starts in about 1.5 s, has no PyTorch dependency, and was stable in all tests.
5. **Do not use** Piper `bass-high` on this class of CPU (TTFA 636 ms, playback underruns on long text). **Do not use** Pocket int8 with `torchao` on AVX2 CPUs (slower than fp32, RSS increase).
6. **Supertonic 3 is the third option and has no advantage here.** It is slower to the first audio (762 ms) than Pocket and Piper. It cannot stream inside a sentence. The repository is archived, and the weights use the OpenRAIL-M license. Keep it out of M1.

## 7. Next steps

1. Run the blind listening test (see section 6). This closes M0.
2. Optional: install a local ASR to measure WER/CER automatically. The recommended choice is `parakeet-tdt-0.6b-v3` int8 through `onnx-asr`. Its download is about 640 MiB. Do this only after approval.

### Proposal for M1

M1 does not depend on the open quality decision. Piper is the fallback in all cases, so it is needed in every case.

1. Daemon skeleton: one Python process, a backend interface `synthesize_stream(text) -> Iterator[PCM]` with `cancel()`, model kept in memory.
2. Piper backend (`zenski_wg_glos-medium`, 4 threads), sentence-level streaming.
3. Local playback through PipeWire and cancel (barge-in).
4. A minimal sentence splitter, so the first sentence is synthesized first.
5. The benchmark adapters in `bench/backends/` show the API calls. Do not import them into the daemon. They are measurement code.

The Polish normalizer (research.md M2) becomes more important: observation 1 shows that Pocket and Supertonic skip digits without it. If the listening test selects Pocket, add the Pocket backend in M3 as research.md describes. Use the measured settings: int8 with `torch.ao`, 1 intra-op thread.

## 8. Listening test and decision

Date: 2026-10-08. Data: `bench/results/listening-test/` (ratings, key, scores).

Method: blind test with random file names. 6 targets, 10 texts each (normalized form where it exists, else raw). 1 listener, native Polish speaker, not a speech specialist. Scale 1-5. The listener started from 3 in every field and changed only what was clearly better or worse. 21 of 60 files stayed at 3 in all fields.

| Target | Naturalness | Pronunciation | Prosody | Mean of all 30 scores |
|---|---:|---:|---:|---:|
| Piper `zenski_wg_glos-medium` | **3.50** | **3.10** | 3.20 | **3.27** |
| Supertonic 3 M1 | 3.00 | 2.90 | **3.60** | 3.17 |
| Supertonic 3 F1 | 3.00 | 2.90 | 2.90 | 2.93 |
| Piper `gosia-medium` | 3.00 | 2.30 | 2.90 | 2.73 |
| Pocket PL int8 (`torch.ao`) | 2.40 | 3.00 | 2.80 | 2.72 |
| Pocket PL fp32 | 2.20 | 2.90 | 2.70 | 2.59 |

Listener comments: Pocket fp32 read "Brzezińska" correctly. Supertonic M1 read it incorrectly. Piper `gosia` read "trzech" as "czech" in the normalized M2 text. This matches the numeral problem of piper1-gpl issue #267.

### Measured facts

- Piper `zenski_wg_glos` has the highest naturalness and the highest mean score.
- Pocket PL has the lowest naturalness of all targets (2.20-2.40).
- No target has a mean above 3.3. The differences are 0.1-0.7 points.

### Limits of this test

- 1 listener and 10 files per target. One file changes a mean by 0.1-0.2. The test can show a clear preference, but it cannot show small differences.
- Pocket used only one reference voice. A different reference clip can sound more natural.

### Decision

The project rule is: Pocket is primary only if it is clearly better than Piper `wg_glos`. The test shows the opposite direction. So:

1. **Primary: Piper `pl_PL-zenski_wg_glos-medium`**, 4 intra-op threads, sentence-level streaming.
2. **Fallback: Piper `pl_PL-gosia-medium`.** Same engine and same code path, so it protects only against a problem in one model file. A fallback with a different engine is not necessary for M1, because Piper had 0 errors in all tests.
3. **Pocket PL is not in M1.** It stays an option for a cloned voice later (M6 in research.md). Its listening score can change with a better reference clip.
4. **Supertonic 3 is not in M1.** M1 voice had good prosody (3.60), but TTFA is 800 ms, it cannot stream inside a sentence, and the project is archived.

Revisit this decision if a test with more listeners or an ASR evaluation gives a different result.
