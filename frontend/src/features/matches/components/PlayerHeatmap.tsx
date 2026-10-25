"use client";

import { useMemo } from "react";

import type { PositionSample } from "@/types/api";

interface PlayerHeatmapProps {
  samples: PositionSample[];
  processing?: boolean;
  measured?: boolean;
  lengthM?: number | null;
  widthM?: number | null;
}

interface DensityPoint {
  x: number;
  y: number;
  count: number;
  intensity: number;
}

const COLUMN_COUNT = 20;
const ROW_COUNT = 12;
const MAX_SAMPLES_FOR_DENSITY = 2500;
const NEIGHBOR_WEIGHT = 0.35;
const DIAGONAL_WEIGHT = 0.16;

export function PlayerHeatmap({
  lengthM = 40,
  measured = false,
  processing = false,
  samples,
  widthM = 20,
}: PlayerHeatmapProps) {
  const length = lengthM && lengthM > 0 ? lengthM : 40;
  const width = widthM && widthM > 0 ? widthM : 20;
  const viewHeight = (100 * width) / length;
  const fullSize = length >= 90;
  const density = useMemo(
    () => createDensity(samples, viewHeight),
    [samples, viewHeight],
  );
  const areaLabel = measured ? "pitch area" : "camera area";

  return (
    <div>
      <div
        aria-label={
          samples.length
            ? measured
              ? `Measured pitch heatmap built from ${samples.length} position samples.`
              : `Camera-position heatmap built from ${samples.length} samples. Not a measured pitch.`
            : "Heatmap without available position samples."
        }
        className="relative w-full overflow-hidden rounded-xl border border-[#1f6b34] bg-[#2f8f3e]"
        style={{ aspectRatio: `${length} / ${width}` }}
        role="img"
      >
        <svg
          aria-hidden="true"
          className="size-full"
          preserveAspectRatio="xMidYMid meet"
          viewBox={`0 0 100 ${viewHeight}`}
        >
          <defs>
            <filter id="heat-blur" x="-40%" y="-40%" width="180%" height="180%">
              <feGaussianBlur stdDeviation="2.4" />
            </filter>
          </defs>
          <rect width="100" height={viewHeight} fill="#3c9a4a" />
          <PitchMarkings fullSize={fullSize} viewHeight={viewHeight} />
          <g filter="url(#heat-blur)" opacity="0.9">
            {density.map((point) => (
              <circle
                cx={point.x}
                cy={point.y}
                fill={heatColor(point.intensity)}
                key={`${point.x}-${point.y}`}
                opacity={0.28 + point.intensity * 0.62}
                r={2.2 + point.intensity * 3.4}
              >
                <title>{`${point.count} samples in this ${areaLabel}`}</title>
              </circle>
            ))}
          </g>
        </svg>
        {samples.length === 0 ? (
          <div className="absolute inset-0 flex items-center justify-center bg-white/55 px-6 text-center">
            <p className="max-w-xs text-sm font-semibold text-slate-700">
              {processing
                ? "Heatmap is being generated."
                : "Heatmap data is not available for this player yet."}
            </p>
          </div>
        ) : null}
      </div>
      {samples.length > 0 ? (
        <div className="mt-3 flex items-center justify-end gap-2 text-xs font-semibold text-slate-500">
          <span>Lower activity</span>
          <span
            className="h-2.5 w-28 rounded-full bg-gradient-to-r from-[#2563eb] via-[#facc15] to-[#dc2626]"
            aria-hidden="true"
          />
          <span>Higher activity</span>
        </div>
      ) : null}
    </div>
  );
}

function PitchMarkings({ fullSize, viewHeight }: { fullSize: boolean; viewHeight: number }) {
  const mid = viewHeight / 2;
  const boxWidth = fullSize ? 16 : 8;
  const boxTop = fullSize ? viewHeight * 0.25 : viewHeight * 0.32;
  const boxHeight = fullSize ? viewHeight * 0.5 : viewHeight * 0.36;
  const goalDepth = fullSize ? 6 : 3.5;
  const goalTop = fullSize ? viewHeight * 0.36 : viewHeight * 0.4;
  const goalHeight = fullSize ? viewHeight * 0.28 : viewHeight * 0.2;
  return (
    <g fill="none" opacity="0.92" stroke="#f4fff6" strokeWidth="0.45">
      <rect height={viewHeight - 4} rx="0.4" width="96" x="2" y="2" />
      <line x1="50" x2="50" y1="2" y2={viewHeight - 2} />
      <circle cx="50" cy={mid} r={fullSize ? 8 : 5} />
      <circle cx="50" cy={mid} fill="#f4fff6" r="0.7" />
      <rect height={boxHeight} width={boxWidth} x="2" y={boxTop} />
      <rect height={boxHeight} width={boxWidth} x={98 - boxWidth} y={boxTop} />
      <rect height={goalHeight} width={goalDepth} x="2" y={goalTop} />
      <rect height={goalHeight} width={goalDepth} x={98 - goalDepth} y={goalTop} />
    </g>
  );
}

