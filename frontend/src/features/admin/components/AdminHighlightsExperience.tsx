"use client";

import { type FormEvent, useEffect, useState } from "react";

import { ErrorState } from "@/components/feedback/ErrorState";
import { LoadingSkeleton } from "@/components/feedback/LoadingSkeleton";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { Field } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import { AdminGuard } from "@/features/admin/components/AdminGuard";
import { AdminShell } from "@/features/admin/components/AdminShell";
import { HIGHLIGHT_LABELS, PlatformHighlightCard } from "@/features/platform/components/PlatformHighlightCard";
import { api } from "@/services/api-client";
import type { HighlightType, PlatformHighlight } from "@/types/api";

export function AdminHighlightsExperience() {
  const [highlights, setHighlights] = useState<PlatformHighlight[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [pendingDelete, setPendingDelete] = useState<PlatformHighlight | null>(null);
  const [busy, setBusy] = useState(false);
  const [matchId, setMatchId] = useState("");
  const [title, setTitle] = useState("");
  const [timestamp, setTimestamp] = useState("0");
  const [highlightType, setHighlightType] = useState<HighlightType>("manual");

  async function load() {
    await Promise.resolve();
    try {
      const response = await api.getAdminHighlights({ page_size: 30 });
      setHighlights(response.data.items);
      setFailed(false);
    } catch {
      setFailed(true);
    }
  }

  useEffect(() => {
    async function initialize() {
      await Promise.resolve();
      try {
        const response = await api.getAdminHighlights({ page_size: 30 });
        setHighlights(response.data.items);
        setFailed(false);
      } catch {
        setFailed(true);
      }
    }
    void initialize();
  }, []);

  async function createHighlight(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    try {
      await api.createAdminHighlight({
        match_id: matchId.trim(),
        highlight_type: highlightType,
        timestamp_ms: Number(timestamp) || 0,
        title: title.trim(),
      });
      setTitle("");
      await load();
    } finally {
      setBusy(false);
    }
  }

  async function removeHighlight() {
    if (!pendingDelete) return;
    setBusy(true);
    try {
      await api.deleteAdminHighlight(pendingDelete.id);
      setPendingDelete(null);
      await load();
    } finally {
      setBusy(false);
    }
  }

  return (
    <AdminGuard>
      <AdminShell
        description="Manual highlight metadata only. Placeholder video URLs are not created."
        title="Highlights"
      >
        <Card className="mb-6">
          <form className="grid gap-3 sm:grid-cols-2" onSubmit={createHighlight}>
            <Field htmlFor="highlight-match" label="Match ID">
              <Input id="highlight-match" onChange={(event) => setMatchId(event.target.value)} required value={matchId} />
            </Field>
            <Field htmlFor="highlight-title" label="Title">
              <Input id="highlight-title" onChange={(event) => setTitle(event.target.value)} required value={title} />
            </Field>
            <Field htmlFor="highlight-time" label="Timestamp (ms)">
              <Input
                id="highlight-time"
                min={0}
                onChange={(event) => setTimestamp(event.target.value)}
                type="number"
                value={timestamp}
              />
            </Field>
            <Field htmlFor="highlight-type" label="Type">
              <select
                className="h-11 w-full rounded-xl border border-border bg-white px-3 text-sm"
                id="highlight-type"
                onChange={(event) => setHighlightType(event.target.value as HighlightType)}
                value={highlightType}
              >
                {Object.entries(HIGHLIGHT_LABELS).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </Field>
            <div className="sm:col-span-2">
              <Button loading={busy} type="submit">
                Create highlight
              </Button>
            </div>
          </form>
        </Card>
        {failed ? (
          <ErrorState message="Highlights could not be loaded." onRetry={() => void load()} title="Highlights unavailable" />
        ) : highlights === null ? (
          <LoadingSkeleton label="Loading highlights" lines={5} />
        ) : highlights.length === 0 ? (
          <p className="text-sm text-slate-500">No highlights yet.</p>
        ) : (
          <div className="grid gap-5 sm:grid-cols-2">
            {highlights.map((highlight) => (
              <div key={highlight.id}>
                <PlatformHighlightCard highlight={highlight} />
                <Button
                  className="mt-2"
                  onClick={() => setPendingDelete(highlight)}
                  size="sm"
                  variant="destructive"
                >
                  Delete
                </Button>
              </div>
            ))}
          </div>
        )}
        <ConfirmDialog
          busy={busy}
          confirmLabel="Delete highlight"
          danger
          description="This removes the highlight metadata. Historical match analytics are not deleted."
          onCancel={() => setPendingDelete(null)}
          onConfirm={() => void removeHighlight()}
          open={pendingDelete !== null}
          title="Delete highlight"
        />
      </AdminShell>
    </AdminGuard>
  );
}
