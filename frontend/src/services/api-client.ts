import { getApiBaseUrl } from "@/lib/env";
import type {
  ApiProblem,
  ApiResponse,
  AnalyticsLeaderboards,
  DashboardData,
  GlobalPlayerProfile,
  HighlightType,
  JerseyAssignment,
  JoinContext,
  MatchCreated,
  MatchDetail,
  MatchListItem,
  MatchSummary,
  PlayerAnalyticsDetail,
  PlayerComparison,
  PlayerDirectoryItem,
  PlatformHighlight,
  PageResponse,
  ProcessingJob,
  TeamDetail,
  TeamDirectoryItem,
  ServiceHealth,
} from "@/types/api";

export interface MatchListFilters {
  q?: string;
  status?: MatchSummary["status"] | "";
  team_id?: string;
  date_from?: string;
  date_to?: string;
  page?: number;
  page_size?: number;
}

export interface DirectoryFilters {
  q?: string;
  team_id?: string;
  page?: number;
  page_size?: number;
}

export interface AnalyticsFilters {
  team_id?: string;
  date_from?: string;
  date_to?: string;
  minimum_matches?: number;
}

export interface HighlightFilters {
  match_id?: string;
  player_id?: string;
  highlight_type?: HighlightType | "";
  page?: number;
  page_size?: number;
}

export interface CreateMatchInput {
  venue_name: string;
  starts_at: string;
  expected_ends_at: string | null;
  title: string | null;
  team_a_name: string;
  team_b_name: string;
}

export interface CreateAssignmentInput {
  team_id: string;
  player_id?: string;
  display_name?: string;
  jersey_number: number;
}

export interface CorrectAssignmentInput {
  team_id?: string;
  jersey_number?: number;
  close_only?: boolean;
  override_conflict?: boolean;
  override_reason?: string;
  override_actor?: string;
}

export interface UpdateMatchStateInput {
  status: MatchSummary["status"];
  home_score: number | null;
  away_score: number | null;
  ended_at?: string | null;
}

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly problem?: ApiProblem,
  ) {
    super(problem?.detail ?? `API request failed with status ${status}.`);
    this.name = "ApiError";
  }
}

async function request<T>(
  path: `/${string}`,
  init: RequestInit = {},
): Promise<T> {
  const response = await fetch(`${getApiBaseUrl()}${path}`, {
    ...init,
    headers: {
      Accept: "application/json",
      ...init.headers,
    },
  });

  if (!response.ok) {
    const isJson = response.headers
      .get("content-type")
      ?.includes("application/problem+json");
    const problem = isJson
      ? ((await response.json()) as ApiProblem)
      : undefined;
    throw new ApiError(response.status, problem);
  }

  return (await response.json()) as T;
}

function withQuery(path: `/${string}`, values: object) {
  const query = new URLSearchParams();
  Object.entries(values).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      query.set(key, String(value));
    }
  });
  const serialized = query.toString();
  return (serialized ? `${path}?${serialized}` : path) as `/${string}`;
}

