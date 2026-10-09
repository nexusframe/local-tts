"""M4: how fast does PiperBackend.interrupt() stop the synthesis of a long sentence?

interrupt() sets RunOptions.terminate on the current ONNX Runtime run.
Run: .venv/bin/python scripts/spike_terminate_m4.py | tee bench/results/m4/terminate_spike.txt
"""
import statistics
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from local_tts.backends.piper import PiperBackend  # noqa: E402
from local_tts.config import DEFAULT_MODELS_DIR, DEFAULT_VOICES  # noqa: E402

LONG = ("Jutro w Krakowie od rana będzie pochmurno i chłodno, po południu przelotne opady deszczu, "
        "a wieczorem wiatr z zachodu przyniesie wyraźne ochłodzenie oraz mgły w dolinach rzek.")

model = DEFAULT_VOICES["zenski"]
backend = PiperBackend(DEFAULT_MODELS_DIR / model / f"{model}.onnx")
backend.warm_up()
start = time.perf_counter()
list(backend.synthesize(LONG))
print(f"full synthesis of the long sentence: {(time.perf_counter() - start) * 1000:.0f} ms")

latencies = []
for delay in [0.02, 0.05, 0.1, 0.2, 0.3] * 3:
    result = {}

    def work():
        try:
            list(backend.synthesize(LONG))
            result["outcome"] = "finished"
        except Exception as exc:
            result["outcome"] = f"{type(exc).__name__}: {str(exc)[:50]}"
        result["end"] = time.perf_counter()

    thread = threading.Thread(target=work)
    thread.start()
    time.sleep(delay)
    interrupted = time.perf_counter()
    backend.interrupt()
    thread.join()
    latency = (result["end"] - interrupted) * 1000
    latencies.append(latency)
    print(f"interrupt after {delay * 1000:.0f} ms -> synthesis ends {latency:.1f} ms later: {result['outcome']}")
print(f"median {statistics.median(latencies):.1f} ms, max {max(latencies):.1f} ms, n {len(latencies)}")
start = time.perf_counter()
list(backend.synthesize("Test po przerwaniu."))
print(f"next synthesis OK: {(time.perf_counter() - start) * 1000:.0f} ms")
