import type { MatchSummary } from "@/types/api";

type StatusVariant = "neutral" | "brand" | "success" | "warning" | "danger" | "info";

interface MatchStatusPresentation {
  label: string;
  shortLabel: string;
  variant: StatusVariant;
}

export const MATCH_STATUS: Record<
  MatchSummary["status"],
  MatchStatusPresentation
> = {
  scheduled: { label: "Scheduled", shortLabel: "Upcoming", variant: "info" },
  live: { label: "Live", shortLabel: "Live", variant: "danger" },
  processing: {
    label: "Processing analytics",
    shortLabel: "Processing",
    variant: "warning",
  },
  completed: { label: "Full time", shortLabel: "FT", variant: "success" },
  failed: { label: "Processing failed", shortLabel: "Failed", variant: "danger" },
  cancelled: { label: "Cancelled", shortLabel: "Cancelled", variant: "neutral" },
};

export function formatMatchClock(match: MatchSummary, now = new Date()): string {
  if (match.status === "completed") {
    if (!match.ended_at) return "Full time";
    return formatDuration(
      new Date(match.ended_at).getTime() - new Date(match.starts_at).getTime(),
    );
  }
  if (match.status === "live") {
    return formatDuration(now.getTime() - new Date(match.starts_at).getTime());
  }
  if (match.status === "processing") return "Processing";
  if (match.status === "failed") return "Unavailable";
  if (match.status === "cancelled") return "Cancelled";
  return new Intl.DateTimeFormat(undefined, {
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(match.starts_at));
}

function formatDuration(milliseconds: number): string {
  const totalSeconds = Math.max(0, Math.floor(milliseconds / 1000));
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}