export const api = {
  getHealth(signal?: AbortSignal) {
    return request<ApiResponse<ServiceHealth>>("/api/v1/health", { signal });
  },
  getDashboard(signal?: AbortSignal) {
    return request<ApiResponse<DashboardData>>("/api/v1/public/dashboard", {
      signal,
    });
  },
  getPlatformMatches(filters: MatchListFilters, signal?: AbortSignal) {
    return request<ApiResponse<PageResponse<MatchListItem>>>(
      withQuery("/api/v1/public/matches", filters),
      { signal },
    );
  },
  getPlayers(filters: DirectoryFilters, signal?: AbortSignal) {
    return request<ApiResponse<PageResponse<PlayerDirectoryItem>>>(
      withQuery("/api/v1/public/players", filters),
      { signal },
    );
  },
  getPlayerProfile(playerId: string, signal?: AbortSignal) {
    return request<ApiResponse<GlobalPlayerProfile>>(
      `/api/v1/public/players/${playerId}`,
      { signal },
    );
  },
  getTeams(
    filters: Omit<DirectoryFilters, "team_id">,
    signal?: AbortSignal,
  ) {
    return request<ApiResponse<PageResponse<TeamDirectoryItem>>>(
      withQuery("/api/v1/public/teams", filters),
      { signal },
    );
  },
  getTeam(teamId: string, signal?: AbortSignal) {
    return request<ApiResponse<TeamDetail>>(
      `/api/v1/public/teams/${teamId}`,
      { signal },
    );
  },
  getAnalytics(filters: AnalyticsFilters, signal?: AbortSignal) {
    return request<ApiResponse<AnalyticsLeaderboards>>(
      withQuery("/api/v1/public/analytics/leaderboards", filters),
      { signal },
    );
  },
  getHighlights(filters: HighlightFilters, signal?: AbortSignal) {
    return request<ApiResponse<PageResponse<PlatformHighlight>>>(
      withQuery("/api/v1/public/highlights", filters),
      { signal },
    );
  },
  createMatch(input: CreateMatchInput) {
    return request<ApiResponse<MatchCreated>>("/api/v1/matches", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    });
  },
  getJoinContext(token: string, signal?: AbortSignal) {
    return request<ApiResponse<JoinContext>>(
      `/api/v1/join/${encodeURIComponent(token)}`,
      { signal },
    );
  },
  createAssignment(token: string, input: CreateAssignmentInput) {
    return request<ApiResponse<JerseyAssignment>>(
      `/api/v1/join/${encodeURIComponent(token)}/assignments`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(input),
      },
    );
  },
  getMatch(matchId: string, organizerToken: string, signal?: AbortSignal) {
    return request<ApiResponse<MatchSummary>>(`/api/v1/matches/${matchId}`, {
      signal,
      headers: { "X-Organizer-Token": organizerToken },
    });
  },
  getPublicMatchDetail(matchId: string, signal?: AbortSignal) {
    return request<ApiResponse<MatchDetail>>(
      `/api/v1/public/matches/${matchId}`,
      { signal },
    );
  },
  getPlayerAnalytics(
    matchId: string,
    playerId: string,
    signal?: AbortSignal,
  ) {
    return request<ApiResponse<PlayerAnalyticsDetail>>(
      `/api/v1/public/matches/${matchId}/players/${playerId}/analytics`,
      { signal },
    );
  },
  comparePlayers(
    matchId: string,
    leftPlayerId: string,
    rightPlayerId: string,
    signal?: AbortSignal,
  ) {
    const query = new URLSearchParams({
      left_player_id: leftPlayerId,
      right_player_id: rightPlayerId,
    });
    return request<ApiResponse<PlayerComparison>>(
      `/api/v1/public/matches/${matchId}/players/compare?${query}`,
      { signal },
    );
  },
  updateMatchState(
    matchId: string,
    organizerToken: string,
    input: UpdateMatchStateInput,
  ) {
    return request<ApiResponse<MatchSummary>>(`/api/v1/matches/${matchId}`, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
        "X-Organizer-Token": organizerToken,
      },
      body: JSON.stringify(input),
    });
  },
  createProcessingJob(
    matchId: string,
    organizerToken: string,
    video: File,
  ) {
    const body = new FormData();
    body.append("video", video);
    return request<ApiResponse<ProcessingJob>>(
      `/api/v1/matches/${matchId}/processing-jobs`,
      {
        method: "POST",
        headers: { "X-Organizer-Token": organizerToken },
        body,
      },
    );
  },
  getProcessingJobs(
    matchId: string,
    organizerToken: string,
    signal?: AbortSignal,
  ) {
    return request<ApiResponse<ProcessingJob[]>>(
      `/api/v1/matches/${matchId}/processing-jobs`,
      {
        signal,
        headers: { "X-Organizer-Token": organizerToken },
      },
    );
  },
  retryProcessingJob(jobId: string, organizerToken: string) {
    return request<ApiResponse<ProcessingJob>>(
      `/api/v1/processing-jobs/${jobId}/retry`,
      {
        method: "POST",
        headers: { "X-Organizer-Token": organizerToken },
      },
    );
  },
  getAssignments(
    matchId: string,
    organizerToken: string,
    signal?: AbortSignal,
  ) {
    return request<ApiResponse<JerseyAssignment[]>>(
      `/api/v1/matches/${matchId}/assignments`,
      {
        signal,
        headers: { "X-Organizer-Token": organizerToken },
      },
    );
  },
  correctAssignment(
    matchId: string,
    assignmentId: string,
    organizerToken: string,
    input: CorrectAssignmentInput,
  ) {
    return request<ApiResponse<JerseyAssignment>>(
      `/api/v1/matches/${matchId}/assignments/${assignmentId}`,
      {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          "X-Organizer-Token": organizerToken,
        },
        body: JSON.stringify(input),
      },
    );
  },
  changeJersey(
    matchId: string,
    assignmentId: string,
    organizerToken: string,
    input: CorrectAssignmentInput,
  ) {
    return request<ApiResponse<JerseyAssignment>>(
      `/api/v1/matches/${matchId}/assignments/${assignmentId}/change-jersey`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Organizer-Token": organizerToken,
        },
        body: JSON.stringify(input),
      },
    );
  },
};
