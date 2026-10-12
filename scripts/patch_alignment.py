"""Make copies of the Piper models with the phoneme alignment output.

Run: .venv/bin/python scripts/patch_alignment.py [MODEL ...]
Default: the models of DEFAULT_VOICES. The copies go to bench/models/piper-aligned/
(not in git). The originals in bench/models/piper/ do not change, because
bench/fetch_models.py verifies their sha256.

The patch marks the w_ceil tensor (audio frames for each phoneme id) as a model
output (piper.patch_voice_with_alignment, piper-tts 1.8.0, needs the onnx package).
The script verifies each copy:
1. With noise 0, the audio of the copy is the same as the audio of the original, bit for bit.
2. The sum of the alignment samples is the number of audio samples.
"""

import json
import shutil
import sys
from pathlib import Path

import numpy as np
import onnx
import onnxruntime as ort
from piper.patch_voice_with_alignment import add_alignment_output
from piper.voice import PiperConfig, PiperVoice, SynthesisConfig

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from local_tts.config import ALIGNED_MODELS_DIR, DEFAULT_MODELS_DIR, DEFAULT_VOICES

TEXTS = {"pl": "Kraków to jedno z najstarszych miast w Polsce.", "en": "The weather will be sunny tomorrow."}
NO_NOISE = SynthesisConfig(noise_scale=0.0, noise_w_scale=0.0)


def voice(model_path: Path, config: PiperConfig) -> PiperVoice:
    return PiperVoice(config=config, session=ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"]))


def patch(model: str) -> None:
    source = DEFAULT_MODELS_DIR / model / f"{model}.onnx"
    target = ALIGNED_MODELS_DIR / model / f"{model}.onnx"
    target.parent.mkdir(parents=True, exist_ok=True)
    proto = onnx.load(str(source))
    tensor = add_alignment_output(proto)
    onnx.save(proto, str(target))
    shutil.copyfile(f"{source}.json", f"{target}.json")

    config = PiperConfig.from_dict(json.loads(Path(f"{source}.json").read_text(encoding="utf-8")))
    original, patched = voice(source, config), voice(target, config)
    text = TEXTS[config.espeak_voice.split("-")[0]]
    ids = original.phonemes_to_ids(original.phonemize(text)[0])
    expected = original.phoneme_ids_to_audio(ids, NO_NOISE)
    audio, samples = patched.phoneme_ids_to_audio(ids, NO_NOISE, include_alignments=True)
    if not np.array_equal(expected, audio):
        raise SystemExit(f"{model}: the audio of the copy is not the same as the audio of the original")
    if samples is None or int(samples.sum()) != len(audio):
        raise SystemExit(f"{model}: the alignment samples do not agree with the audio length")
    print(f"{model}: OK (tensor {tensor}, {len(ids)} phoneme ids, {len(audio)} samples)")


def main() -> None:
    for model in sys.argv[1:] or DEFAULT_VOICES.values():
        patch(model)


if __name__ == "__main__":
    main()
