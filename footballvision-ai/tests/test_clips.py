import cv2
import numpy as np
import pytest

from app.core.types import EventType, MatchEvent, TeamId
from app.highlights import clips


def test_failed_clip_extraction_is_not_advertised(config, tmp_path, monkeypatch):
    event = MatchEvent(EventType.SHOT, 1, 25, 1, TeamId.HOME)
    monkeypatch.setattr(clips, "_extract", lambda *args: False)
    found = clips.cut_highlights(
        tmp_path / "absent.mp4", [event], tmp_path / "out", config, 25
    )
    assert found == []
    assert event.clip_path is None


def test_highlight_is_decodable_and_has_requested_duration(tmp_path):
    source = tmp_path / "source.mp4"
    dest = tmp_path / "clip.mp4"
    writer = cv2.VideoWriter(
        str(source), cv2.VideoWriter_fourcc(*"mp4v"), 10, (160, 100)
    )
    assert writer.isOpened()
    for index in range(40):
        frame = np.zeros((100, 160, 3), dtype=np.uint8)
        cv2.rectangle(frame, (index * 2, 20), (index * 2 + 20, 60), (100, 200, 250), -1)
        writer.write(frame)
    writer.release()
    assert clips._extract(source, dest, 1.0, 2.0, 10)
    cap = cv2.VideoCapture(str(dest))
    try:
        assert cap.isOpened()
        assert cap.read()[0]
        duration = cap.get(cv2.CAP_PROP_FRAME_COUNT) / cap.get(cv2.CAP_PROP_FPS)
        assert duration == pytest.approx(1.0, abs=0.15)
    finally:
        cap.release()
