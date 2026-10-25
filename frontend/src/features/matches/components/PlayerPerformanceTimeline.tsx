import { Activity, Clock3, Shirt, Zap } from "lucide-react";

import { EmptyState } from "@/components/feedback/EmptyState";
import { Badge } from "@/components/ui/Badge";
import { formatSpeed, formatTimestamp, reviewedEventTitle } from "@/lib/analytics-formatters";
import type { EventReviewStatus, PlayerAnalyticsDetail } from "@/types/api";

interface PlayerPerformanceTimelineProps {
  detail: PlayerAnalyticsDetail;
}

interface DisplayEvent {
  id: string;
  timestampMs: number;
  title: string;
  detail: string | null;
  type: string;
  reviewStatus?: EventReviewStatus;
}

const eventLabels: Record<string, string> = {
  sprint: "Sprint",
  peak_speed: "Peak speed",
  jersey_change: "Jersey change",
  high_intensity: "High intensity",
  custom: "Performance event",
  pass: "Pass",
  successful_pass: "Successful pass",
  failed_pass: "Failed pass",
  key_pass: "Key pass",
  shot: "Shot",
  shot_on_target: "Shot on target",
  shot_off_target: "Shot off target",
  goal: "Goal",
  assist: "Assist",
  tackle: "Tackle",
  interception: "Interception",
  turnover: "Turnover",
  ball_recovery: "Ball recovery",
  dribble: "Dribble",
  save: "Save",
  corner: "Corner",
  goal_kick: "Goal kick",
  woodwork: "Post",
  big_chance: "Big chance",
  free_kick: "Free kick",
  penalty: "Penalty",
};

export function PlayerPerformanceTimeline({
  detail,
}: PlayerPerformanceTimelineProps) {
  const events = createEvents(detail);

  if (events.length === 0) {
    return (
      <EmptyState
        compact
        description="Movement and performance moments will appear here when available. AI suggestions require review."
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
                {eventLabels[event.type] ?? event.type.replaceAll("_", " ")}
              </p>
              <p className="mt-1 break-words text-sm font-semibold text-slate-950">
                {reviewedEventTitle(event.title, event.reviewStatus)}
              </p>
              {event.reviewStatus ? <div className="mt-2"><Badge variant={event.reviewStatus === "confirmed" ? "success" : "warning"}>{event.reviewStatus === "confirmed" ? "Organizer confirmed" : "AI suggestion · needs review"}</Badge></div> : null}
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
  const analyticsEvents: DisplayEvent[] = detail.events.filter((event) => event.review_status !== "rejected").map((event) => ({
    id: event.id,
    timestampMs: event.timestamp_ms,
    title: event.title,
    reviewStatus: event.review_status ?? "pending",
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
