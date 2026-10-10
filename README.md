# local-tts

Local text-to-speech daemon for a Polish AI assistant. It uses Piper voices on the CPU and plays audio through PipeWire (`pw-cat`). Linux only.

## Install

```
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.lock.txt
python3 bench/fetch_models.py --backend piper   # voices go to bench/models/piper/
```

## Start the daemon

```
.venv/bin/python -m local_tts
```

The daemon listens on the Unix socket `$XDG_RUNTIME_DIR/local-tts.sock`. Use `--help` to see all options (voices, threads, socket path). To stop the daemon, push Ctrl+C or send SIGTERM.

## Speak text from the command line

```
.venv/bin/python -m local_tts.client speak "Dzień dobry."
.venv/bin/python -m local_tts.client speak --voice jarvis "Dzień dobry."
.venv/bin/python -m local_tts.client speak --voice en_cori "Good morning."
.venv/bin/python -m local_tts.client speak --interrupt "Stop."   # stop the current speech first
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

## Tests

```
.venv/bin/python -m pytest
```
