import { Clapperboard } from "lucide-react";
import Link from "next/link";

import { Badge } from "@/components/ui/Badge";
import { formatTimestamp, reviewedEventTitle } from "@/lib/analytics-formatters";
import { getApiBaseUrl } from "@/lib/env";
import type { HighlightType, PlatformHighlight } from "@/types/api";

function clipSource(videoUrl: string) {
  if (videoUrl.startsWith("http://") || videoUrl.startsWith("https://")) {
    return videoUrl;
  }
  return `${getApiBaseUrl()}${videoUrl}`;
}

export const HIGHLIGHT_LABELS: Record<HighlightType, string> = {
  goal: "Goal",
  top_run: "Top run",
  sprint: "Sprint",
  key_moment: "Key moment",
  manual: "Manual",
  ai_detected: "AI detected",
};

export function PlatformHighlightCard({
  highlight,
}: {
  highlight: PlatformHighlight;
}) {
  return (
    <article className="min-w-0 overflow-hidden rounded-2xl border border-border bg-white shadow-card">
      {highlight.video_url ? (
        <video
          className="aspect-video w-full bg-slate-950"
          controls
          playsInline
          preload="metadata"
          src={clipSource(highlight.video_url)}
        />
      ) : (
        <div
          aria-label="Highlight video unavailable"
          className="flex aspect-video items-center justify-center bg-subtle text-brand-700"
          role="img"
        >
          <Clapperboard className="size-8" strokeWidth={1.5} aria-hidden="true" />
        </div>
      )}
      <div className="p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex flex-wrap gap-2"><Badge>{HIGHLIGHT_LABELS[highlight.highlight_type]}</Badge>{highlight.review_status ? <Badge variant={highlight.review_status === "confirmed" ? "success" : "warning"}>{highlight.review_status === "confirmed" ? "Organizer confirmed" : "Needs review"}</Badge> : highlight.highlight_type === "ai_detected" ? <Badge variant="warning">AI suggestion</Badge> : null}</div>
          <span className="text-xs font-semibold tabular-nums text-slate-500">
            {formatTimestamp(highlight.timestamp_ms)}
          </span>
        </div>
        <h3 className="mt-3 font-bold text-slate-950">{reviewedEventTitle(highlight.title, highlight.review_status)}</h3>
        <p className="mt-1 truncate text-sm text-slate-500">
          {highlight.match_title ?? "Match highlight"}
          {highlight.player_name ? ` · ${highlight.player_name}` : ""}
        </p>
        <div className="mt-4">
          <Link
            className="ml-4 inline-flex min-h-11 items-center text-sm font-semibold text-slate-600 hover:text-brand-800"
            href={`/matches/${highlight.match_id}?tab=highlights`}
          >
            View match
          </Link>
        </div>
      </div>
    </article>
  );
}
