import { Activity, Clock3, Shirt, Zap } from "lucide-react";

import { EmptyState } from "@/components/feedback/EmptyState";
import { formatSpeed, formatTimestamp } from "@/lib/analytics-formatters";
import type { PlayerAnalyticsDetail } from "@/types/api";

interface PlayerPerformanceTimelineProps {
  detail: PlayerAnalyticsDetail;
}

interface DisplayEvent {
  id: string;
  timestampMs: number;
  title: string;
  detail: string | null;
  type: "sprint" | "peak_speed" | "jersey_change" | "high_intensity" | "custom";
}

const eventLabels: Record<DisplayEvent["type"], string> = {
  sprint: "Sprint",
  peak_speed: "Peak speed",
  jersey_change: "Jersey change",
  high_intensity: "High intensity",
  custom: "Performance event",
};

export function PlayerPerformanceTimeline({
  detail,
}: PlayerPerformanceTimelineProps) {
  const events = createEvents(detail);

  if (events.length === 0) {
    return (
      <EmptyState
        compact
        description="Sprint, peak-speed and other verified performance moments will appear here when available."
        icon={Clock3}
        title="No performance events yet"
      />
    );
  }

  return (
    <ol className="mt-5 space-y-1">
      {events.map((event) => {
        const Icon =
          event.type === "jersey_change"
            ? Shirt
            : event.type === "peak_speed"
              ? Zap
              : Activity;
        return (
          <li
            className="grid grid-cols-[3.2rem_2rem_minmax(0,1fr)] gap-2"
            key={event.id}
          >
            <span className="pt-3 text-right text-xs font-bold tabular-nums text-brand-700">
              {formatTimestamp(event.timestampMs)}
            </span>
            <span className="relative flex justify-center">
              <span className="absolute inset-y-0 w-px bg-border" aria-hidden="true" />
              <span className="relative mt-2 flex size-8 items-center justify-center rounded-full border border-border bg-white text-brand-700">
                <Icon className="size-4" aria-hidden="true" />
              </span>
            </span>
            <div className="min-w-0 pb-5 pt-2">
              <p className="text-xs font-bold uppercase tracking-wide text-slate-500">
                {eventLabels[event.type]}
              </p>
              <p className="mt-1 break-words text-sm font-semibold text-slate-950">
                {event.title}
              </p>
              {event.detail ? (
                <p className="mt-1 text-sm text-slate-600">{event.detail}</p>
              ) : null}
            </div>
          </li>
        );
      })}
    </ol>
  );
}

function createEvents(detail: PlayerAnalyticsDetail): DisplayEvent[] {
  const analyticsEvents: DisplayEvent[] = detail.events.map((event) => ({
    id: event.id,
    timestampMs: event.timestamp_ms,
    title: event.title,
    detail: event.speed_kmh === null ? null : formatSpeed(event.speed_kmh),
    type:
      event.event_type === "high_intensity_period"
        ? "high_intensity"
        : event.event_type,
  }));
  const matchStart = new Date(detail.match.starts_at).getTime();
  const jerseyEvents: DisplayEvent[] = detail.player.jersey_history
    .slice(1)
    .map((assignment, index) => ({
      id: `jersey-${assignment.assignment_id}`,
      timestampMs: Math.max(
        0,
        new Date(assignment.started_at).getTime() - matchStart,
      ),
      title: `Changed to #${assignment.jersey_number}`,
      detail: `Previous jersey #${detail.player.jersey_history[index]?.jersey_number}`,
      type: "jersey_change",
    }));
  return [...analyticsEvents, ...jerseyEvents].sort(
    (left, right) => left.timestampMs - right.timestampMs,
  );
}
