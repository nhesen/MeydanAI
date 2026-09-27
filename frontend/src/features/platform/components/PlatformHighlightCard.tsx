import { Clapperboard, ExternalLink, Play } from "lucide-react";
import Link from "next/link";

import { Badge } from "@/components/ui/Badge";
import { formatTimestamp } from "@/lib/analytics-formatters";
import type { HighlightType, PlatformHighlight } from "@/types/api";

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
      <div
        aria-label={
          highlight.thumbnail_url
            ? `Thumbnail for ${highlight.title}`
            : "Highlight thumbnail unavailable"
        }
        className="flex aspect-video items-center justify-center bg-subtle bg-cover bg-center text-brand-700"
        role="img"
        style={
          highlight.thumbnail_url
            ? { backgroundImage: `url("${highlight.thumbnail_url}")` }
            : undefined
        }
      >
        {!highlight.thumbnail_url ? (
          <Clapperboard className="size-8" strokeWidth={1.5} aria-hidden="true" />
        ) : null}
      </div>
      <div className="p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <Badge>{HIGHLIGHT_LABELS[highlight.highlight_type]}</Badge>
          <span className="text-xs font-semibold tabular-nums text-slate-500">
            {formatTimestamp(highlight.timestamp_ms)}
          </span>
        </div>
        <h3 className="mt-3 font-bold text-slate-950">{highlight.title}</h3>
        <p className="mt-1 truncate text-sm text-slate-500">
          {highlight.match_title ?? "Match highlight"}
          {highlight.player_name ? ` · ${highlight.player_name}` : ""}
        </p>
        <div className="mt-4">
          {highlight.video_url ? (
            <a
              className="inline-flex min-h-11 items-center gap-2 text-sm font-semibold text-brand-700 hover:text-brand-900"
              href={highlight.video_url}
              rel="noreferrer"
              target="_blank"
            >
              <Play className="size-4" aria-hidden="true" />
              Open clip
              <ExternalLink className="size-3.5" aria-hidden="true" />
            </a>
          ) : (
            <span className="inline-flex min-h-11 items-center text-sm font-semibold text-slate-400">
              Clip unavailable
            </span>
          )}
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
