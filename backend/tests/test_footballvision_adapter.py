import json
from pathlib import Path

from app.core.analytics_bounds import FOOTBALL_EVENT_TYPES, sanitize_events
from app.schemas.ingestion import AnalyticsEventIngest
from app.worker.footballvision import load_motion_results


def test_load_motion_results_from_exported_tables(tmp_path: Path) -> None:
    (tmp_path / "match_summary.json").write_text(
        json.dumps(
            {
                "calibrated": True,
                "calibration_coverage": 0.95,
                "calibration_source": "manual",
                "pitch_length_m": 40,
                "pitch_width_m": 20,
                "frame_width": 1920,
                "frame_height": 1080,
                "ball_observed_coverage": 0.92,
                "sprint_definition": {"threshold_kmh": 24, "minimum_duration_s": 1},
            }
        ),
        encoding="utf-8",
    )
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
        "player_id,distance_m,avg_speed_kmh,max_speed_kmh,sprint_count,active_seconds,measured_seconds,rating\n"
        "1,120.5,8.1,22.0,2,90,90,7.4\n",
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
    assert tracks[0].frame_width == 1920
    assert tracks[0].team == "home"
    assert tracks[0].calibration["pitch_length_m"] == 40
    assert tracks[0].calibration["transform_metadata"]["ball_observed_coverage"] == 0.92
    assert tracks[0].calibration["transform_metadata"]["sprint_threshold_kmh"] == 24
    from app.schemas.ingestion import CalibrationMetadata

    CalibrationMetadata.model_validate(tracks[0].calibration)
    assert tracks[0].peak_speed_at_ms is None
    kinds = {item[0] for item in tracks[0].events}
    assert kinds == {"successful_pass", "shot", "goal"}
    assert all(item[3].startswith("Possible ") for item in tracks[0].events)

    # Unknown calibration must remain unknown, even if a legacy export has numbers.
    (tmp_path / "match_summary.json").unlink()
    uncalibrated = load_motion_results(tmp_path)[0]
    assert uncalibrated.distance_m is None
    assert uncalibrated.avg_speed_kmh is None
    assert uncalibrated.max_speed_kmh is None
    assert uncalibrated.sprint_count is None
    assert uncalibrated.intensity == []


def test_football_events_survive_sanitizer() -> None:
    events = [
        AnalyticsEventIngest(event_type="goal", timestamp_ms=1200, title="Goal"),
        AnalyticsEventIngest(event_type="successful_pass", timestamp_ms=400, title="Pass"),
        AnalyticsEventIngest(event_type="sprint", timestamp_ms=800, speed_kmh=26, title="Sprint"),
    ]
    kept = sanitize_events(events)
    assert [item.event_type for item in kept] == ["successful_pass", "sprint", "goal"]
    assert "goal" in FOOTBALL_EVENT_TYPES
    assert {"big_chance", "goal_kick", "woodwork"} <= FOOTBALL_EVENT_TYPES


def test_estimated_events_are_not_ingested_and_xg_stays_on_the_shot(tmp_path: Path) -> None:
    (tmp_path / "match_summary.json").write_text(
        json.dumps(
            {
                "calibrated": True,
                "calibration_coverage": 0.95,
                "pitch_length_m": 40,
                "pitch_width_m": 20,
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "tracks.json").write_text(
        '{"1": {"role": "player", "team": "home", "positions": ['
        '{"timestamp_ms": 0, "x": 0.2, "y": 0.4, "calibrated": true},'
        '{"timestamp_ms": 1000, "x": 0.3, "y": 0.4, "calibrated": true}]}}',
        encoding="utf-8",
    )
    (tmp_path / "player_stats.csv").write_text(
        "player_id,distance_m,avg_speed_kmh,max_speed_kmh,sprint_count,active_seconds,measured_seconds,rating\n"
        "1,20,5,10,0,10,30,6\n",
        encoding="utf-8",
    )
    (tmp_path / "events.csv").write_text(
        "event_type,time_s,frame,player_id,team,extra\n"
        'pass,1.0,25,1,home,"{""estimated"": true}"\n'
        'shot,4.0,100,1,home,"{""xg"": 0.42}"\n'
        'big_chance,4.0,100,1,home,"{""xg"": 0.42}"\n',
        encoding="utf-8",
    )
    tracks = load_motion_results(tmp_path)
    titles = {item[0]: item[3] for item in tracks[0].events}
    assert titles["pass"] == "Possible pass"
    assert titles["shot"] == "Possible shot · xG 0.42"
    assert titles["big_chance"] == "Possible big chance · xG 0.42"
    AnalyticsEventIngest(event_type="big_chance", timestamp_ms=4000, title=titles["big_chance"])
    AnalyticsEventIngest(event_type="goal_kick", timestamp_ms=1000, title="Possible goal kick")
    AnalyticsEventIngest(event_type="woodwork", timestamp_ms=2000, title="Possible woodwork")


def test_short_or_sparse_calibration_publishes_no_speed(tmp_path: Path) -> None:
    (tmp_path / "match_summary.json").write_text(
        json.dumps(
            {
                "calibrated": True,
                "calibration_coverage": 0.4545,
                "pitch_length_m": 105,
                "pitch_width_m": 68,
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "tracks.json").write_text(
        '{"9": {"role": "player", "team": "away", "positions": ['
        '{"timestamp_ms": 0, "x": 0.2, "y": 0.4, "calibrated": true},'
        '{"timestamp_ms": 1000, "x": 0.8, "y": 0.4, "calibrated": true}]}}',
        encoding="utf-8",
    )
    (tmp_path / "player_stats.csv").write_text(
        "player_id,distance_m,avg_speed_kmh,max_speed_kmh,sprint_count,measured_seconds,rating\n"
        "9,40,18,32.0,1,3.16,7.1\n",
        encoding="utf-8",
    )
    (tmp_path / "events.csv").write_text(
        "event_type,time_s,player_id,extra\nshot,1.0,9,{}\n",
        encoding="utf-8",
    )
    track = load_motion_results(tmp_path)[0]
    assert track.distance_m is None
    assert track.max_speed_kmh is None
    assert track.avg_speed_kmh is None
    assert track.sprint_count is None
    assert track.rating is None
    assert track.events == []
