# M4 results: text from the LLM in pieces, end-to-end TTFA, barge-in

Date: 2026-10-09. Branch: `m4-streaming`. Data: `bench/results/m4/measure.json`, `bench/results/m4/first_words/` (measured before the uppercase, preposition and list rules), `bench/results/m4/listening.json`, `bench/results/m4/terminate_spike.txt`.

Machine: the M0 machine (Intel Core i5-8365U, AC power, governor `powersave`). Voices loaded: `zenski` (default) and `gosia`, 4 intra-op threads each.

## 1. What M4 contains

| Part | File | Test method |
|---|---|---|
| Commands `begin`, `append`, `end` (`speak` does not change) | `local_tts/protocol.py` | unit tests |
| `SentenceStream`: gives complete sentences while the text comes in; early first segment | `local_tts/splitter.py` | unit tests; parity test on 139 texts |
| Engine: stream utterances, `abort()` for one stream, `interrupt()` of the backend on cancel | `local_tts/engine.py` | unit tests with fake backend and fake player |
| Server: streams belong to their client; a disconnect cancels the open streams | `local_tts/server.py` | measurement script; disconnect: 1 smoke test run (`cancelled` event, daemon continues) |
| Piper backend: `interrupt()` stops the ONNX Runtime run (`RunOptions.terminate`) | `local_tts/backends/piper.py` | `scripts/spike_terminate_m4.py`, measurement script |
| Daemon option `--first-words` (default 2) | `local_tts/__main__.py` | measurement script |

Protocol of a stream (JSON lines, Unix socket):

```
{"cmd": "begin", "id": "s1", "voice": "zenski", "interrupt": true}   -> {"event": "accepted", "id": "s1"}
{"cmd": "append", "id": "s1", "text": "Jas"}                          -> no reply (one command for each token)
{"cmd": "end", "id": "s1"}                                             -> {"event": "ack", "cmd": "end", "id": "s1"}
```

The events `started`, `done`, `cancelled` and `error` are the same as in M1. After `cancel`, the daemon ignores `append` and `end` for the cancelled stream, because the client can send tokens before it gets the `cancelled` event.

Rules of the early first segment (only the first segment of a stream):

1. Cut at the first comma that has whitespace after it.
2. If no comma comes first: cut after `--first-words` complete words, between two plain words (letters only).
3. Do not cut after a preposition or conjunction („Jutro w | Warszawie”), before an uppercase word („Agnieszka | Brzezińska”), next to a number or an abbreviation, or in a Markdown list item.

Commands:

```
.venv/bin/python -m local_tts [--first-words 2]
.venv/bin/python scripts/measure_m4.py --out bench/results/m4/measure.json
.venv/bin/python scripts/listen_m4.py
```

## 2. Measured facts

TTFA is the time from the first `append` to the first audio write to `pw-cat`. M1 measured approximately 50 ms more until `pw-cat` starts the sound (M1 limit 1). Tokens are simulated (see section 4). 5 runs for each cell, values in ms, median / maximum.

| Text | First segment | 20 tok/s | 40 tok/s | 80 tok/s |
|---|---|---|---|---|
| S1 „Jasne, już sprawdzam.” | „Jasne,” | 147 / 152 | 81 / 95 | 71 / 79 |
| M1 „Na koncie zostało trzy tysiące…” | „Na koncie” | 388 / 400 | 213 / 214 | 144 / 152 |
| M3 „Spotkanie przeniesiono na 15.11.2026 r. …” | „Spotkanie przeniesiono” | 524 / 532 | 295 / 299 | 188 / 198 |
| M5 „Pani Agnieszka Brzezińska i pan…” | „Pani Agnieszka Brzezińska” | 641 / 648 | 347 / 366 | 212 / 221 |
| L1 „Dzień dobry! Sprawdziłem…” (1022 characters) | „Dzień dobry!” | 289 / 306 | 172 / 188 | 113 / 118 |

Without the early first segment, synthesis cannot start before the first sentence is complete. For M1 this is 1650 / 825 / 412 ms at 20 / 40 / 80 tok/s (calculated from the send schedule, `first_sentence_s`). With `--first-words 6`, M1 had a TTFA of 1085 / 578 / 345 ms (`first_words/fw6.json`).

