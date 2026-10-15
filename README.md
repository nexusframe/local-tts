# local-tts

Local text-to-speech daemon for a Polish AI assistant. It uses Piper voices on the CPU and plays audio through PipeWire (`pw-cat`). Linux only.

## Install

```
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.lock.txt
python3 bench/fetch_models.py --backend piper   # voices go to bench/models/piper/
.venv/bin/python scripts/patch_alignment.py      # copies with word times go to bench/models/piper-aligned/
```

The patched copies give the word times for `spoken_partial` (see below). The script verifies that the audio of each copy is the same as the audio of the original. Without the copies, the daemon works, and `spoken_partial` is always empty.

## Start the daemon

```
.venv/bin/python -m local_tts
```

The daemon listens on the Unix socket `$XDG_RUNTIME_DIR/local-tts.sock`. Use `--help` to see all options (voices, threads, socket path). To stop the daemon, push Ctrl+C or send SIGTERM.

### Start the daemon as a systemd user service

The unit file `systemd/local-tts.service` starts the daemon with the graphical session and starts it again after a failure. It expects the repository in `~/projects/local-tts`. Stop a daemon that you started by hand first, because the service uses the same socket. A second daemon on a socket that is in use stops at once with exit code 78.

```
ln -s ~/projects/local-tts/systemd/local-tts.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now local-tts
```

`systemctl --user start` returns when the voices are loaded and the socket listens. Logs: `journalctl --user -u local-tts -f`. Stop: `systemctl --user stop local-tts`. After a change to the code: `systemctl --user restart local-tts`.

### Metrics

At the end of each request the daemon logs one line `metrics {...}` (JSON):

| Field | Meaning |
|---|---|
| `result` | `done`, `cancelled` or `error` |
| `chars`, `sentences` | length of the client text, number of synthesized sentences |
| `first_audio_s` | seconds from the first text to the first audio write (for a stream: from the first `append` with text, not from `begin`). `null` if no audio was played |
| `synth_s`, `audio_s`, `rtf` | synthesis time, audio time, and `synth_s / audio_s` |

`python scripts/metrics_summary.py --since "-1 day"` shows the median and p95 of `first_audio_s` and `rtf` for each voice.
The `status` event also has `rss_mb` and `peak_rss_mb` (memory of the daemon process), `uptime_s`, and `results` (number of `done`, `cancelled` and `error` events since the start).

## Speak text from the command line

```
.venv/bin/python -m local_tts.client speak "Dzień dobry."
.venv/bin/python -m local_tts.client speak --voice jarvis "Dzień dobry."
.venv/bin/python -m local_tts.client speak --voice en_cori "Good morning."
.venv/bin/python -m local_tts.client speak --interrupt "Stop."   # stop the current speech first
.venv/bin/python -m local_tts.client speak --speed 0.8 "Wolniej."  # slower than the rate of the voice
.venv/bin/python -m local_tts.client speak --no-wait "Tekst."     # do not wait for the end
.venv/bin/python -m local_tts.client cancel                       # stop speech, clear the queue
.venv/bin/python -m local_tts.client status                       # voices, current speech, queue
```

Voices: `zenski` (default), `jarvis`, `en_hfc_female`, `en_cori`, `en_bryce`, `en_hfc_male`. The Polish voices read English words in `<en>` tags: `Testy w <en>Python</en>ie przeszły.` See `docs/en-tags.md`.

Without the client, send one JSON object per line to the socket:

```
echo '{"cmd": "speak", "text": "Dzień dobry."}' | socat - UNIX-CONNECT:$XDG_RUNTIME_DIR/local-tts.sock
```

For streamed LLM text, use `begin`, `append` and `end` (see `local_tts/protocol.py` and `docs/m4-results.md`).

`speak` and `begin` have an optional field `speed`: a multiplier of the speech rate of the voice, from 0.5 to 2.0. The default is 1.0. A smaller value gives slower speech, for example to say an answer again more slowly. For `begin`, the speed is for all the text of the stream. A value out of the range gives an `error` event. Each voice has its own rate at 1.0 (see `docs/voices.md`, "Speech rate"):

```
{"cmd": "speak", "text": "Numer to 5 5 5, 1 2 3.", "speed": 0.8}
```

