"use client";

import { useEffect, useMemo, useRef, useState, type KeyboardEvent, type MouseEvent } from "react";

import { Button } from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import { calibrationError, RELATIVE_CALIBRATION } from "@/lib/calibration";
import type { UploadCalibrationConfig } from "@/types/api";

const CORNERS = ["Near-left", "Near-right", "Far-right", "Far-left"];
const selectClass = "h-11 w-full rounded-xl border border-border bg-white px-3 text-sm";

export function PitchCalibrationEditor({ file, disabled, onChange }: {
  file: File;
  disabled: boolean;
  onChange: (config: UploadCalibrationConfig | null) => void;
}) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [previewUrl, setPreviewUrl] = useState("");
  const [ready, setReady] = useState(false);
  const [previewError, setPreviewError] = useState(false);
  const [mode, setMode] = useState<UploadCalibrationConfig["mode"]>("relative");
  const [pitchMode, setPitchMode] = useState<UploadCalibrationConfig["pitch_mode"]>("hali_saha");
  const [cameraMode, setCameraMode] = useState<UploadCalibrationConfig["camera_mode"]>("fixed");
  const [length, setLength] = useState("40");
  const [width, setWidth] = useState("20");
  const [points, setPoints] = useState<[number, number][]>([]);
  const [keyboardActive, setKeyboardActive] = useState(false);
  const [cursor, setCursor] = useState<[number, number]>([0.5, 0.5]);

  useEffect(() => {
    const url = URL.createObjectURL(file);
    let disposed = false;
    void Promise.resolve().then(() => { if (!disposed) setPreviewUrl(url); });
    return () => { disposed = true; URL.revokeObjectURL(url); };
  }, [file]);

  const config = useMemo<UploadCalibrationConfig>(() => ({
    mode, pitch_mode: mode === "automatic" ? "11v11" : pitchMode,
    camera_mode: cameraMode,
    length_m: mode === "relative" ? RELATIVE_CALIBRATION.length_m : Number(length),
    width_m: mode === "relative" ? RELATIVE_CALIBRATION.width_m : Number(width),
    points: mode === "manual" ? points : [],
  }), [mode, pitchMode, cameraMode, length, width, points]);
  const problem = calibrationError(config) ?? (mode === "manual" && !ready ? "Wait for the first frame to load before marking corners." : null);
  useEffect(() => { onChange(problem ? null : config); }, [config, problem, onChange]);

  function addPoint(point: [number, number]) {
    if (disabled || !ready || points.length >= 4) return;
    setPoints((current) => [...current, point]);
  }
  function selectPoint(event: MouseEvent<HTMLDivElement>) {
    const bounds = event.currentTarget.getBoundingClientRect();
    addPoint([
      Math.min(1, Math.max(0, (event.clientX - bounds.left) / bounds.width)),
      Math.min(1, Math.max(0, (event.clientY - bounds.top) / bounds.height)),
    ]);
  }
  function keyboardPoint(event: KeyboardEvent<HTMLDivElement>) {
    if (disabled || !ready) return;
    const delta = event.shiftKey ? 0.02 : 0.005;
    if (event.key === "Enter" || event.key === " ") { event.preventDefault(); addPoint(cursor); }
    if (["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(event.key)) {
      event.preventDefault();
      setCursor(([x, y]) => [
        Math.min(1, Math.max(0, x + (event.key === "ArrowRight" ? delta : event.key === "ArrowLeft" ? -delta : 0))),
        Math.min(1, Math.max(0, y + (event.key === "ArrowDown" ? delta : event.key === "ArrowUp" ? -delta : 0))),
      ]);
    }
  }

  return (
    <section className="mt-5 space-y-4 rounded-xl border border-border bg-subtle/40 p-4" aria-label="Pitch calibration settings">
      <div>
        <h3 className="font-semibold text-slate-950">Pitch calibration</h3>
        <p className="mt-1 text-sm leading-6 text-slate-600">Most videos are halı saha, about 40 m by 20 m, with 3 m goals. Enter the real metres for this pitch. A full 11-a-side pitch is the exception, and only that pitch can use automatic keypoints. Passes still appear without calibration. Distance, shots and goals appear after the visible pitch is measured.</p>
      </div>
      <div className="grid gap-4 sm:grid-cols-3">
        <Field htmlFor="calibration-mode" label="Measurement mode">
          <select className={selectClass} disabled={disabled} id="calibration-mode" value={mode} onChange={(event) => {
            const next = event.target.value as UploadCalibrationConfig["mode"];
            setMode(next);
            if (next === "manual") setCameraMode("fixed");
            if (next === "automatic") {
              setPitchMode("11v11");
              setLength("105");
              setWidth("68");
            }
            if (next === "manual" && pitchMode !== "11v11") {
              setLength("40");
              setWidth("20");
            }
          }}>
            <option value="relative">Relative movement only</option>
            <option value="manual">Manual four-corner calibration</option>
            <option value="automatic">Automatic keypoints, 11-a-side only</option>
          </select>
        </Field>
        <Field htmlFor="calibration-pitch" label="Pitch type">
          <select className={selectClass} disabled={disabled || mode === "automatic"} id="calibration-pitch" value={mode === "automatic" ? "11v11" : pitchMode} onChange={(event) => {
            const next = event.target.value as UploadCalibrationConfig["pitch_mode"];
            setPitchMode(next);
            if (next === "11v11") { setLength("105"); setWidth("68"); }
            else { setLength("40"); setWidth("20"); }
          }}>
            <option value="hali_saha">Small-sided / halı saha</option><option value="11v11">11-a-side</option><option value="futsal">Futsal</option>
          </select>
        </Field>
        <Field htmlFor="calibration-camera" label="Camera">
          <select className={selectClass} disabled={disabled || mode === "manual"} id="calibration-camera" value={cameraMode} onChange={(event) => setCameraMode(event.target.value as UploadCalibrationConfig["camera_mode"])}>
            <option value="fixed">Fixed camera</option><option value="broadcast">Moving / broadcast camera</option>
          </select>
        </Field>
      </div>
      {mode !== "relative" ? (
        <div className="grid gap-4 sm:grid-cols-2">
          <Field htmlFor="pitch-length" label="Actual pitch length (m)" hint="Along the touchline">
            <Input disabled={disabled} id="pitch-length" type="number" min={mode === "automatic" ? 90 : 5} max={mode === "automatic" ? 120 : 130} step="0.1" placeholder={pitchMode === "11v11" ? "105" : "40"} value={length} onChange={(event) => setLength(event.target.value)} />
          </Field>
          <Field htmlFor="pitch-width" label="Actual pitch width (m)" hint="Along the goal line">
            <Input disabled={disabled} id="pitch-width" type="number" min={mode === "automatic" ? 45 : 5} max={90} step="0.1" placeholder={pitchMode === "11v11" ? "68" : "20"} value={width} onChange={(event) => setWidth(event.target.value)} />
          </Field>
        </div>
      ) : null}
      {mode === "automatic" ? <p className="rounded-xl bg-brand-50 p-3 text-sm leading-6 text-brand-900">Automatic calibration uses the standard 11-a-side marking template. If the pitch cannot be calibrated confidently, results fall back to relative movement with no distance or speed values.</p> : null}
      {mode === "manual" ? (
        <div className="space-y-3">
          <p className="text-sm leading-6 text-slate-600">Mark the first frame in this order: <strong>1 near-left → 2 near-right → 3 far-right → 4 far-left.</strong> The near edge follows the touchline (pitch length). All four corners must be visible. Do not guess a hidden corner; choose relative mode instead. Manual calibration is for a fixed camera throughout the clip.</p>
          <div className="relative overflow-hidden rounded-xl bg-slate-950 outline-offset-4 focus-visible:outline-2 focus-visible:outline-brand-700" role="button" tabIndex={disabled ? -1 : 0} aria-disabled={disabled || !ready || points.length === 4} aria-label={points.length < 4 ? `Mark corner ${points.length + 1}: ${CORNERS[points.length]}. Arrow keys move the target, Enter marks the corner.` : "All four corners are marked"} onClick={selectPoint} onKeyDown={keyboardPoint} onFocus={() => setKeyboardActive(true)} onBlur={() => setKeyboardActive(false)}>
            {previewUrl ? <video className="block w-full" src={previewUrl} ref={videoRef} muted playsInline preload="auto" onLoadedData={() => { videoRef.current?.pause(); setReady(true); }} onError={() => { setPreviewError(true); setReady(false); }} /> : <div className="aspect-video" />}
            <svg className="pointer-events-none absolute inset-0 h-full w-full" viewBox="0 0 1000 1000" preserveAspectRatio="none" aria-hidden="true">
              {points.length > 1 ? <polyline points={[...points, ...(points.length === 4 ? [points[0]] : [])].map(([x, y]) => `${x * 1000},${y * 1000}`).join(" ")} fill={points.length === 4 ? "#22c55e26" : "none"} stroke="#86efac" strokeWidth="3" vectorEffect="non-scaling-stroke" /> : null}
            </svg>
            {points.map(([x, y], index) => <span key={index} className="pointer-events-none absolute grid size-7 -translate-x-1/2 -translate-y-1/2 place-items-center rounded-full border-2 border-white bg-brand-700 text-xs font-bold text-white shadow-sm" style={{ left: `${x * 100}%`, top: `${y * 100}%` }}>{index + 1}</span>)}
            {keyboardActive && points.length < 4 ? <span className="pointer-events-none absolute size-5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-yellow-300" style={{ left: `${cursor[0] * 100}%`, top: `${cursor[1] * 100}%` }} /> : null}
          </div>
          <div className="flex flex-wrap items-center gap-3"><span className="text-sm text-slate-600" role="status">{points.length}/4 corners selected · First frame (00:00)</span><Button disabled={disabled || points.length === 0} size="sm" variant="secondary" onClick={() => setPoints((current) => current.slice(0, -1))}>Undo corner</Button><Button disabled={disabled || points.length === 0} size="sm" variant="ghost" onClick={() => setPoints([])}>Reset corners</Button></div>
          <p className="text-xs text-slate-500">Keyboard: focus the frame, use arrow keys to move the target and Enter to mark a corner. Shift moves faster. This preview stays on your device until you upload.</p>
          {previewError ? <p role="alert" className="text-sm text-danger-700">This browser cannot preview the selected video. Use a supported MP4 or choose relative mode; do not calibrate an unreadable frame.</p> : null}
        </div>
      ) : null}
      {problem ? <p className="text-sm text-warning-800" role="status">{problem}</p> : mode !== "relative" ? <p className="text-sm font-semibold text-brand-800" role="status">Calibration settings are ready to upload.</p> : null}
    </section>
  );
}
