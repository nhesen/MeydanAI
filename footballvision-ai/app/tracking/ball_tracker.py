from __future__ import annotations

from dataclasses import dataclass

from app.core.config import AppConfig
from app.core.types import BallSample, Detection, Role


@dataclass
class _Kalman2D:
    x: float
    y: float
    vx: float = 0.0
    vy: float = 0.0
    initialized: bool = False

    def predict(self, dt: float) -> tuple[float, float]:
        if not self.initialized:
            return self.x, self.y
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.vx *= 0.98
        self.vy *= 0.98
        return self.x, self.y

    def correct(self, x: float, y: float, dt: float) -> None:
        if not self.initialized:
            self.x, self.y = x, y
            self.initialized = True
            return
        if dt <= 0:
            self.x, self.y = x, y
            return
        self.vx = 0.65 * self.vx + 0.35 * ((x - self.x) / dt)
        self.vy = 0.65 * self.vy + 0.35 * ((y - self.y) / dt)
        self.x, self.y = x, y


class BallTracker:
    """Dedicated ball tracker: highest-confidence detection + Kalman fill-in."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self._filter = _Kalman2D(0.0, 0.0)
        self._misses = 0
        self._last_time: float | None = None
        self.samples: list[BallSample] = []

    def update(
        self,
        detections: list[Detection],
        frame: int,
        time_s: float,
        to_world,
    ) -> BallSample:
        balls = [item for item in detections if item.role is Role.BALL]
        dt = 0.04 if self._last_time is None else max(1e-3, time_s - self._last_time)
        predicted = self._filter.predict(dt)
        if balls:
            chosen = max(balls, key=lambda item: item.confidence * max(item.bbox.area(), 1.0) ** 0.15)
            pixel = (chosen.bbox.cx, chosen.bbox.cy)
            world = to_world(*pixel)
            self._filter.correct(pixel[0], pixel[1], dt)
            self._misses = 0
            sample = BallSample(
                frame=frame,
                time_s=time_s,
                pixel=pixel,
                world=world,
                confidence=chosen.confidence,
                interpolated=False,
                velocity_mps=self._velocity(world, time_s),
            )
        elif self._filter.initialized and self._misses < self.config.tracking.ball_max_gap_frames:
            self._misses += 1
            pixel = predicted
            world = to_world(*pixel)
            sample = BallSample(
                frame=frame,
                time_s=time_s,
                pixel=pixel,
                world=world,
                confidence=max(0.15, 0.55 - 0.04 * self._misses),
                interpolated=True,
                velocity_mps=self._velocity(world, time_s),
            )
        else:
            self._misses += 1
            if self._misses > self.config.tracking.ball_max_gap_frames:
                self._filter = _Kalman2D(0.0, 0.0)
            sample = BallSample(
                frame=frame,
                time_s=time_s,
                pixel=None,
                world=None,
                confidence=0.0,
                interpolated=False,
            )
        self._last_time = time_s
        self.samples.append(sample)
        return sample

    def _velocity(self, world: tuple[float, float] | None, time_s: float) -> tuple[float, float] | None:
        if world is None:
            return None
        previous = next((item for item in reversed(self.samples) if item.world is not None), None)
        if previous is None or previous.world is None:
            return None
        dt = time_s - previous.time_s
        if dt <= 0:
            return None
        return (world[0] - previous.world[0]) / dt, (world[1] - previous.world[1]) / dt
