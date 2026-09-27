import {
  Activity,
  Gauge,
  ListChecks,
  Route,
  Star,
  Timer,
  Zap,
} from "lucide-react";

import { Card } from "@/components/ui/Card";
import { getRatingBand } from "@/config/player-rating";
import {
  formatCount,
  formatDistance,
  formatDuration,
  formatRating,
  formatSpeed,
} from "@/lib/analytics-formatters";
import { cn } from "@/lib/cn";
import type { MatchPlayer } from "@/types/api";

interface PlayerKpiGridProps {
  player: MatchPlayer;
}

export function PlayerKpiGrid({ player }: PlayerKpiGridProps) {
  const ratingBand = getRatingBand(player.rating);
  const items = [
    {
      label: "Rating",
      value: formatRating(player.rating),
      icon: Star,
      detail: ratingBand?.label,
      className: ratingBand?.className,
    },
    {
      label: "Distance",
      value: formatDistance(player.distance_m),
      icon: Route,
    },
    {
      label: "Average speed",
      value: formatSpeed(player.avg_speed_kmh),
      icon: Gauge,
    },
    {
      label: "Maximum speed",
      value: formatSpeed(player.max_speed_kmh),
      icon: Zap,
    },
    {
      label: "Sprint count",
      value: formatCount(player.sprint_count),
      icon: Activity,
    },
    {
      label: "Active time",
      value: formatDuration(player.active_seconds),
      icon: Timer,
    },
    {
      label: "Activity count",
      value: formatCount(player.activity_count),
      icon: ListChecks,
    },
  ];

  return (
    <section aria-labelledby="performance-kpis">
      <h2 className="type-section-title text-slate-950" id="performance-kpis">
        Performance
      </h2>
      <div className="mt-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
        {items.map(({ className, detail, icon: Icon, label, value }) => (
          <Card className="min-h-32" key={label} padding="sm">
            <div className="flex items-start justify-between gap-2">
              <span className="flex size-9 items-center justify-center rounded-lg bg-subtle text-brand-700">
                <Icon className="size-4" aria-hidden="true" />
              </span>
              {detail ? (
                <span
                  className={cn(
                    "rounded-full px-2 py-1 text-[0.65rem] font-bold",
                    className,
                  )}
                >
                  {detail}
                </span>
              ) : null}
            </div>
            <p className="mt-4 text-lg font-bold tabular-nums text-slate-950 sm:text-xl">
              {value}
            </p>
            <p className="mt-1 text-xs font-semibold text-slate-500">{label}</p>
          </Card>
        ))}
      </div>
    </section>
  );
}
