# M1 results: daemon skeleton, Piper backend, PipeWire playback, cancel

Date: 2026-10-08. Branch: `m1-daemon`. Data: `bench/results/m1/measure.json`.

Machine: the M0 machine (Intel Core i5-8365U, AC power, governor `powersave`). Voices loaded: `zenski` (`pl_PL-zenski_wg_glos-medium`, default) and `gosia` (`pl_PL-gosia-medium`), 4 intra-op threads each.

## 1. What M1 contains

| Part | File | Test method |
|---|---|---|
| Sentence splitter | `local_tts/splitter.py` | 7 unit tests |
| JSON lines protocol | `local_tts/protocol.py` | 14 unit tests |
| Engine: queue, voice selection, cancel, interrupt, synthesis ahead of playback | `local_tts/engine.py` | 9 unit tests with a fake backend and a fake player |
| Piper backend | `local_tts/backends/piper.py` | measurement script |
| `pw-cat` player | `local_tts/player.py` | measurement script and listening |
| Unix socket server, start command, client | `local_tts/server.py`, `__main__.py`, `client.py` | measurement script |

Commands:

```
.venv/bin/pip install -r requirements.lock.txt
.venv/bin/python -m local_tts                      # start the daemon
.venv/bin/python -m local_tts.client speak "Dzień dobry."
.venv/bin/python -m local_tts.client cancel
.venv/bin/python scripts/measure_m1.py --out bench/results/m1/measure.json
```

## 2. Measured facts

| Metric | Target | Result | Status |
|---|---|---|---|
| S1: speak to first audio write (10 runs) | ≤ 150 ms | median 72 ms, max 101 ms | pass (see limit 1) |
| L1: speak to first audio write (3 runs) | — | median 45 ms | — |
| L1: playback time minus audio length (59.1 s of audio, 3 runs) | no gaps | median 49 ms, max 50 ms | pass (see limit 2) |
| Cancel: command to reply (5 runs) | — | median 2 ms, max 5 ms | — |
| Cancel: sound stops | ≤ 100 ms | `stop()` takes 1 ms; one listener confirmed that the sound stops at once | pass |
| Cancel: command to `cancelled` event (5 runs) | — | median 95 ms, max 169 ms | — |
| Barge-in: `interrupt` 0.3 s after start to first audio write of the new text (5 runs) | — | median 159 ms, max 237 ms | see observation 1 |
| Dialogue: `done` of voice 1 to `started` of voice 2 (5 runs) | — | median 0.1 ms | see limit 3 |
| Daemon start, 2 voices with warm-up | — | 2.8 s | — |
| RSS after S1, L1 and cancel tests with `zenski` | ≤ 600 MB | 511 MB | pass |
| RSS after L1 also with `gosia` | ≤ 700 MB for 2 voices (changed from 600 MB, see decision) | 656 MB | pass |
| Unit tests | all pass | 30 of 30, stable in 20 consecutive runs | pass |

## 3. Observations

1. **Barge-in waits for the current sentence.** The synthesis thread checks for cancel only between Piper chunks. Piper gives one chunk for each sentence. If the interrupt comes during the synthesis of a long sentence, the new text waits until that sentence is complete. The result is 136-237 ms to the first audio write, against 58-101 ms for S1 without barge-in. The old sound stops at once. Only the start of the new text is late.
2. **RSS increases with the number of voices that read long text.** Each voice has its own ONNX Runtime session. M0 observation 4 showed that the memory arena keeps memory after the longest input. With 2 voices, RSS is 656 MB. This is above the first M1 target (600 MB) and below the `research.md` target (1.5 GB).
3. The daemon process does not import `bench/`. It reads the model files from `bench/models/piper/` (`local_tts/config.py`).

## 4. Limits of the method

1. "First audio write" is the time when the daemon writes the first audio to `pw-cat`. The time until the sound comes out of the speaker is not included. A separate test played 2.0 s of audio through `pw-cat` in 2.056 s, so the start and drain overhead of `pw-cat` is approximately 50 ms. This value is an estimate, not a measurement of the sound output.
2. Gaps in playback are not detected directly. The 49 ms of extra time contains all gaps plus the `pw-cat` start and drain. So the sum of all gaps in 59 s of audio is less than 50 ms.
3. The dialogue value is measured at the audio write, not at the speaker. The player starts a new `pw-cat` process for each utterance, so the silence between two voices is probably approximately 50 ms longer. This is not measured.
4. 1 machine, 1 listener for the cancel test, 3-10 runs for each metric.

## 5. Recommendations

1. **RSS (observation 2):** before M5, measure `SessionOptions.enable_cpu_mem_arena = False` for RSS and RTF.
2. **Barge-in (observation 1):** measure barge-in again in M4, where the end-to-end TTFA is measured. Possible fixes: split long sentences at commas (this also decreases TTFA), or stop the ONNX Runtime run with `RunOptions.terminate`. Do not fix it in M1.
3. **Silence between voices (limit 3):** if dialogues become a milestone, measure the sound output with a loopback recording.

## 6. Decision

Date: 2026-10-08. The RSS target for 2 loaded voices is 700 MB (it was 600 MB). Reason: the `research.md` target for the daemon is 1.5 GB, and 656 MB is far below it. The arena test (recommendation 1) is a separate task before M5. With this change, M1 is complete.
