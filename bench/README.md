# M0 benchmark: Polish TTS on CPU

This directory contains a reproducible benchmark of three local text-to-speech (TTS) backends for Polish:

1. Pocket TTS with the community model `shefowl/pocket-tts-polish-6l`.
2. Piper (`piper1-gpl`, Python package `piper-tts`).
3. Supertonic 3.

The benchmark measures speed, latency, memory, streaming behavior and stability. It does not measure the quality of Polish speech automatically. For quality, use the blind listening test (see [Listening test](#listening-test)).

The results are in `results/report.md`. The decision document for M0 is `../docs/m0-decision.md`.

## Prerequisites

- Linux on x86-64. The benchmark uses CPU only.
- Python 3.12 with the `venv` module.
- `git`, `taskset` (package `util-linux`).
- Network access to `pypi.org`, `download.pytorch.org`, `huggingface.co` and `github.com` during setup only.
- About 3.5 GB of free disk space.
- About 2 GB of free RAM.

## Procedure

1. Install the backends and download the models:

   ```bash
   bench/setup.sh
   ```

   The script makes one venv for each backend in `bench/.venvs/`. It downloads the models to `bench/models/` and to the Hugging Face cache. All model revisions are pinned in `models.json`. The script verifies the sha256 of each large file.

2. Connect the computer to AC power.

3. Stop other heavy work on the computer. Other processes change the results. The report shows how much CPU other processes used during each run.

4. Run the benchmark:

   ```bash
   bench/run_all.sh
   ```

   The full run takes about 4 to 5 hours on an Intel Core i5-8365U. To test the setup in about 20 minutes, use `bench/run_all.sh --quick`. Do not use `--quick` results for decisions.

5. Read `bench/results/report.md`.

To run only one backend, use `bench/run_all.sh --backend piper`. To continue an interrupted run, use `bench/run_all.sh --resume`.

## What the benchmark measures

| Suite | Texts | Protocol | Metrics |
|---|---|---|---|
| warm | all 11 raw texts | 3 warm-up runs, then 10 measured runs, for each thread configuration | TTFA, total time, audio duration, RTF, CPU cores used, peak RSS, audio checks, warnings |
| stream | S1, M1, L1 | 1 warm-up run, then 3 runs | arrival time and size of each chunk, playback simulation, cancel latency |
| repeat | M1, M8 | 3 warm-up runs, then 100 runs | time drift, RSS drift, audio length changes, errors |
| samples | all raw and normalized texts | 1 run | WAV files and audio checks |
| cold | S1 | 3 new processes | time from process start to the first audio chunk |

Definitions:

- **TTFA** (time to first audio): the time from the synthesis call to the first audio chunk. The model is already loaded.
- **RTF** (real-time factor): synthesis time divided by audio duration. A value below 1.0 is faster than real time.
- **Peak RSS**: the maximum resident memory of the process. The orchestrator gets it from `wait4()`.
- **Streaming**: the backend streams only if the first chunk arrives before 90% of the total synthesis time. An API that returns an iterator is not sufficient evidence.

### Thread configurations

| Name | Intra-op threads | CPUs (`taskset -c`) |
|---|---:|---|
| t1c2 | 1 | 0,1 |
| t2c2 | 2 | 0,1 |
| t4c4 | 4 | 0-3 |
| t8c8 | 8 | 0-7 |

On the reference machine, CPUs 0-3 are four different physical cores and CPUs 4-7 are their hyper-threads. On a different machine, check `lscpu -e` and edit `THREAD_CONFIGS` in `bench.py`.

The orchestrator selects the best configuration for each target. The best configuration has the lowest mean of the per-text median RTF. The stream, repeat, samples and cold suites run only on the best configuration.

### Technical decisions

- **One venv for each backend.** Pocket TTS needs PyTorch. Piper and Supertonic need ONNX Runtime. Separate venvs prevent version conflicts and make the memory values independent.
- **One process for each configuration.** A new process gives a clean memory measurement. It also makes sure that thread settings from one configuration do not affect the next configuration.
- **Thread control in the adapters.** `PiperVoice.load()` and the Supertonic helper create ONNX Runtime sessions with default options. The adapters create the sessions with `intra_op_num_threads`. `pocket_tts` calls `torch.set_num_threads(1)` when it is imported, so the adapter sets the thread count after the import.
- **Two int8 paths for Pocket TTS.** `pocket-tts[quantize]` installs `torchao`, and `pocket-tts` then uses the `torchao` int8 kernels. pocket-tts also has a fallback that uses `torch.ao` (FBGEMM). Both are measured as separate targets: `int8-torchao` and `int8-torch.ao`.
- **No text normalizer.** The engines get the raw text. `corpus.json` contains hand-written normalized forms. The samples suite synthesizes both forms, so you can hear the effect of normalization.
- **Fixed seeds.** Pocket TTS and Supertonic use random sampling. The adapters set a seed once at load time. Each run then uses the next random values, as in real use.
- **No network during runs.** The orchestrator sets `HF_HUB_OFFLINE=1`.

## Files

| Path | Purpose |
|---|---|
| `setup.sh` | Makes the venvs, installs pinned packages, gets the Supertonic helper code, downloads models. |
| `run_all.sh` | Records the environment, runs `bench.py run`, makes the report. |
| `bench.py` | Orchestrator. Starts one `run_backend.py` process for each configuration. |
| `run_backend.py` | Runs the suites inside a backend venv. |
| `common.py` | Measurement code: timing, RSS sampler, audio checks, statistics. |
| `backends/*_backend.py` | One small adapter for each backend. |
| `corpus.json` | Test texts S1-S2, M1-M8, L1, with normalized reference forms. |
| `models.json` | Model repositories, pinned revisions and sha256 values. |
| `requirements/*.lock.txt` | Pinned Python packages for each venv. |
| `fetch_models.py` | Downloads models and verifies sha256. |
| `env_info.py` | Records the environment to `results/env.json`. |
| `report.py` | Makes `results/report.md` and `results/summary.json` from `results/raw/*.json`. |
| `listening_kit.py` | Makes a blind listening test from the WAV samples. |
| `results/raw/` | One JSON file for each run. |
| `results/audio/` | WAV samples. Not in git. |
| `results/logs/` | Process output. Not in git. |

## Listening test

The benchmark cannot measure the quality of Polish speech without a speech recognizer or human listeners. To make a blind listening test:

1. Make the test files:

   ```bash
   python3 bench/listening_kit.py
   ```

2. Listen to the files in `bench/results/listening/` in the order of their names. Do not open `key.json`.

3. In `ratings.csv`, give each file a score from 1 to 5 for naturalness, pronunciation and prosody.

4. Get the mean scores for each model:

   ```bash
   python3 bench/listening_kit.py --score
   ```

Use at least 3 native Polish listeners for a reliable result.

## Automatic quality evaluation (ASR)

No local speech recognizer (ASR) is installed on the reference machine. The benchmark does not download one, because the models are large. The options are:

| ASR model | Download for CPU use | Runtime | Note |
|---|---|---|---|
| `nvidia/parakeet-tdt-0.6b-v3` (ONNX int8, `istupakov/parakeet-tdt-0.6b-v3-onnx`) | about 640 MiB | `onnx-asr` + onnxruntime | Polish supported. The Pocket PL model author used it as a second recognizer. |
| `istupakov/canary-1b-v2-onnx` (int8) | about 1 GiB | `onnx-asr` + onnxruntime | Polish supported. Slower. |
| `Systran/faster-whisper-large-v3` | about 2.9 GiB | `faster-whisper` | Large and slow on this CPU. |
| `nvidia/stt_pl_fastconformer_hybrid_large_pc` | about 120 MiB | sherpa-onnx | The Pocket PL author reports that it misses Polish consonant clusters. Do not use it alone. |

All options work offline after the download. Use the same ASR for all backends. Do not compare WER values from different sources.

## Limitations

- The results are valid for the reference machine only. Repeat the benchmark on the target hardware.
- The computer is a desktop in normal use. Other processes used CPU during the runs. The report shows this value for each configuration.
- Cold start values use a warm operating system file cache. A first start after a reboot is slower.
- The audio checks detect empty, broken, clipped and unusually fast or slow audio. They cannot detect wrong pronunciation.
- Pocket TTS uses one voice: `reference.wav` from the model repository. Other reference clips can give different quality and speed.
