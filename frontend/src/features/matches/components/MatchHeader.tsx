import { CalendarDays, MapPin } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { MATCH_STATUS, formatMatchClock } from "@/config/match-status";
import type { MatchSummary, MatchTeam } from "@/types/api";

interface MatchHeaderProps {
  match: MatchSummary;
  now: Date;
}

export function MatchHeader({ match, now }: MatchHeaderProps) {
  const home = match.teams.find((team) => team.side === "home") ?? match.teams[0];
  const away = match.teams.find((team) => team.side === "away") ?? match.teams[1];
  const status = MATCH_STATUS[match.status];

  return (
    <Card className="overflow-hidden" padding="none">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border bg-subtle/60 px-4 py-3 sm:px-6">
        <div className="flex min-w-0 flex-wrap items-center gap-x-4 gap-y-2 text-xs text-slate-600">
          <span className="inline-flex items-center gap-1.5">
            <CalendarDays className="size-3.5" aria-hidden="true" />
            {new Intl.DateTimeFormat(undefined, {
              dateStyle: "medium",
              timeStyle: "short",
            }).format(new Date(match.starts_at))}
          </span>
          <span className="inline-flex min-w-0 items-center gap-1.5">
            <MapPin className="size-3.5 shrink-0" aria-hidden="true" />
            <span className="truncate">{match.venue_name}</span>
          </span>
        </div>
        <Badge dot={match.status === "live"} variant={status.variant}>
          {status.label}
        </Badge>
      </div>

      <div className="px-4 py-7 sm:px-8 sm:py-9">
        {match.title ? (
          <p className="mb-5 text-center text-xs font-semibold uppercase tracking-wider text-slate-500">
            {match.title}
          </p>
        ) : null}
        <div className="grid grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-center gap-3 sm:gap-8">
          {home ? <TeamIdentity team={home} /> : <span />}
          <div className="text-center">
            <div className="flex items-baseline justify-center gap-2 sm:gap-3">
              <span className="type-score text-slate-950">
                {match.home_score ?? "—"}
              </span>
              <span className="text-xl font-medium text-slate-300">–</span>
              <span className="type-score text-slate-950">
                {match.away_score ?? "—"}
              </span>
            </div>
            <p className="mt-3 text-sm font-bold tabular-nums text-brand-700">
              {formatMatchClock(match, now)}
            </p>
          </div>
          {away ? <TeamIdentity align="right" team={away} /> : <span />}
        </div>
      </div>
    </Card>
  );
}

function TeamIdentity({
  align = "left",
  team,
}: {
  align?: "left" | "right";
  team: MatchTeam;
}) {
  const initial = team.name.trim().charAt(0).toUpperCase() || "?";
  return (
    <div
      className={`flex min-w-0 flex-col gap-2 ${
        align === "right" ? "items-end text-right" : "items-start"
      }`}
    >
      <span
        className={`grid size-11 place-items-center rounded-2xl text-sm font-bold sm:size-14 ${
          align === "right"
            ? "bg-info-100 text-info-800"
            : "bg-brand-100 text-brand-800"
        }`}
        aria-hidden="true"
      >
        {initial}
      </span>
      <span className="max-w-full truncate text-sm font-bold text-slate-950 sm:text-base">
        {team.name}
      </span>
    </div>
  );
}
