from pathlib import Path

from app.core.analytics_bounds import FOOTBALL_EVENT_TYPES, sanitize_events
from app.schemas.ingestion import AnalyticsEventIngest
from app.worker.footballvision import load_motion_results


def test_load_motion_results_from_exported_tables(tmp_path: Path) -> None:
    (tmp_path / "tracks.json").write_text(
        """
        {
          "1": {
            "team": "home",
            "role": "player",
            "positions": [
              {"timestamp_ms": 0, "x": 0.2, "y": 0.5},
              {"timestamp_ms": 1000, "x": 0.3, "y": 0.5},
              {"timestamp_ms": 2000, "x": 0.4, "y": 0.5}
            ]
          }
        }
        """,
        encoding="utf-8",
    )
    (tmp_path / "player_stats.csv").write_text(
        "player_id,distance_m,avg_speed_kmh,max_speed_kmh,sprint_count,active_seconds,rating\n"
        "1,120.5,8.1,22.0,2,90,7.4\n",
        encoding="utf-8",
    )
    (tmp_path / "events.csv").write_text(
        "event_type,time_s,frame,player_id,team,related_player_id,x,y,confidence,clip_path\n"
        "successful_pass,1.2,30,1,home,2,12,10,0.8,\n"
        "shot,4.0,100,1,home,,24,10,0.7,\n"
        "goal,4.4,110,1,home,,40,10,0.86,\n",
        encoding="utf-8",
    )
    tracks = load_motion_results(tmp_path)
    assert len(tracks) == 1
    assert tracks[0].distance_m == 120.5
    assert tracks[0].sprint_count == 2
    kinds = {item[0] for item in tracks[0].events}
    assert kinds == {"successful_pass", "shot", "goal"}


def test_football_events_survive_sanitizer() -> None:
    events = [
        AnalyticsEventIngest(event_type="goal", timestamp_ms=1200, title="Goal"),
        AnalyticsEventIngest(event_type="successful_pass", timestamp_ms=400, title="Pass"),
        AnalyticsEventIngest(event_type="sprint", timestamp_ms=800, speed_kmh=26, title="Sprint"),
    ]
    kept = sanitize_events(events)
    assert [item.event_type for item in kept] == ["successful_pass", "sprint", "goal"]
    assert "goal" in FOOTBALL_EVENT_TYPES
