from __future__ import annotations

from dataclasses import dataclass

from app.core.config import AppConfig


@dataclass(frozen=True)
class PitchZones:
    length_m: float
    width_m: float
    rows: int
    cols: int
    fine_rows: int
    fine_cols: int

    @classmethod
    def from_config(cls, config: AppConfig) -> PitchZones:
        return cls(
            length_m=config.pitch.length_m,
            width_m=config.pitch.width_m,
            rows=config.pitch.grid_rows,
            cols=config.pitch.grid_cols,
            fine_rows=config.pitch.fine_grid_rows,
            fine_cols=config.pitch.fine_grid_cols,
        )

    def cell(self, x: float, y: float, *, fine: bool = False) -> str:
        rows = self.fine_rows if fine else self.rows
        cols = self.fine_cols if fine else self.cols
        col = min(cols - 1, max(0, int(x / self.length_m * cols)))
        row = min(rows - 1, max(0, int(y / self.width_m * rows)))
        prefix = "fine" if fine else "grid"
        return f"{prefix}-{row}-{col}"

    def band(self, x: float, y: float | None = None, *, attacking_home: bool = True) -> str:
        thirds = self.length_m / 3
        if attacking_home:
            if x < thirds:
                return "defense"
            if x < 2 * thirds:
                return "midfield"
            return "attack"
        if x > 2 * thirds:
            return "defense"
        if x > thirds:
            return "midfield"
        return "attack"

    def in_penalty(self, x: float, y: float, left_goal: bool) -> bool:
        box_length = min(11.0, self.length_m * 0.22)
        box_width = min(self.width_m * 0.7, max(8.0, self.width_m * 0.55))
        y0 = (self.width_m - box_width) / 2
        y1 = y0 + box_width
        if left_goal:
            return 0 <= x <= box_length and y0 <= y <= y1
        return self.length_m - box_length <= x <= self.length_m and y0 <= y <= y1

    def goal_center(self, left: bool) -> tuple[float, float]:
        return (0.0 if left else self.length_m, self.width_m / 2)

    def in_goal(self, x: float, y: float, goal_width_m: float, left: bool) -> bool:
        half = goal_width_m / 2
        cy = self.width_m / 2
        if not (cy - half - 0.3 <= y <= cy + half + 0.3):
            return False
        if left:
            return x <= 0.35
        return x >= self.length_m - 0.35
