from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from app.core.config import AppConfig
from app.core.types import PlayerTrack, TeamId, TrackSample


def _hist_corr(a: list[float] | None, b: list[float] | None) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    left = np.asarray(a, dtype=np.float32)
    right = np.asarray(b, dtype=np.float32)
    if np.allclose(left, right):
        return 1.0
    left = left - left.mean()
    right = right - right.mean()
    denom = float(np.linalg.norm(left) * np.linalg.norm(right))
    if denom < 1e-6:
        return 0.0
    return float(np.clip(np.dot(left, right) / denom, -1.0, 1.0))


def _distance(a: TrackSample, b: TrackSample) -> float:
    if a.world is not None and b.world is not None:
        return float(np.hypot(a.world[0] - b.world[0], a.world[1] - b.world[1]))
    return float(np.hypot(a.pixel[0] - b.pixel[0], a.pixel[1] - b.pixel[1])) / 40.0


@dataclass
class IdentityRepair:
    """Merge fragmented IDs after occlusion using appearance + motion + team."""

    config: AppConfig

    def merge(self, tracks: dict[int, PlayerTrack]) -> dict[int, PlayerTrack]:
        ordered = sorted(tracks.values(), key=lambda item: item.samples[0].time_s if item.samples else 0)
        survivors: dict[int, PlayerTrack] = {}
        for track in ordered:
            if not track.samples:
                continue
            partner = self._best_partner(track, survivors)
            if partner is None:
                survivors[track.track_id] = track
                continue
            partner.samples.extend(track.samples)
            partner.samples.sort(key=lambda sample: (sample.frame, sample.time_s))
            partner.merged_from.append(track.track_id)
            if partner.team is TeamId.UNKNOWN:
                partner.team = track.team
        return survivors

    def _best_partner(self, track: PlayerTrack, survivors: dict[int, PlayerTrack]) -> PlayerTrack | None:
        first = track.samples[0]
        best: tuple[float, PlayerTrack] | None = None
        for candidate in survivors.values():
            if candidate.role != track.role:
                continue
            last = candidate.last
            if last is None:
                continue
            gap = first.time_s - last.time_s
            if gap < -0.05 or gap > self.config.tracking.lost_track_buffer / 12:
                continue
            if (
                candidate.team not in {TeamId.UNKNOWN, track.team}
                and track.team is not TeamId.UNKNOWN
            ):
                continue
            dist = _distance(last, first)
            if dist > self.config.tracking.reid_max_distance_m:
                continue
            appearance = _hist_corr(last.color_hist, first.color_hist)
            motion = max(0.0, 1.0 - dist / self.config.tracking.reid_max_distance_m)
            color = 1.0 if candidate.team == track.team and track.team is not TeamId.UNKNOWN else 0.4
            score = (
                self.config.tracking.reid_hist_weight * max(appearance, 0.0)
                + self.config.tracking.reid_motion_weight * motion
                + self.config.tracking.reid_color_weight * color
            )
            if score < 0.62:
                continue
            if best is None or score > best[0]:
                best = score, candidate
        return None if best is None else best[1]
