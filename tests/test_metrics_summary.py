"""scripts/metrics_summary.py: medians and p95 of the "metrics" log lines, for each voice."""

import importlib.util
import json
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scripts" / "metrics_summary.py"
spec = importlib.util.spec_from_file_location("metrics_summary", SCRIPT)
metrics_summary = importlib.util.module_from_spec(spec)
spec.loader.exec_module(metrics_summary)


def line(voice, result="done", first_audio=0.3, rtf=0.08):
    data = {"id": "u", "voice": voice, "result": result, "chars": 10, "sentences": 1,
            "first_audio_s": first_audio, "synth_s": 0.1, "audio_s": 1.0, "rtf": rtf}
    return "2026-10-15 22:00:00,000 INFO local_tts.engine: metrics " + json.dumps(data)


def test_summary_for_each_voice_skips_other_lines_and_missing_values():
    lines = [
        "2026-10-15 22:00:00,000 INFO local_tts.server: started {'id': 'u1'}",
        line("zenski", first_audio=0.2, rtf=0.07),
        line("zenski", first_audio=0.4, rtf=0.09),
        line("zenski", first_audio=0.3, rtf=0.08),
        line("zenski", result="cancelled", first_audio=None, rtf=None),
        line("jarvis", result="error", first_audio=0.5, rtf=0.1),
    ]
    summary = metrics_summary.summarize(lines)
    assert summary["zenski"]["results"] == {"done": 3, "cancelled": 1}
    assert summary["zenski"]["first_audio_s"] == {"n": 3, "median": 0.3, "p95": 0.4}
    assert summary["zenski"]["rtf"] == {"n": 3, "median": 0.08, "p95": 0.09}
    assert summary["jarvis"]["results"] == {"error": 1}
