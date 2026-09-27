"use client";

import { useMemo } from "react";

import type { PositionSample } from "@/types/api";

interface PlayerHeatmapProps {
  samples: PositionSample[];
  processing?: boolean;
}

interface DensityPoint {
  x: number;
  y: number;
  count: number;
  intensity: number;
}

const COLUMN_COUNT = 12;
const ROW_COUNT = 8;
const MAX_SAMPLES_FOR_DENSITY = 2500;

export function PlayerHeatmap({
  processing = false,
  samples,
}: PlayerHeatmapProps) {
  const density = useMemo(() => createDensity(samples), [samples]);

  return (
    <div>
      <div
        aria-label={
          samples.length
            ? `Football pitch heatmap built from ${samples.length} normalized position samples.`
            : "Football pitch heatmap without available position samples."
        }
        className="relative aspect-[100/64] w-full overflow-hidden rounded-xl border border-brand-800/20 bg-[#e4f0e7]"
        role="img"
      >
        <svg
          aria-hidden="true"
          className="size-full"
          preserveAspectRatio="xMidYMid meet"
          viewBox="0 0 100 64"
        >
          <defs>
            <filter id="heat-blur" x="-40%" y="-40%" width="180%" height="180%">
              <feGaussianBlur stdDeviation="3.5" />
            </filter>
          </defs>
          <rect width="100" height="64" fill="#dcebe0" />
          <g
            fill="none"
            stroke="#659475"
            strokeWidth="0.55"
            opacity="0.85"
          >
            <rect x="2" y="2" width="96" height="60" rx="0.5" />
            <line x1="50" y1="2" x2="50" y2="62" />
            <circle cx="50" cy="32" r="8" />
            <circle cx="50" cy="32" r="0.8" fill="#659475" />
            <rect x="2" y="16" width="16" height="32" />
            <rect x="82" y="16" width="16" height="32" />
            <rect x="2" y="23" width="6" height="18" />
            <rect x="92" y="23" width="6" height="18" />
            <circle cx="12" cy="32" r="0.8" fill="#659475" />
            <circle cx="88" cy="32" r="0.8" fill="#659475" />
          </g>
          <g filter="url(#heat-blur)">
            {density.map((point) => (
              <circle
                cx={point.x}
                cy={point.y}
                fill={heatColor(point.intensity)}
                key={`${point.x}-${point.y}`}
                opacity={0.3 + point.intensity * 0.55}
                r={3.5 + point.intensity * 5.5}
              />
            ))}
          </g>
          <g>
            {density.map((point) => (
              <circle
                cx={point.x}
                cy={point.y}
                fill={heatColor(point.intensity)}
                key={`core-${point.x}-${point.y}`}
                opacity={0.2 + point.intensity * 0.45}
                r={1.3 + point.intensity * 2}
              >
                <title>{`${point.count} samples in this pitch area`}</title>
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
            className="h-2.5 w-24 rounded-full bg-gradient-to-r from-emerald-500 via-amber-400 to-red-500"
            aria-hidden="true"
          />
          <span>Higher activity</span>
        </div>
      ) : null}
    </div>
  );
}

function downsampleSamples(samples: PositionSample[]): PositionSample[] {
  if (samples.length <= MAX_SAMPLES_FOR_DENSITY) return samples;
  const step = samples.length / MAX_SAMPLES_FOR_DENSITY;
  return Array.from({ length: MAX_SAMPLES_FOR_DENSITY }, (_, index) => {
    return samples[Math.min(samples.length - 1, Math.floor(index * step))];
  });
}

function createDensity(samples: PositionSample[]): DensityPoint[] {
  const buckets = new Map<string, { column: number; row: number; count: number }>();
  for (const sample of downsampleSamples(samples)) {
    const column = Math.min(
      COLUMN_COUNT - 1,
      Math.max(0, Math.floor(sample.x * COLUMN_COUNT)),
    );
    const row = Math.min(
      ROW_COUNT - 1,
      Math.max(0, Math.floor(sample.y * ROW_COUNT)),
    );
    const key = `${column}-${row}`;
    const bucket = buckets.get(key);
    if (bucket) bucket.count += 1;
    else buckets.set(key, { column, row, count: 1 });
  }
  const highestCount = Math.max(1, ...Array.from(buckets.values(), (item) => item.count));
  return Array.from(buckets.values(), (bucket) => ({
    x: ((bucket.column + 0.5) / COLUMN_COUNT) * 96 + 2,
    y: ((bucket.row + 0.5) / ROW_COUNT) * 60 + 2,
    count: bucket.count,
    intensity: bucket.count / highestCount,
  }));
}

function heatColor(intensity: number): string {
  if (intensity >= 0.7) return "#dc2626";
  if (intensity >= 0.4) return "#f59e0b";
  return "#16a34a";
}