The speed is for a full request, not for one word in a sentence: Piper uses one rate for each synthesis. To say one word more slowly, send it in a separate request.

A sentence is spoken when the next sentence starts or at `end`. Before a pause in the text, for example an LLM tool call, send `flush`. The daemon then speaks the text that it has now, and the stream stays open. The text after `flush` starts to play early again (`--first-words`). `flush` has no reply:

```
{"cmd": "flush", "id": "s1"}
```

Each request gets one final event: `done`, `cancelled` or `error`. The events `cancelled` and `error` have the field `spoken`: the text of the segments that the listener heard completely, as the client sent it (before normalization). A segment is a sentence or the early first part of a stream. Use it to remove the words that were not spoken from the LLM history after barge-in:

```
{"event": "cancelled", "id": "u1", "spoken": "Pierwsze zdanie jest krótkie."}
```

The daemon calculates `spoken` from the audio in the output buffer at the time of the cancel. A segment that was cut in the middle is not in `spoken`. A request that did not start gets `"spoken": ""`.

The events `cancelled` and `error` also have the field `spoken_partial`: the words of the cut segment that the listener heard completely, from the start of the segment, as the client sent them. Use `spoken` and `spoken_partial` together:

```
{"event": "cancelled", "id": "u1", "spoken": "", "spoken_partial": "Kraków to jedno z najstarszych miast w Polsce,"}
```

- The word times come from the phoneme alignment of the Piper model (`scripts/patch_alignment.py`).
- A number or an abbreviation counts only when all its spoken words were heard ("1257" is 4 words).
- Measured on the real daemon (2026-10-12, voice `zenski`, 1 sentence, 7 cuts): in 5 cuts, the error was 0 words, compared with a recording of the audio output. In 2 cuts inside "1257", the field had 2 and 3 words fewer (the number rule above). The reference has an error of about 1 word, because the word times of two syntheses differ (median 192 ms).
- Word times compared with an independent reference (the last sound before each space phoneme, same synthesis): Polish corpus 187 of 200 words agree within 1 ms, 13 are late (at most 128 ms), none early. English voices `cori`, `bryce`: 2 sentences each, 1 word late (93 and 151 ms), none early.
- `spoken_partial` is `""` when no segment was cut, when no word of it was heard, or when the voice has no word times.

## Text from the client: numbers

Both normalizers read units and currency (`5 km`, `20 zł`, `$20`). The English normalizer reads a range as "to" (`15-20°C` is "15 to 20 degrees Celsius"). The Polish normalizer reads a range without "do" (`15-20` is "piętnaście-dwadzieścia"). Some numbers need a special format from the client (for example, the LLM prompt of the assistant):

- **Phone numbers:** write the digits one by one with spaces, and put a comma between the groups: `5 5 5, 1 2 3, 4 5 6`. For a country code, write `plus 4 8,` (English) or `plus czterdzieści osiem,` (Polish). Both voice languages read this format correctly (measured 2026-10-13).
- Do not send a phone number with hyphens. The English normalizer reads two groups as a range (`555-123` is "555 to 123"). It does not change three or more groups, and espeak-ng reads the hyphens as "dash" (`555-123-456`). The Polish normalizer reads each group as a number with a hyphen.
- Do not send a phone number with spaces only (`555 123 456`). The Polish normalizer reads it as one number: "pięćset pięćdziesiąt pięć milionów…".
- ISO dates (`2026-10-13`) are not changed by the English normalizer. espeak-ng reads the hyphens as "dash". Write the date in words for an English voice: `October 13, 2026`.

## Pronunciation dictionary

To change how the daemon reads a word, add it to `~/.config/local-tts/pronunciation.toml` (or the file of `--pronunciation`). Use one table for each language of the voices:

```toml
[pl]
"Kubernetes" = "<en>kubernetes</en>"
"nginx" = "<en>engine x</en>"

[en]
"nginx" = "engine x"
```

- The daemon replaces whole words before the normalizer, so the new text can have `<en>` tags, numbers and abbreviations.
- Words are case-sensitive. A longer word wins ("GitHub Actions" before "GitHub"). Text in `<en>` tags does not change.
- The daemon reads the file again when it changes. If the file is not valid, the log shows a warning and the last valid words stay in use.
- The `spoken` field of the events has the text before the replacement.

## Tests

```
.venv/bin/python -m pytest
```
