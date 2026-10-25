from __future__ import annotations

from html import escape
from pathlib import Path

from app.core.types import MatchResult, TeamId


def write_html_report(path: Path, result: MatchResult) -> str:
    home = next((item for item in result.teams if item.team is TeamId.HOME), None)
    away = next((item for item in result.teams if item.team is TeamId.AWAY), None)
    leaders = result.extras.get("tables")
    possession = result.extras.get("possession", {})
    analysis = result.extras.get("analysis", {})
    calibration_note = (
        f"Kalibrasiya: {escape(str(analysis.get('calibration_source', 'manual')))}. "
        f"Etibarlı kadrlar: {float(analysis.get('calibration_coverage', 1))*100:.1f}%. "
        "Məsafə və sürət yalnız yoxlanmış fasiləsiz müşahidələrdə ölçülür. Oyun hadisələri təsdiq tələb edən AI təxminləridir."
        if result.calibrated else
        "Meydan koordinatları nisbidir. Məsafə, sürət və fiziki oyun hadisələri üçün etibarlı kalibrasiya yoxdur."
    )
    rows = "\n".join(
        f"<tr><td>{p.track_id}</td><td>{escape(p.name or '')}</td><td>{p.team.value}</td>"
        f"<td>{p.distance_m or '—'}</td><td>{p.max_speed_kmh or '—'}</td>"
        f"<td>{p.passes}</td><td>{p.pass_accuracy or '—'}</td><td>{p.shots}</td>"
        f"<td>{p.goals}</td><td>{'—' if p.rating is None else p.rating}</td></tr>"
        for p in result.players
    )
    events = "".join(
        f"<li>{event.time_s:.1f}s · {event.event_type.value} · player {event.player_id} "
        f"(conf {event.confidence:.2f})</li>"
        for event in result.events[:40]
    )
    html = f"""<!doctype html>
<html lang="az"><head><meta charset="utf-8"><title>FootballVision AI report</title>
<style>
body {{ font-family: Segoe UI, sans-serif; background:#0f141a; color:#eef3f8; margin:24px; }}
h1,h2 {{ color:#fff; }}
.score {{ font-size:42px; font-weight:700; }}
table {{ border-collapse:collapse; width:100%; background:#18222c; }}
td,th {{ border:1px solid #2a3946; padding:8px; text-align:left; }}
.card {{ background:#18222c; padding:16px; border-radius:12px; margin:16px 0; }}
img {{ max-width:48%; border-radius:8px; }}
</style></head>
<body>
<h1>FootballVision AI</h1>
<p>{escape(result.home_name)} vs {escape(result.away_name)} · {result.duration_s:.0f}s · meydan {result.pitch_length_m}×{result.pitch_width_m} m</p>
<p>{calibration_note}</p>
<div class="score">{result.score[0]} - {result.score[1]}</div>
<div class="card">
  <h2>Komanda</h2>
  <p>Possession: home {possession.get("home", 0)}% · away {possession.get("away", 0)}%</p>
  <p>Home shots {getattr(home, "shots", 0)} ({getattr(home, "shots_on_target", 0)} on target),
     xG {getattr(home, "xg", None) if getattr(home, "xg", None) is not None else "—"},
     big chances {getattr(home, "big_chances", 0)}, saves {getattr(home, "saves", 0)},
     corners {getattr(home, "corners", 0)}, goal kicks {getattr(home, "goal_kicks", 0)},
     posts {getattr(home, "woodwork", 0)}, fouls —,
     passes {getattr(home, "passes", 0)} ({getattr(home, "pass_accuracy", "—")}%)</p>
  <p>Away shots {getattr(away, "shots", 0)} ({getattr(away, "shots_on_target", 0)} on target),
     xG {getattr(away, "xg", None) if getattr(away, "xg", None) is not None else "—"},
     big chances {getattr(away, "big_chances", 0)}, saves {getattr(away, "saves", 0)},
     corners {getattr(away, "corners", 0)}, goal kicks {getattr(away, "goal_kicks", 0)},
     posts {getattr(away, "woodwork", 0)}, fouls —,
     passes {getattr(away, "passes", 0)} ({getattr(away, "pass_accuracy", "—")}%)</p>
</div>
<div class="card">
  <h2>Oyunçular</h2>
  <table>
    <tr><th>ID</th><th>Ad</th><th>Komanda</th><th>Məsafə m</th><th>Max km/h</th>
    <th>Pas</th><th>Pas %</th><th>Şut</th><th>Qol</th><th>Reytinq</th></tr>
    {rows}
  </table>
</div>
<div class="card">
  <h2>Heatmap</h2>
  <img src="heatmaps/home.png" alt="home heatmap">
  <img src="heatmaps/away.png" alt="away heatmap">
</div>
<div class="card">
  <h2>Vacib anlar</h2>
  <ul>{events}</ul>
</div>
<p>Leaders file: {leaders}</p>
</body></html>
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    return str(path)
