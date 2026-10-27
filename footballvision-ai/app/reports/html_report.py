from __future__ import annotations

from collections import Counter
from html import escape
from pathlib import Path

from app.analytics.stats import _count
from app.core.types import EventType, MatchEvent, MatchResult, PlayerStats, TeamId


def _actions(player: PlayerStats) -> int:
    return (
        player.passes
        + player.tackles
        + player.interceptions
        + player.turnovers
        + player.recoveries
    )


def _shown_players(players: list[PlayerStats]) -> tuple[list[PlayerStats], int]:
    """List the tracks that actually received a counted action."""
    ranked = sorted(
        players,
        key=lambda item: (_actions(item), item.active_seconds or 0.0),
        reverse=True,
    )
    visible = [item for item in ranked if _actions(item) > 0]
    return visible, len(players) - len(visible)


def _team_passes(events: list[MatchEvent], team: TeamId) -> tuple[int, int]:
    owned = [event for event in events if event.team is team]
    successful = _count(owned, EventType.SUCCESSFUL_PASS)
    failed = _count(owned, EventType.FAILED_PASS)
    return successful + failed, successful


def write_html_report(path: Path, result: MatchResult) -> str:
    home = next((item for item in result.teams if item.team is TeamId.HOME), None)
    away = next((item for item in result.teams if item.team is TeamId.AWAY), None)
    possession = result.extras.get("possession", {})
    analysis = result.extras.get("analysis", {})
    calibration_note = (
        f"Kalibrasiya: {escape(str(analysis.get('calibration_source', 'manual')))}. "
        f"Etibarlı kadrlar: {float(analysis.get('calibration_coverage', 1)) * 100:.1f}%. "
        "Məsafə və sürət yalnız yoxlanmış fasiləsiz müşahidələrdə ölçülür."
        if result.calibrated
        else "Meydan ölçülməyib. Məsafə, sürət, şut və qol yazılmır. "
        "Aşağıdakı pas və müdaxilələr şəkil üzərindən tapılıb, rəsmi hesab deyil."
    )
    visible, hidden = _shown_players(result.players)
    rows = "\n".join(
        f"<tr><td>{player.track_id}</td><td>{escape(player.name or '')}</td>"
        f"<td>{player.team.value}</td><td>{player.active_seconds or '—'}</td>"
        f"<td>{player.passes}</td><td>{player.successful_passes}</td>"
        f"<td>{player.tackles}</td><td>{player.interceptions}</td>"
        f"<td>{player.turnovers}</td><td>{player.recoveries}</td></tr>"
        for player in visible
    )
    counts = Counter(event.event_type for event in result.events)
    summary = "".join(
        f"<li>{escape(kind.value)}: {total}</li>"
        for kind, total in sorted(counts.items(), key=lambda item: item[0].value)
    )
    events = "".join(
        f"<li>{event.time_s:.1f}s · {escape(event.event_type.value)} · player {event.player_id} "
        f"(conf {event.confidence:.2f})</li>"
        for event in result.events[:40]
    )
    home_total, home_ok = _team_passes(result.events, TeamId.HOME)
    away_total, away_ok = _team_passes(result.events, TeamId.AWAY)
    home_accuracy = "—" if not home_total else round(100.0 * home_ok / home_total, 1)
    away_accuracy = "—" if not away_total else round(100.0 * away_ok / away_total, 1)
    hidden_note = (
        f"<p>{hidden} izdə sayılan hadisə yoxdur, ona görə cədvəldə görünmür.</p>"
        if hidden
        else ""
    )
    none_share = possession.get("none")
    none_note = f" · top sahibsiz {none_share}%" if none_share is not None else ""
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
  <p>Possession: home {possession.get("home", 0)}% · away {possession.get("away", 0)}%{none_note}</p>
  <p>Home shots {getattr(home, "shots", 0)} ({getattr(home, "shots_on_target", 0)} on target),
     xG {getattr(home, "xg", None) if getattr(home, "xg", None) is not None else "—"},
     passes {home_total} ({home_accuracy}%),
     tackles {_count([event for event in result.events if event.team is TeamId.HOME], EventType.TACKLE)}</p>
  <p>Away shots {getattr(away, "shots", 0)} ({getattr(away, "shots_on_target", 0)} on target),
     xG {getattr(away, "xg", None) if getattr(away, "xg", None) is not None else "—"},
     passes {away_total} ({away_accuracy}%),
     tackles {_count([event for event in result.events if event.team is TeamId.AWAY], EventType.TACKLE)}</p>
</div>
<div class="card">
  <h2>Tapılan hadisələr</h2>
  <ul>{summary}</ul>
</div>
<div class="card">
  <h2>Oyunçular</h2>
  {hidden_note}
  <table>
    <tr><th>ID</th><th>Ad</th><th>Komanda</th><th>Müddət s</th>
    <th>Pas</th><th>Uğurlu pas</th><th>Müdaxilə</th><th>Kəsilmə</th>
    <th>Top itkisi</th><th>Geri alma</th></tr>
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
</body></html>
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    return str(path)
