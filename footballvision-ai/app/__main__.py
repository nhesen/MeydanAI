from __future__ import annotations

import argparse
from pathlib import Path

from app.core.config import load_config
from app.pipeline import analyze_video


def main() -> None:
    parser = argparse.ArgumentParser(description="FootballVision AI match analyzer")
    parser.add_argument("--video", required=True)
    parser.add_argument("--output", default="var/local-run")
    parser.add_argument("--config", default="configs/config.yaml")
    args = parser.parse_args()
    config = load_config(args.config)
    result = analyze_video(args.video, args.output, config)
    print(f"score {result.score[0]}-{result.score[1]}")
    print(f"players {len(result.players)} events {len(result.events)}")
    print(f"report {result.report_html}")
    print(f"tables {result.extras.get('tables')}")


if __name__ == "__main__":
    Path("var").mkdir(exist_ok=True)
    main()
