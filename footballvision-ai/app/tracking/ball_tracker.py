from __future__ import annotations

from dataclasses import dataclass
from math import hypot

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
        self.vx += 0.35 * ((x - self.x) / dt)
        self.vy += 0.35 * ((y - self.y) / dt)
        self.x, self.y = x, y


class BallTracker:
    """Dedicated ball tracker: motion-gated detection + short, explicitly interpolated fill-in."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self._filter = _Kalman2D(0.0, 0.0)
        self._misses = 0
        self._last_time: float | None = None
        self._last_seen_frame: int | None = None
        self._cut_pending = False
        self._velocity_start = 0
        self.samples: list[BallSample] = []
        self._ball_size = 6.0

    def update(
        self,
        detections: list[Detection],
        frame: int,
        time_s: float,
        to_world,
        *,
        calibrated: bool = True,
        calibration_source: str = "manual",
    ) -> BallSample:
        balls = [item for item in detections if item.role is Role.BALL]
        dt = 0.04 if self._last_time is None else max(1e-3, time_s - self._last_time)
        predicted = self._filter.predict(dt)
        if self._filter.initialized and self._last_seen_frame is not None and frame-self._last_seen_frame <= self.config.tracking.ball_max_gap_frames:
            gate = max(40.0, self._ball_size * 4) * max(1.0, dt / .04) * (1 + min(self._misses, 4) * .1)
            balls = [item for item in balls if hypot(item.bbox.cx-predicted[0], item.bbox.cy-predicted[1]) <= gate]
        else:
            balls = [item for item in balls if item.confidence >= .35]
            self._filter = _Kalman2D(0.0, 0.0)
        if balls:
            chosen = max(
                balls,
                key=lambda item: item.confidence / (1 + hypot(item.bbox.cx-predicted[0], item.bbox.cy-predicted[1]) / max(40.0, self._ball_size*8)) if self._filter.initialized else item.confidence,
            )
            self._ball_size = max(chosen.bbox.width, chosen.bbox.height)
            pixel = (chosen.bbox.cx, chosen.bbox.cy)
            world = to_world(*pixel)
            self._filter.correct(pixel[0], pixel[1], dt)
            self._misses = 0
            self._last_seen_frame = frame
            sample = BallSample(
                frame=frame,
                time_s=time_s,
                pixel=pixel,
                world=world,
                confidence=chosen.confidence,
                interpolated=False,
                velocity_mps=self._velocity(world, time_s) if calibrated else None,
            )
        elif (
            self._filter.initialized
            and self._last_seen_frame is not None
            and frame - self._last_seen_frame
            <= self.config.tracking.ball_max_gap_frames
        ):
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
                velocity_mps=self._velocity(world, time_s) if calibrated else None,
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
        sample.scene_cut = self._cut_pending
        sample.calibrated = calibrated
        sample.calibration_source = calibration_source
        self._cut_pending = False
        self.samples.append(sample)
        return sample

    def cut(self) -> None:
        """Drop the ball path across a replay or camera cut."""
        self._filter = _Kalman2D(0.0, 0.0)
        self._misses = self.config.tracking.ball_max_gap_frames + 1
        self._last_time = None
        self._last_seen_frame = None
        self._velocity_start = len(self.samples)
        self._cut_pending = True

    def _velocity(
        self, world: tuple[float, float] | None, time_s: float
    ) -> tuple[float, float] | None:
        if world is None:
            return None
        previous = (
            self.samples[-1] if len(self.samples) > self._velocity_start else None
        )
        if previous is None or previous.world is None or not previous.calibrated:
            return None
        dt = time_s - previous.time_s
        if dt <= 0:
            return None
        return (world[0] - previous.world[0]) / dt, (world[1] - previous.world[1]) / dt
