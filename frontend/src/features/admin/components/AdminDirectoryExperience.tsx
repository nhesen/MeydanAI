"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { ErrorState } from "@/components/feedback/ErrorState";
import { LoadingSkeleton } from "@/components/feedback/LoadingSkeleton";
import { Card } from "@/components/ui/Card";
import { AdminGuard } from "@/features/admin/components/AdminGuard";
import { AdminShell } from "@/features/admin/components/AdminShell";
import { api } from "@/services/api-client";
import type { MatchListItem, PlayerDirectoryItem, TeamDirectoryItem } from "@/types/api";

type DirectoryKind = "matches" | "players" | "teams";

export function AdminDirectoryExperience({ kind }: { kind: DirectoryKind }) {
  const [items, setItems] = useState<Array<MatchListItem | PlayerDirectoryItem | TeamDirectoryItem> | null>(
    null,
  );
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      await Promise.resolve();
      try {
        if (kind === "matches") {
          setItems((await api.getAdminMatches({ page_size: 30 }, controller.signal)).data.items);
        } else if (kind === "players") {
          setItems((await api.getAdminPlayers({ page_size: 30 }, controller.signal)).data.items);
        } else {
          setItems((await api.getAdminTeams({ page_size: 30 }, controller.signal)).data.items);
        }
        setFailed(false);
      } catch {
        if (!controller.signal.aborted) setFailed(true);
      }
    }
    void load();
    return () => controller.abort();
  }, [kind]);

  const copy = {
    matches: ["Matches", "Review and open match management."],
    players: ["Players", "Global player identities, not jersey numbers."],
    teams: ["Teams", "Squads created with matches."],
  } as const;

  return (
    <AdminGuard>
      <AdminShell description={copy[kind][1]} title={copy[kind][0]}>
        {failed ? (
          <ErrorState message="This directory could not be loaded." title="Directory unavailable" />
        ) : items === null ? (
          <LoadingSkeleton label={`Loading ${kind}`} lines={5} />
        ) : items.length === 0 ? (
          <p className="text-sm text-slate-500">No records yet.</p>
        ) : (
          <div className="space-y-3">
            {items.map((item) => (
              <DirectoryRow item={item} key={"id" in item ? item.id : item.match.id} kind={kind} />
            ))}
          </div>
        )}
      </AdminShell>
    </AdminGuard>
  );
}

function DirectoryRow({
  item,
  kind,
}: {
  item: MatchListItem | PlayerDirectoryItem | TeamDirectoryItem;
  kind: DirectoryKind;
}) {
  if (kind === "matches" && "match" in item) {
    return (
      <Card>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="font-semibold text-slate-950">
              {item.match.title ?? item.match.venue_name}
            </p>
            <p className="mt-1 text-sm text-slate-500">{item.match.status}</p>
          </div>
          <Link className="text-sm font-semibold text-brand-700" href={`/matches/${item.match.id}/manage`}>
            Manage
          </Link>
        </div>
      </Card>
    );
  }
  if (kind === "players" && "display_name" in item) {
    return (
      <Card>
        <Link className="font-semibold text-slate-950 hover:text-brand-800" href={`/players/${item.id}`}>
          {item.display_name}
        </Link>
      </Card>
    );
  }
  if (kind === "teams" && "name" in item) {
    return (
      <Card>
        <Link className="font-semibold text-slate-950 hover:text-brand-800" href={`/teams/${item.id}`}>
          {item.name}
        </Link>
      </Card>
    );
  }
  return null;
}
