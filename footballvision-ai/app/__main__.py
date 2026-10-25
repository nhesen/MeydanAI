from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.core.config import load_config, with_video_calibration
from app.pipeline import analyze_video


def main() -> None:
    parser = argparse.ArgumentParser(description="FootballVision AI match analyzer")
    parser.add_argument("--video", required=True)
    parser.add_argument("--output", default="var/local-run")
    parser.add_argument("--config", default="configs/config.yaml")
    parser.add_argument("--calibration-json", type=Path)
    args = parser.parse_args()
    config = load_config(args.config)
    if args.calibration_json is not None:
        config = with_video_calibration(config, json.loads(args.calibration_json.read_text(encoding="utf-8")))

    def progress(percent: int, message: str) -> None:
        print(
            json.dumps({"progress": percent, "message": message}, ensure_ascii=True),
            flush=True,
        )

    result = analyze_video(args.video, args.output, config, progress=progress)
    print(f"score {result.score[0]}-{result.score[1]}")
    print(f"players {len(result.players)} events {len(result.events)}")
    print(f"report {result.report_html}")
    print(f"tables {result.extras.get('tables')}")


if __name__ == "__main__":
    Path("var").mkdir(exist_ok=True)
    main()
