import type { IntensityBucket } from "@/types/api";

interface PlayerIntensityChartProps {
  buckets: IntensityBucket[];
  processing?: boolean;
}

export function PlayerIntensityChart({
  buckets,
  processing = false,
}: PlayerIntensityChartProps) {
  if (buckets.length === 0) {
    return (
      <div className="flex min-h-52 items-center justify-center rounded-xl border border-dashed border-border bg-subtle/50 px-6 text-center">
        <p className="max-w-xs text-sm font-semibold text-slate-600">
          {processing
            ? "Intensity data is being processed."
            : "Intensity-by-minute data is not available for this player yet."}
        </p>
      </div>
    );
  }

  return (
    <div
      aria-label="Player intensity by match minute. Intensity is a normalized zero to one hundred value supplied by the analytics pipeline."
      role="img"
    >
      <div className="grid grid-cols-[2rem_minmax(0,1fr)] gap-2">
        <div className="flex h-52 flex-col justify-between pb-6 text-right text-[0.65rem] font-semibold text-slate-400">
          <span>100</span>
          <span>50</span>
          <span>0</span>
        </div>
        <div
          className="grid h-52 items-end gap-1 border-b border-l border-border px-1 pt-2"
          style={{
            gridTemplateColumns: `repeat(${buckets.length}, minmax(0, 1fr))`,
          }}
        >
          {buckets.map((bucket, index) => {
            const label = `${bucket.from_minute}–${bucket.to_minute} min: intensity ${formatIntensity(bucket.intensity)}`;
            return (
              <div
                className="group relative flex h-full min-w-0 items-end justify-center"
                key={`${bucket.from_minute}-${bucket.to_minute}`}
              >
                <button
                  aria-label={label}
                  className="w-full min-w-1 rounded-t bg-brand-500 transition-colors hover:bg-brand-700 focus-visible:bg-brand-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-700"
                  style={{ height: `${bucket.intensity}%` }}
                  title={label}
                  type="button"
                />
                <span className="pointer-events-none absolute bottom-[calc(100%+0.35rem)] left-1/2 z-10 hidden -translate-x-1/2 whitespace-nowrap rounded-md bg-slate-950 px-2 py-1 text-[0.65rem] font-semibold text-white group-focus-within:block group-hover:block">
                  {label}
                </span>
                {shouldShowLabel(index, buckets.length) ? (
                  <span className="absolute -bottom-5 left-1/2 -translate-x-1/2 text-[0.65rem] font-semibold text-slate-500">
                    {bucket.from_minute}
                  </span>
                ) : null}
              </div>
            );
          })}
        </div>
      </div>
      <p className="mt-7 text-center text-xs font-semibold text-slate-500">
        Match minute
      </p>
    </div>
  );
}

function formatIntensity(value: number): string {
  return Number.isInteger(value) ? value.toString() : value.toFixed(1);
}

function shouldShowLabel(index: number, total: number): boolean {
  const interval = Math.max(1, Math.ceil(total / 6));
  return index === 0 || index === total - 1 || index % interval === 0;
}
