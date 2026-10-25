"use client";

import Image from "next/image";
import { useEffect, useMemo, useState } from "react";

import { EmptyState } from "@/components/feedback/EmptyState";
import { ErrorState } from "@/components/feedback/ErrorState";
import { LoadingSkeleton } from "@/components/feedback/LoadingSkeleton";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { Input } from "@/components/ui/Input";
import { AnalysisQualityPanel } from "@/features/matches/components/AnalysisQualityPanel";
import { formatTimestamp, reviewedEventTitle } from "@/lib/analytics-formatters";
import { getApiBaseUrl } from "@/lib/env";
import { ApiError, api } from "@/services/api-client";
import type { AnalysisReview, JerseyAssignment, MatchTeam, TrackReviewItem } from "@/types/api";

interface PlayerOption { id: string; name: string; teamIds: string[]; canRename?: boolean; }
interface MappingChange { mapping: TrackReviewItem; playerId: string; teamId: string; playerName: string; displayName?: string; }
function mediaUrl(value: string): string { return value.startsWith("/") ? `${getApiBaseUrl()}${value}` : value; }

export function AnalysisReviewPanel({ matchId, organizerToken, teams, assignments, reloadKey, onReviewed }: {
  matchId: string; organizerToken?: string | null; teams: MatchTeam[]; assignments: JerseyAssignment[];
  reloadKey: number; onReviewed: () => void;
}) {
  const [review, setReview] = useState<AnalysisReview | null>(null);
  const [loading, setLoading] = useState(true);
  const [attempt, setAttempt] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [eventFilter, setEventFilter] = useState("pending");
  const [eventLimit, setEventLimit] = useState(24);
  const [confirmation, setConfirmation] = useState<MappingChange | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    void api.getAnalysisReview(matchId, organizerToken, controller.signal).then((response) => {
      setReview(response.data); setError(null);
    }).catch((caught: unknown) => {
      if (!controller.signal.aborted) setError(caught instanceof ApiError && caught.status === 403 ? "Organizer access is required to review analysis." : "Analysis review could not be loaded.");
    }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [matchId, organizerToken, reloadKey, attempt]);

  const players = useMemo(() => {
    const choices = new Map<string, PlayerOption>();
    assignments.forEach((item) => {
      const existing = choices.get(item.player.id);
      choices.set(item.player.id, { id: item.player.id, name: item.player.display_name, teamIds: [...new Set([...(existing?.teamIds ?? []), item.team.id])] });
    });
    review?.mappings.forEach((item) => { if (item.player_id) {
      const existing = choices.get(item.player_id);
      choices.set(item.player_id, { id: item.player_id, name: item.display_name ?? existing?.name ?? `Track ${item.provider_track_id}`, teamIds: existing?.teamIds ?? (item.team_id ? [item.team_id] : []), canRename: item.can_rename });
    } });
    return [...choices.values()].sort((a, b) => a.name.localeCompare(b.name));
  }, [assignments, review]);

  async function confirmMapping() {
    if (!confirmation || busy) return;
    setBusy(confirmation.mapping.id); setError(null);
    try {
      const response = await api.reviewTrackMapping(matchId, confirmation.mapping.id, organizerToken, confirmation.playerId, confirmation.teamId, confirmation.displayName);
      setReview(response.data); setConfirmation(null); onReviewed();
    } catch (caught: unknown) {
      setError(caught instanceof ApiError ? caught.problem?.detail ?? "Player mapping could not be updated." : "Player mapping could not be updated. Check your connection.");
    } finally { setBusy(null); }
  }
  async function reviewEvent(eventId: string, status: "confirmed" | "rejected") {
    if (busy) return;
    setBusy(eventId); setError(null);
    try {
      const response = await api.reviewAnalysisEvent(matchId, eventId, organizerToken, status);
      setReview(response.data); onReviewed();
    } catch (caught: unknown) {
      setError(caught instanceof ApiError ? caught.problem?.detail ?? "Event review could not be saved." : "Event review could not be saved. Check your connection.");
    } finally { setBusy(null); }
  }

  if (loading) return <Card><LoadingSkeleton lines={3} label="Loading analysis review" /></Card>;
  if (!review) return <ErrorState compact title="Review unavailable" message={error ?? "Analysis review could not be loaded."} onRetry={() => setAttempt((current) => current + 1)} />;
  const other = confirmation ? review.mappings.find((item) => item.id !== confirmation.mapping.id && item.player_id === confirmation.playerId) : undefined;
  const events = review.events.filter((item) => eventFilter === "all" || item.review_status === eventFilter);
  const confirmed = review.mappings.filter((item) => item.review_status === "confirmed").length;

  return (
    <section className="space-y-5" aria-label="Review player identity and AI events">
      {error ? <ErrorState compact title="Review action failed" message={error} /> : null}
      <Card>
        <div className="flex flex-wrap items-center justify-between gap-3"><h2 className="text-lg font-semibold text-slate-950">Review player identity</h2><div className="flex items-center gap-2"><Badge variant={confirmed === review.mappings.length && confirmed > 0 ? "success" : "warning"}>{confirmed}/{review.mappings.length} tracks confirmed</Badge><Button size="sm" variant="ghost" disabled={Boolean(busy)} onClick={() => setAttempt((current) => current + 1)}>Refresh review</Button></div></div>
        <p className="mt-2 text-sm leading-6 text-slate-600">Compare each track snapshot with your roster, then choose the player and team. Tracking IDs and jersey suggestions are evidence, not a confirmed identity. Confirming a mapping attaches that track&apos;s results to the selected player.</p>
        {!review.job_id ? <EmptyState compact title="Upload a video first" description="Detected tracks and event suggestions will appear after analysis completes." /> : review.mappings.length === 0 ? <EmptyState compact title="No tracked players available" description="Track evidence will appear when analysis completes and results are saved." /> : <>
          <label className="mt-4 block"><span className="mb-1.5 block text-sm font-semibold text-slate-700">Find a player in this match&apos;s roster</span><Input type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Filter player choices by name" /></label>
          <p className="mt-2 text-xs text-slate-500">Missing a real player? Add them using the match join link first. Correct their team in Assignments before linking a track.</p>
          <div className="mt-5 grid gap-4 lg:grid-cols-2">{review.mappings.map((mapping) => <MappingReviewCard key={`${mapping.id}:${mapping.player_id}:${mapping.team_id}:${mapping.review_status}:${mapping.display_name}`} mapping={mapping} players={players} query={query} teams={teams} disabled={Boolean(busy)} onConfirm={(change) => setConfirmation(change)} />)}</div>
        </>}
      </Card>
      {review.job_id ? <AnalysisQualityPanel quality={review.analysis_quality} /> : null}
      <Card>
        <div className="flex flex-wrap items-center justify-between gap-3"><h2 className="text-lg font-semibold text-slate-950">Review AI event suggestions</h2><select className="h-11 rounded-xl border border-border bg-white px-3 text-sm" aria-label="Event review filter" value={eventFilter} onChange={(event) => { setEventFilter(event.target.value); setEventLimit(24); }}><option value="pending">Needs review</option><option value="confirmed">Confirmed</option><option value="rejected">Rejected</option><option value="all">All events</option></select></div>
        <p className="mt-2 text-sm leading-6 text-slate-600">Watch the clip or check the original video at the shown time before confirming. Rejected suggestions are hidden from public results. Event confirmation does not change the match score.</p>
        {events.length === 0 ? <EmptyState compact title="No events in this view" description="AI suggestions stay pending until an organizer confirms or rejects them." /> : <div className="mt-5 grid gap-4 lg:grid-cols-2">{events.slice(0, eventLimit).map((event) => <article className="rounded-xl border border-border p-4" key={event.id}>
          {event.video_url ? <video className="mb-3 aspect-video w-full rounded-lg bg-slate-950" controls playsInline preload="metadata" src={mediaUrl(event.video_url)} /> : <p className="mb-3 rounded-lg bg-subtle p-3 text-sm text-slate-600">No extracted clip. Check the original video at {formatTimestamp(event.timestamp_ms)}.</p>}
          <div className="flex flex-wrap items-center gap-2"><Badge variant={event.review_status === "confirmed" ? "success" : event.review_status === "rejected" ? "danger" : "warning"}>{event.review_status === "pending" ? "Needs review" : event.review_status}</Badge><span className="text-xs font-semibold text-slate-500">{formatTimestamp(event.timestamp_ms)} · {event.event_type.replaceAll("_", " ")}</span></div>
          <h3 className="mt-3 font-semibold text-slate-950">{reviewedEventTitle(event.title, event.review_status)}</h3><p className="mt-1 text-sm text-slate-600">{players.find((player) => player.id === event.player_id)?.name ?? "Unidentified player"} · {teams.find((team) => team.id === event.team_id)?.name ?? "Unknown team"}</p>
          <div className="mt-4 flex gap-2"><Button size="sm" disabled={Boolean(busy) || event.review_status === "confirmed"} loading={busy === event.id} onClick={() => void reviewEvent(event.id, "confirmed")}>Confirm event</Button><Button size="sm" variant="secondary" disabled={Boolean(busy) || event.review_status === "rejected"} onClick={() => void reviewEvent(event.id, "rejected")}>Reject</Button></div>
        </article>)}</div>}
        {events.length > eventLimit ? <Button className="mt-4" variant="secondary" onClick={() => setEventLimit((current) => current + 24)}>Show more ({events.length - eventLimit} remaining)</Button> : null}
      </Card>
      <ConfirmDialog open={Boolean(confirmation)} busy={Boolean(busy)} title={other ? "Swap player assignments?" : "Confirm player identity?"} description={confirmation ? other ? `${confirmation.playerName} is already assigned to track ${other.provider_track_id}. Confirming will swap the assignments of that track and track ${confirmation.mapping.provider_track_id}. Check both snapshots first.` : `Confirm that track ${confirmation.mapping.provider_track_id} belongs to ${confirmation.playerName} on ${teams.find((team) => team.id === confirmation.teamId)?.name ?? "the selected team"}. The visual evidence must match this person.` : ""} confirmLabel={other ? "Confirm swap" : "Confirm identity"} onCancel={() => { if (!busy) setConfirmation(null); }} onConfirm={() => void confirmMapping()} />
    </section>
  );
}

