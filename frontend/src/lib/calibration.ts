import type { UploadCalibrationConfig } from "@/types/api";

export const RELATIVE_CALIBRATION: UploadCalibrationConfig = {
  mode: "relative", pitch_mode: "hali_saha", camera_mode: "fixed",
  length_m: 40, width_m: 20, points: [],
};

export function calibrationError(config: UploadCalibrationConfig): string | null {
  if (config.mode !== "manual" && config.points.length > 0) return "Pitch corners are only used in manual calibration.";
  if (config.mode === "relative") return null;
  if (!Number.isFinite(config.length_m) || config.length_m < 5 || config.length_m > 130 ||
      !Number.isFinite(config.width_m) || config.width_m < 5 || config.width_m > 90) {
    return "Enter the actual pitch length (5–130 m) and width (5–90 m).";
  }
  if (config.mode === "automatic") {
    if (config.pitch_mode !== "11v11") return "Automatic keypoints support standard 11-a-side pitches only.";
    return config.length_m >= 90 && config.length_m <= 120 && config.width_m >= 45
      ? null : "Automatic keypoints require an actual 90–120 m × 45–90 m pitch.";
  }
  if (config.camera_mode !== "fixed") return "Manual calibration requires a fixed camera.";
  const { points } = config;
  if (points.length !== 4) return "Mark all four visible pitch corners in the indicated order.";
  if (points.some((point) => point.length !== 2 || point.some((value) => !Number.isFinite(value) || value < 0 || value > 1))) {
    return "Each pitch corner must be inside the video frame.";
  }
  const crosses = points.map((a, index) => {
    const b = points[(index + 1) % 4];
    const c = points[(index + 2) % 4];
    return (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0]);
  });
  if (!crosses.every((value) => value > 1e-6) && !crosses.every((value) => value < -1e-6)) {
    return "Corners must go around the pitch without crossing. Undo or reset the points.";
  }
  const area = Math.abs(points.reduce((sum, point, index) => {
    const next = points[(index + 1) % 4];
    return sum + point[0] * next[1] - next[0] * point[1];
  }, 0)) / 2;
  return area < 0.005 ? "The selected pitch area is too small. Use a clearer full-pitch video." : null;
}
