import { BarChart3, CalendarDays, MapPin } from "lucide-react";
import Link from "next/link";

import { Badge } from "@/components/ui/Badge";
import { MATCH_STATUS } from "@/config/match-status";
import type { MatchListItem } from "@/types/api";

export function PlatformMatchCard({ item }: { item: MatchListItem }) {
  const { match } = item;
  const status = MATCH_STATUS[match.status];
  const home = match.teams.find((team) => team.side === "home") ?? match.teams[0];
  const away = match.teams.find((team) => team.side === "away") ?? match.teams[1];

  return (
    <Link
      className="group block min-w-0 rounded-2xl border border-border bg-white p-4 shadow-card transition hover:border-brand-200 hover:shadow-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-700"
      href={`/matches/${match.id}`}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <Badge dot variant={status.variant}>
          {status.shortLabel}
        </Badge>
        {item.has_analytics ? (
          <span className="inline-flex items-center gap-1 text-xs font-semibold text-brand-700">
            <BarChart3 className="size-3.5" aria-hidden="true" />
            Analytics
          </span>
        ) : null}
      </div>
      <h3 className="mt-3 truncate text-sm font-semibold text-slate-600">
        {match.title ?? `${home?.name ?? "Home"} vs ${away?.name ?? "Away"}`}
      </h3>
      <div className="mt-4 grid grid-cols-[minmax(0,1fr)_auto] items-center gap-3">
        <div className="min-w-0 space-y-2">
          <p className="truncate font-bold text-slate-950">{home?.name ?? "Home"}</p>
          <p className="truncate font-bold text-slate-950">{away?.name ?? "Away"}</p>
        </div>
        <div className="grid grid-cols-1 gap-2 text-right text-xl font-bold tabular-nums text-slate-950">
          <span>{match.home_score ?? "—"}</span>
          <span>{match.away_score ?? "—"}</span>
        </div>
      </div>
      <div className="mt-4 flex flex-wrap gap-x-4 gap-y-1 border-t border-border pt-3 text-xs text-slate-500">
        <span className="inline-flex items-center gap-1">
          <CalendarDays className="size-3.5" aria-hidden="true" />
          {formatDate(match.starts_at)}
        </span>
        <span className="inline-flex min-w-0 items-center gap-1">
          <MapPin className="size-3.5 shrink-0" aria-hidden="true" />
          <span className="truncate">{match.venue_name}</span>
        </span>
      </div>
    </Link>
  );
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("en", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}
