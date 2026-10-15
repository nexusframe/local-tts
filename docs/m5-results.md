# M5 results: memory, systemd service, logs and metrics

Date: 2026-10-15. `main`: 8a40a2a. Machine: i5-8365U.

## 1. Scope

`research.md` section 18.3 gives M5 as: automatic fallback (Pocket to Piper), a `systemd --user` service, logs and metrics.
The open item from M1 (ONNX Runtime arena and RSS) was done first.

| Part | Status | Commit | Details |
|---|---|---|---|
| A. ONNX Runtime CPU memory arena off | done | 00aff3e | `docs/m5-arena.md` |
| B. `systemd --user` service, `READY=1`/`STOPPING=1`, exit 78 when the socket is in use | done | 4070ac0 | `README.md`, `systemd/local-tts.service` |
| B fix. Stop with a connected client | done | 3966c39 | see section 3 |
| C. `metrics` log line for each request, process fields in `status`, summary script | done | 8a40a2a | `README.md` section "Metrics" |
| D. Automatic fallback | not done | — | see section 4 |

## 2. Measured facts

| Metric | Target | Result | Source | Status |
|---|---|---|---|---|
| Daemon RSS, 6 default voices | ≤ 1.5 GB (`research.md`) | 586-592 MB after all corpus texts, peak 808-813 MB (before: 2010-2222 MB) | `docs/m5-arena.md` | pass |
| Daemon RSS, 1 voice | — | 151 MB after load, 214 MB after L1, peak 412 MB | `docs/m5-arena.md` | — |
| RTF with the arena off | no RTF loss larger than 10 % (plan criterion, not in `research.md`) | differences between variants are in the noise of the measurement (up to 17 % between two series of the same variant) | `docs/m5-arena.md` | pass |
| Service start (6 voices) | — | 9.8 s until `READY=1` | live test | — |
| Restart after `kill -9` | starts again | new process after `RestartSec=2`, `NRestarts=1` | live test | pass |
| `systemctl --user stop`, no client | exit 0, socket removed | exit 0, `Result=success`, socket removed | live test | pass |
| `systemctl --user stop`, one client connected | exit 0 | before 3966c39: no stop in 20 s (`deactivating`). After: 0.19 s, the client gets end of file | live test | pass |
| Second daemon on a live socket | does not take the socket | exit 78 after 0.4 s, first daemon continues | live test | pass |
| `metrics` line and `status` fields | one line for each request | lines for `zenski`, `jarvis`, `en_cori`; `status` with `rss_mb`, `peak_rss_mb`, `uptime_s`, `results` | live test | pass |
| Tests | all pass | 1048 passed, 1 xfailed | `pytest` | pass |

Other prototype targets were measured in M1 and M4 with the arena on: TTFA of a short answer ≤ 202 ms (target ≤ 400 ms), no gaps in 59 s of audio, sound stops after `cancel` at once (`stop()` 1 ms). See `docs/m1-results.md` and `docs/m4-results.md`.

## 3. Observations

1. With the arena on, RSS increased with each new longest input of a voice. The earlier value of 1509 MB was after one synthesis for each voice only. The daemon went above the 1.5 GB target in normal use.
2. In Python 3.12 the end of `async with server` waits until all clients disconnect. The assistant keeps its connection open, so `systemctl --user stop` waited until systemd sent SIGKILL (default `TimeoutStopSec` 90 s). The SIGTERM test from d3d83a2 had no connected client. Fix: the server closes the client connections before the end of `async with` (test: `test_sigterm_stops_the_server_also_with_a_connected_client`).
3. First live `metrics` values (one request each, 2 sentences): `first_audio_s` 0.071-0.183 s, `rtf` 0.08-0.123.

## 4. Not done, and limits

1. **D. Automatic fallback.** The planned fallback was "Pocket to Piper". M0 rejected Pocket, and the fallback voice `gosia` was removed from the default set. A new fallback (for example: the default voice when another voice fails) has no request from a client. Recommendation: do it only when a client needs it.
2. **TTFA and barge-in were not measured again with the arena off.** The first live `metrics` values are in the M4 range, but this is not a comparison with the same method.
3. Live tests: 1 machine, 1 run for each service test.
4. local-assistant still starts the daemon by hand in its docs. A request to change this is in `~/agent-exchange/requests/2026-10-15-local-tts-to-local-assistant-systemd.md` (no reply on 2026-10-15). With the daemon running as a service, a manual start now stops with exit 78 and does not take the socket.

## 5. Decision

M5 is closed with parts A, B and C. Part D is not done (section 4, item 1).
