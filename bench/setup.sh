#!/usr/bin/env bash
# Create one venv per backend, install pinned packages, get the Supertonic
# helper code and download all models at pinned revisions.
#
# Prerequisites: python3.12 with venv, git, curl access to pypi.org,
# download.pytorch.org, huggingface.co and github.com. About 3.5 GB of disk.
set -euo pipefail

BENCH_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="${PYTHON:-python3.12}"
TORCH_INDEX="https://download.pytorch.org/whl/cpu"
SUPERTONIC_REPO="https://github.com/supertone-oss-archive/supertonic"
SUPERTONIC_REV="1e9799e964ea4c0dad7cde993b65c3c813a7b373"

for backend in piper pocket supertonic; do
  venv="$BENCH_DIR/.venvs/$backend"
  if [[ ! -x "$venv/bin/python" ]]; then
    echo "== create venv $backend"
    "$PY" -m venv "$venv"
  fi
  extra=()
  # The CPU index prevents a download of CUDA builds of torch.
  [[ "$backend" == pocket ]] && extra=(--extra-index-url "$TORCH_INDEX")
  echo "== install $backend"
  "$venv/bin/pip" install -q -r "$BENCH_DIR/requirements/$backend.lock.txt" "${extra[@]}"
done

vendor="$BENCH_DIR/.vendor/supertonic"
if [[ ! -d "$vendor/.git" ]]; then
  echo "== clone Supertonic helper code"
  git clone -q "$SUPERTONIC_REPO" "$vendor"
fi
git -C "$vendor" -c advice.detachedHead=false checkout -q "$SUPERTONIC_REV"

echo "== download models"
python3 "$BENCH_DIR/fetch_models.py"

# pocket-tts downloads its weights into the Hugging Face cache on first load.
# Load the model once here, so that benchmark runs do not include a download.
echo "== prefetch Pocket TTS weights"
BENCH_DIR="$BENCH_DIR" "$BENCH_DIR/.venvs/pocket/bin/python" - <<'PYEOF'
import json, os, pathlib
from pocket_tts import TTSModel
cfg = json.loads((pathlib.Path(os.environ["BENCH_DIR"]) / "models.json").read_text())["pocket"]["shefowl/pocket-tts-polish-6l"]["config"]
TTSModel.load_model(config=cfg)
print("ok")
PYEOF
echo "== setup done"
