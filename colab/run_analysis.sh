#!/usr/bin/env bash
# Run FootballVision on a RunPod GPU pod (PyTorch template, Ubuntu).
# Usage: bash run_analysis.sh /workspace/match.mp4
# Expects /workspace/footballvision-ai.zip next to the video.
set -euo pipefail

VIDEO="${1:?usage: bash run_analysis.sh /workspace/match.mp4}"
WORK="${WORK:-/workspace}"
BALL_SHA=fb37942448e7de08745e8aab148d0794f680a738ddd55e5f17abe9ab2d6313fb
BALL_URL=https://huggingface.co/martinjolif/yolo-football-ball-detection/resolve/main/yolo-football-ball-detection.pt

cd "$WORK"
apt-get update -qq && apt-get install -y -qq ffmpeg unzip zip libgl1 libglib2.0-0 >/dev/null
rm -rf footballvision-ai && unzip -q footballvision-ai.zip -d footballvision-ai
cd footballvision-ai

pip install -q -r requirements.txt pytest
mkdir -p models
curl -L -o models/football-ball-specialist.pt "$BALL_URL"
echo "$BALL_SHA  models/football-ball-specialist.pt" | sha256sum -c -

python - <<'PY'
import torch
print("GPU:", torch.cuda.get_device_name(0) if torch.cuda.is_available() else "NONE (CPU)")
PY

# A bigger GPU can afford a larger batch and image size than the 4 GB laptop defaults.
export FOOTBALLVISION_DEVICE=auto
export FOOTBALLVISION_BATCH="${FOOTBALLVISION_BATCH:-16}"
export FOOTBALLVISION_IMAGE_SIZE="${FOOTBALLVISION_IMAGE_SIZE:-960}"
export FOOTBALLVISION_RENDER=0
export FOOTBALLVISION_PLAYER_CLIPS=0

START=$(date +%s)
python -m app --video "$VIDEO" --output "$WORK/result" --config configs/config.yaml
END=$(date +%s)
echo "TOTAL_SECONDS $((END - START))"
python - "$VIDEO" <<'PY'
import sys, cv2
cap = cv2.VideoCapture(sys.argv[1])
print("video_frames", int(cap.get(cv2.CAP_PROP_FRAME_COUNT)), "fps", cap.get(cv2.CAP_PROP_FPS))
PY

cd "$WORK" && zip -qr result.zip result && echo "Download: $WORK/result.zip"