function MappingReviewCard({ mapping, players, query, teams, disabled, onConfirm }: {
  mapping: TrackReviewItem; players: PlayerOption[]; teams: MatchTeam[]; disabled: boolean;
  query: string;
  onConfirm: (change: MappingChange) => void;
}) {
  const [playerId, setPlayerId] = useState(mapping.player_id ?? "");
  const [playerName, setPlayerName] = useState(mapping.display_name ?? "Unidentified player");
  const [displayName, setDisplayName] = useState(mapping.display_name ?? "");
  const [teamId, setTeamId] = useState(mapping.team_id ?? "");
  const [imageFailed, setImageFailed] = useState(false);
  const evidence = mapping.evidence;
  const choices = players.filter((player) => player.id === playerId || player.name.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase()));
  const validTeamIds = players.find((player) => player.id === playerId)?.teamIds ?? [];
  const selectedPlayer = players.find((player) => player.id === playerId);
  const canRename = Boolean(selectedPlayer?.canRename);
  const rename = canRename && displayName.trim() !== selectedPlayer?.name ? displayName.trim() : undefined;
  const invalidName = rename !== undefined && (rename.length < 2 || rename.length > 100);
  return <article className="rounded-xl border border-border p-4">
    <div className="flex flex-wrap gap-4">
      {evidence?.image_url && !imageFailed ? <Image unoptimized src={mediaUrl(evidence.image_url)} width={160} height={120} className="h-36 w-36 rounded-lg bg-slate-950 object-contain" alt={`Visual evidence for track ${mapping.provider_track_id}`} onError={() => setImageFailed(true)} /> : <div className="grid h-36 w-36 place-items-center rounded-lg bg-subtle p-3 text-center text-xs text-slate-500">Snapshot unavailable. Check the source video to identify this track.</div>}
      <div className="min-w-0 flex-1"><Badge variant={mapping.review_status === "confirmed" ? "success" : "warning"}>{mapping.review_status === "confirmed" ? "Identity confirmed" : "Identity estimated"}</Badge><h3 className="mt-3 break-all font-semibold text-slate-950">Track {mapping.provider_track_id}</h3><p className="mt-1 text-sm text-slate-600">Current label: {mapping.display_name ?? "Unidentified"}</p>
        {evidence?.first_seen_ms !== null && evidence?.first_seen_ms !== undefined ? <p className="mt-1 text-xs text-slate-500">Seen {formatTimestamp(evidence.first_seen_ms)}{evidence.last_seen_ms !== null ? ` – ${formatTimestamp(evidence.last_seen_ms)}` : ""}</p> : null}
        {evidence?.jersey_candidate !== null && evidence?.jersey_candidate !== undefined ? <p className="mt-2 text-xs leading-5 text-slate-600">Jersey suggestion <strong>#{evidence.jersey_candidate}</strong>{evidence.jersey_confidence !== null && evidence.jersey_confidence !== undefined ? ` · ${Math.round(evidence.jersey_confidence * 100)}% OCR confidence` : ""}{evidence.ocr_observations ? ` · ${evidence.ocr_observations} observed frames` : ""}. Needs visual confirmation.</p> : null}
      </div>
    </div>
    <div className="mt-4 grid gap-3 sm:grid-cols-2"><label><span className="mb-1 block text-sm font-semibold text-slate-700">Player</span><select className="h-11 w-full rounded-xl border border-border bg-white px-3 text-sm" disabled={disabled} value={playerId} onChange={(event) => { const player = players.find((item) => item.id === event.target.value); setPlayerId(event.target.value); setPlayerName(player?.name ?? "Unidentified player"); setDisplayName(player?.name ?? ""); setTeamId(player?.teamIds[0] ?? ""); }}><option value="">Choose player</option>{playerId && !choices.some((player) => player.id === playerId) ? <option value={playerId}>{playerName}</option> : null}{choices.map((player) => <option value={player.id} key={player.id}>{player.name}</option>)}</select></label>
      <label><span className="mb-1 block text-sm font-semibold text-slate-700">Team</span><select className="h-11 w-full rounded-xl border border-border bg-white px-3 text-sm" disabled={disabled} value={teamId} onChange={(event) => setTeamId(event.target.value)}><option value="">Choose team</option>{teams.filter((team) => validTeamIds.includes(team.id)).map((team) => <option value={team.id} key={team.id}>{team.name}</option>)}</select></label></div>
    {canRename ? <label className="mt-3 block"><span className="mb-1 block text-sm font-semibold text-slate-700">Player name</span><Input value={displayName} disabled={disabled} minLength={2} maxLength={100} onChange={(event) => setDisplayName(event.target.value)} /><span className="mt-1 block text-xs text-slate-500">Replace a temporary label with the player&apos;s real name after checking the snapshot. Account-linked player names are protected.</span></label> : null}
    {invalidName ? <p className="mt-2 text-xs text-danger-700">Enter a player name with 2–100 characters.</p> : null}
    {!evidence?.image_url || imageFailed ? <p className="mt-3 text-xs leading-5 text-warning-800">Run a new analysis to generate usable image evidence before confirming this identity.</p> : null}
    <Button className="mt-4" size="sm" disabled={disabled || !evidence?.image_url || imageFailed || !playerId || !validTeamIds.includes(teamId) || invalidName || (mapping.review_status === "confirmed" && playerId === mapping.player_id && teamId === mapping.team_id && rename === undefined)} onClick={() => onConfirm({ mapping, playerId, teamId, playerName: rename ?? playerName, displayName: rename })}>{mapping.review_status === "confirmed" ? "Correct mapping" : "Review and confirm"}</Button>
  </article>;
}