| Metric | Target | M1 result | M4 result | Status |
|---|---|---|---|---|
| TTFA end to end, short answer (S1), plus 50 ms for `pw-cat` | ≤ 400 ms | — | ≤ 202 ms at all rates | pass |
| TTFA end to end, one sentence without a comma (M1, M3, M5), plus 50 ms | ≤ 400 ms | — | 80 tok/s: pass (max 271 ms). 40 tok/s: median pass for all (max median 397 ms, M5); M5 maximum 416 ms. 20 tok/s: fail for all three (median 438-691 ms) | partly |
| Barge-in: `speak` with `interrupt` to first audio of the new text (10 runs) | — | median 159, max 237 | median 66, max 91 | better |
| Barge-in with streams: new stream with `interrupt` (S2 at 40 tok/s) to first audio (10 runs) | — | — | median 177, max 188 | — |
| `cancel` to `cancelled` event during L1 (10 runs) | — | median 95, max 169 | median 4, max 20 | better |
| Synthesis stop after `PiperBackend.interrupt()`, long sentence of 537 ms (`terminate_spike.txt`, 15 runs) | — | — | median 0.7, max 88.6; all 15 runs stopped | — |
| RSS after the measurement | ≤ 700 MB for 2 voices | 656 MB | 459 MB (only `zenski` read long text) | pass |
| Unit tests | all pass | 30 | 743 passed, 1 expected failure (N19) | pass |

Playback time minus audio length (`(done - started) - audio_seconds`, contains the gaps plus the `pw-cat` start and drain), 3 runs:

| Text | `speak` (reference) | stream 20 tok/s | stream 80 tok/s |
|---|---|---|---|
| S1 | 120 ms | 133 ms | 121 ms |
| M1 | 144 ms | **716 ms** | 147 ms |
| L1 (59 s of audio, 1 run) | 49 ms (M1 measurement) | 301 ms | not measured |

## 3. Observations

1. **At 20 tok/s, the early first segment makes a pause inside the sentence.** M1: the rest of the sentence comes from the LLM at 1.65 s, but „Na koncie” is short (estimate: less than 1 s of audio). The measured extra playback time is 716 ms against 144 ms for `speak`, so the pause inside the sentence is approximately 0.6 s. At 80 tok/s there is no pause (147 ms, the same as `speak`). So the early segment changes the delay before the sound into a pause inside the sentence when the LLM is slower than the speech.
2. **The rules that protect the intonation also make TTFA longer.** M5 at 40 tok/s: 322 ms in the first sweep (cut „Pani Agnieszka |”), 347 ms with the uppercase rule (cut „Pani Agnieszka Brzezińska |”). M3 can be cut only before the date, because the date and „godz.” block all other cuts.
3. **Listening test (1 listener, blind, 5 sentences, `listening.json`).** The early cut was preferred or equal in 3 of 5 sentences (M1, X1, X2). The listener preferred no cut inside a name (M5) and the full sentence for M3 (no cut before the date). The uppercase rule came from this result.
4. **The normalizer can make new sentence ends** (for example from „;” or a removed tag). The engine splits each segment again after normalization. With this, the streamed sentences are the same as the batch sentences in 139 of 139 texts. Before the fix in the splitter, „ok. 5 km” and „tel.” gave a different split in 2 texts.
5. **`interrupt()` can come just before the backend starts a run.** Then the run is not stopped and the new text waits for one sentence, as in M1. The 10 barge-in runs did not show this (max 91 ms).

## 4. Limits of the method

1. Tokens are simulated: up to 3 characters of a word in each token, at a fixed rate. A real LLM has a variable rate and other token borders. No real LLM was connected; the assistant client is still a hypothesis (M1 decision).
2. TTFA and gaps are measured at the audio write to `pw-cat`, not at the speaker (M1 limits 1 and 2).
3. The `speak` reference for S1 and M1 (120-144 ms) is larger than the M1 value for L1 (49 ms). For short texts, the `pw-cat` start and drain are a larger part of the value. The difference between `speak` and stream is the useful value, not the absolute value.
4. 1 machine, 1 listener, 5 sentences in the listening test, 3-10 runs for each metric.
5. Barge-in values were measured with the old text in `speak` mode. With a stream as the old text, only the TTFA of the new stream was measured.

## 5. Recommendations

1. **Pause at slow LLM rates (observation 1):** when the real LLM and its token rate are known, measure again. If the rate is below approximately 30 tok/s, examine an adaptive rule: cut the first segment early only if the measured token rate is high enough to send the rest of the sentence before the first segment ends.
2. **TTFA at 20 tok/s for M1, M3 and M5:** the target is not met. It is not possible to meet it with a sentence-level backend and this LLM rate without more cuts that break the intonation. Accept it, or examine a backend that streams inside a sentence.
3. **Listening:** repeat the test with more sentences from real assistant answers when a client exists.
4. **Before M5:** the ORT arena RSS test (M1 recommendation 1) is still open.

## 6. Decision

Date: 2026-10-09. Default `--first-words 2` with the rules in section 1. Reason: only 2 words gives a median TTFA in the target at 40 tok/s for all measured texts (M5: 397 ms with `pw-cat`, maximum 416 ms), and the listening test did not show a worse result for the early cut, except a cut inside a name (now blocked).