function downsampleSamples(samples: PositionSample[]): PositionSample[] {
  if (samples.length <= MAX_SAMPLES_FOR_DENSITY) return samples;
  const step = samples.length / MAX_SAMPLES_FOR_DENSITY;
  return Array.from({ length: MAX_SAMPLES_FOR_DENSITY }, (_, index) => {
    return samples[Math.min(samples.length - 1, Math.floor(index * step))];
  });
}

function createDensity(samples: PositionSample[], viewHeight: number): DensityPoint[] {
  const grid = Array.from({ length: COLUMN_COUNT }, () =>
    Array.from({ length: ROW_COUNT }, () => 0),
  );
  const rawCounts = Array.from({ length: COLUMN_COUNT }, () =>
    Array.from({ length: ROW_COUNT }, () => 0),
  );

  for (const sample of downsampleSamples(samples)) {
    const column = Math.min(
      COLUMN_COUNT - 1,
      Math.max(0, Math.floor(sample.x * COLUMN_COUNT)),
    );
    const row = Math.min(
      ROW_COUNT - 1,
      Math.max(0, Math.floor(sample.y * ROW_COUNT)),
    );
    rawCounts[column][row] += 1;
    addKernel(grid, column, row, 1);
  }

  const points: DensityPoint[] = [];
  let highest = 0;
  for (let column = 0; column < COLUMN_COUNT; column += 1) {
    for (let row = 0; row < ROW_COUNT; row += 1) {
      const value = grid[column][row];
      if (value <= 0) continue;
      highest = Math.max(highest, value);
      points.push({
        x: ((column + 0.5) / COLUMN_COUNT) * 96 + 2,
        y: ((row + 0.5) / ROW_COUNT) * (viewHeight - 4) + 2,
        count: Math.max(1, rawCounts[column][row] || Math.round(value)),
        intensity: value,
      });
    }
  }
  return points
    .map((point) => ({
      ...point,
      intensity: point.intensity / Math.max(highest, 1),
    }))
    .filter((point) => point.intensity >= 0.18);
}

function addKernel(
  grid: number[][],
  column: number,
  row: number,
  weight: number,
) {
  for (let dx = -1; dx <= 1; dx += 1) {
    for (let dy = -1; dy <= 1; dy += 1) {
      const nextColumn = column + dx;
      const nextRow = row + dy;
      if (
        nextColumn < 0 ||
        nextColumn >= COLUMN_COUNT ||
        nextRow < 0 ||
        nextRow >= ROW_COUNT
      ) {
        continue;
      }
      const spread =
        dx === 0 && dy === 0
          ? weight
          : dx === 0 || dy === 0
            ? weight * NEIGHBOR_WEIGHT
            : weight * DIAGONAL_WEIGHT;
      grid[nextColumn][nextRow] += spread;
    }
  }
}

function heatColor(intensity: number): string {
  const stops: Array<[number, number, number, number]> = [
    [0, 37, 99, 235],
    [0.28, 14, 165, 233],
    [0.5, 250, 204, 21],
    [0.74, 249, 115, 22],
    [1, 220, 38, 38],
  ];
  const value = Math.min(1, Math.max(0, intensity));
  let lower = stops[0];
  let upper = stops[stops.length - 1];
  for (let index = 0; index < stops.length - 1; index += 1) {
    if (value >= stops[index][0] && value <= stops[index + 1][0]) {
      lower = stops[index];
      upper = stops[index + 1];
      break;
    }
  }
  const span = upper[0] - lower[0] || 1;
  const mix = (value - lower[0]) / span;
  const channel = (from: number, to: number) => Math.round(from + (to - from) * mix);
  return `rgb(${channel(lower[1], upper[1])} ${channel(lower[2], upper[2])} ${channel(lower[3], upper[3])})`;
}
