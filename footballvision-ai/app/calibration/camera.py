from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

Array = np.ndarray


@dataclass
class CameraCompensator:
    """Optical-flow camera motion, with replay-cut reset.

    mode "auto" keeps monitoring for panning after an initial static shot.
    Feature loss preserves the reference offset; a scene cut resets it.
    """

    enabled: bool = False
    mode: str = "off"
    previous: Array | None = None
    mask: Array | None = None
    current_to_reference: Array = field(
        default_factory=lambda: np.eye(3, dtype=np.float64)
    )
    valid: bool = True
    reason: str | None = None
    scene_cut: bool = False
    _probe_left: int = 0
    _shifts: list[float] = field(default_factory=list)
    _hist: Array | None = None
    _dx: float = 0.0
    _dy: float = 0.0
    _points: Array | None = None

    def __post_init__(self) -> None:
        if self.mode == "auto" and not self.enabled:
            self._probe_left = 12

    def warp_point(self, x: float, y: float, scale: float = 1.0) -> tuple[float, float]:
        if not self.enabled or not self.valid:
            return x, y
        return x - self._dx, y - self._dy

    def update(
        self, frame: Array, boxes: list[tuple[float, float, float, float]]
    ) -> bool:
        self.scene_cut = False
        import cv2

        height, width = frame.shape[:2]
        scale = min(1.0, 640 / max(width, 1))
        small = cv2.resize(
            frame, (max(1, round(width * scale)), max(1, round(height * scale)))
        )
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        edges = np.zeros(gray.shape, np.uint8)
        band = max(8, gray.shape[1] // 16)
        edges[:, :band] = 255
        edges[:, gray.shape[1] - band :] = 255
        for x1, y1, x2, y2 in boxes:
            cv2.rectangle(
                edges,
                (round(x1 * scale) - 5, round(y1 * scale) - 5),
                (round(x2 * scale) + 5, round(y2 * scale) + 5),
                0,
                -1,
            )
        hist = cv2.calcHist([gray], [0], None, [16], [0, 256]).ravel()
        if self._hist is not None:
            corr = float(
                np.dot(self._hist, hist)
                / (np.linalg.norm(self._hist) * np.linalg.norm(hist) + 1e-6)
            )
            if corr < 0.82:
                self.scene_cut = True
                self._reset_motion()
                self.previous, self._hist = gray, hist
                return True
        self._hist = hist
        if self.mode == "off" and not self.enabled:
            return True
        if self.previous is None or self._points is None:
            self._points = self._edge_points(gray, edges)
            self.previous = gray
            return True
        moved, status, _ = cv2.calcOpticalFlowPyrLK(
            self.previous,
            gray,
            self._points,
            None,
            winSize=(15, 15),
            maxLevel=2,
            criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 10, 0.03),
        )
        if moved is None or status is None:
            return self._recover(gray, edges, "optical_flow_failed")
        good = status.ravel() == 1
        source, destination = (
            self._points.reshape(-1, 2)[good],
            moved.reshape(-1, 2)[good],
        )
        if len(source) < 8:
            return self._recover(gray, edges, "insufficient_consistent_features")
        delta = (destination - source) / max(scale, 1e-6)
        dx = float(np.median(delta[:, 0]))
        dy = float(np.median(delta[:, 1]))
        shift = float(np.hypot(dx, dy))
        if self.mode == "auto" and shift >= 1.5:
            self.enabled = True
        if self._probe_left > 0:
            self._shifts.append(shift)
            self._probe_left -= 1
            if self._probe_left == 0:
                ordered = sorted(self._shifts)
                self.enabled = self.enabled or ordered[len(ordered) // 2] >= 1.5
        if self.enabled and shift >= 0.4:
            self._dx += dx
            self._dy += dy
        self._points = destination.reshape(-1, 1, 2).astype(np.float32)
        if shift > 5 or len(destination) < 12:
            self._points = self._edge_points(gray, edges)
        self.previous = gray
        self.valid = True
        self.reason = None
        return True

    def _edge_points(self, gray: Array, edges: Array) -> Array | None:
        import cv2

        return cv2.goodFeaturesToTrack(
            gray,
            maxCorners=80,
            qualityLevel=0.3,
            minDistance=5,
            blockSize=7,
            mask=edges,
        )

    def _recover(self, gray: Array, edges: Array, reason: str) -> bool:
        self.reason = reason
        # Keep the accumulated reference offset when background features vanish.
        # Resetting it here would create a false jump in every player trajectory.
        self._points = self._edge_points(gray, edges)
        self.previous = gray
        self.valid = True
        return False

    def _reset_motion(self) -> None:
        self._dx = 0.0
        self._dy = 0.0
        self._points = None
        self.current_to_reference = np.eye(3, dtype=np.float64)
