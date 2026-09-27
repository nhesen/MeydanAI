import { ChevronRight } from "lucide-react";
import Link from "next/link";

import { Avatar } from "@/components/ui/Avatar";
import type { MatchPlayer } from "@/types/api";

interface PlayerRowProps {
  matchId: string;
  player: MatchPlayer;
}

export function PlayerRow({ matchId, player }: PlayerRowProps) {
  return (
    <Link
      className="grid min-h-16 grid-cols-[auto_minmax(0,1fr)_auto_auto] items-center gap-3 border-b border-border px-1 py-3 transition-colors last:border-0 hover:bg-subtle/70 focus-visible:rounded-xl focus-visible:outline-2 focus-visible:outline-brand-700"
      href={`/matches/${matchId}/players/${player.id}`}
    >
      <Avatar name={player.display_name} />
      <span className="min-w-0">
        <span className="block truncate text-sm font-semibold text-slate-950">
          {player.display_name}
        </span>
        <span className="mt-0.5 block truncate text-xs text-slate-500">
          {player.current_jersey !== null
            ? `Current jersey #${player.current_jersey}`
            : "Jersey N/A"}
        </span>
      </span>
      <span className="text-right">
        <span className="type-stat-label block">RATING</span>
        <span className="mt-0.5 block text-sm font-bold text-slate-700">
          {player.rating ?? "N/A"}
        </span>
      </span>
      <ChevronRight className="size-4 text-slate-400" aria-hidden="true" />
    </Link>
  );
}
