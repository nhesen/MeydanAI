from __future__ import annotations

import re
import uuid
from collections import defaultdict
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.domain import Highlight, Player

_CAPTION = re.compile(r"Gol:\s*(.+?)(?:\s*·\s*Asist:\s*(.+))?$", re.IGNORECASE)
_INDEX = re.compile(r"\s*\(\d+\)\s*$")


def caption_names(title: str) -> tuple[str, str | None] | None:
    found = _CAPTION.search(title or "")
    if found is None:
        return None
    scorer = _INDEX.sub("", found.group(1)).strip()
    assist_text = found.group(2)
    assist = _INDEX.sub("", assist_text).strip() if assist_text else None
    if not scorer:
        return None
    return scorer, assist or None


def fold_name(name: str) -> str:
    return name.casefold().replace("ç", "c")


@dataclass
class CaptionInvolvement:
    goals: dict[tuple[uuid.UUID, uuid.UUID], int] = field(default_factory=dict)
    assists: dict[tuple[uuid.UUID, uuid.UUID], int] = field(default_factory=dict)
    matches_with_captions: set[uuid.UUID] = field(default_factory=set)
    clips: dict[uuid.UUID, list[Highlight]] = field(default_factory=lambda: defaultdict(list))


def caption_involvement(
    session: Session,
    *,
    match_ids: set[uuid.UUID],
    player_ids: list[uuid.UUID],
) -> CaptionInvolvement:
    result = CaptionInvolvement()
    if not match_ids or not player_ids:
        return result
    players = list(session.scalars(select(Player).where(Player.id.in_(player_ids))))
    by_name = {fold_name(player.display_name): player.id for player in players}
    highlights = list(
        session.scalars(
            select(Highlight)
            .where(
                Highlight.match_id.in_(match_ids),
                Highlight.highlight_type == "goal",
            )
            .order_by(Highlight.timestamp_ms, Highlight.id)
        )
    )
    goal_counts: dict[tuple[uuid.UUID, uuid.UUID], int] = defaultdict(int)
    assist_counts: dict[tuple[uuid.UUID, uuid.UUID], int] = defaultdict(int)
    for highlight in highlights:
        parsed = caption_names(highlight.title)
        if parsed is None:
            continue
        result.matches_with_captions.add(highlight.match_id)
        scorer_name, assist_name = parsed
        scorer_id = by_name.get(fold_name(scorer_name))
        assist_id = by_name.get(fold_name(assist_name)) if assist_name else None
        if scorer_id is not None:
            goal_counts[(scorer_id, highlight.match_id)] += 1
            result.clips[scorer_id].append(highlight)
        if assist_id is not None:
            assist_counts[(assist_id, highlight.match_id)] += 1
            if assist_id != scorer_id:
                result.clips[assist_id].append(highlight)
    result.goals = dict(goal_counts)
    result.assists = dict(assist_counts)
    return result
