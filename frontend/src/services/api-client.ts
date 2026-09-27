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
  AuthSession,
  AuthUser,
  AdminDashboard,
  UserRole,
} from "@/types/api";
import { getSessionToken, setSessionToken } from "@/lib/session";

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

function withAuthHeaders(init: RequestInit = {}): Headers {
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
  const session = getSessionToken();
  if (session && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${session}`);
  }
  return headers;
}

async function request<T>(
  path: `/${string}`,
  init: RequestInit = {},
): Promise<T> {
  const response = await fetch(`${getApiBaseUrl()}${path}`, {
    ...init,
    headers: withAuthHeaders(init),
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

  if (response.status === 204) {
    return undefined as T;
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
  register(email: string, password: string) {
    return request<ApiResponse<AuthSession>>("/api/v1/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
  },
  login(email: string, password: string) {
    return request<ApiResponse<AuthSession>>("/api/v1/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
  },
  logout() {
    return request<void>("/api/v1/auth/logout", { method: "POST" }).finally(() => {
      setSessionToken(null);
    });
  },
  getMe(signal?: AbortSignal) {
    return request<ApiResponse<AuthUser>>("/api/v1/auth/me", { signal });
  },
  getAdminDashboard(signal?: AbortSignal) {
    return request<ApiResponse<AdminDashboard>>("/api/v1/admin/dashboard", {
      signal,
    });
  },
  getAdminUsers(filters: DirectoryFilters, signal?: AbortSignal) {
    return request<ApiResponse<PageResponse<AuthUser>>>(
      withQuery("/api/v1/admin/users", filters),
      { signal },
    );
  },
  updateUserRole(userId: string, role: UserRole) {
    return request<ApiResponse<AuthUser>>(`/api/v1/admin/users/${userId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ role }),
    });
  },
  getAdminMatches(filters: MatchListFilters, signal?: AbortSignal) {
    return request<ApiResponse<PageResponse<MatchListItem>>>(
      withQuery("/api/v1/admin/matches", filters),
      { signal },
    );
  },
  getAdminPlayers(filters: DirectoryFilters, signal?: AbortSignal) {
    return request<ApiResponse<PageResponse<PlayerDirectoryItem>>>(
      withQuery("/api/v1/admin/players", filters),
      { signal },
    );
  },
  getAdminTeams(filters: Omit<DirectoryFilters, "team_id">, signal?: AbortSignal) {
    return request<ApiResponse<PageResponse<TeamDirectoryItem>>>(
      withQuery("/api/v1/admin/teams", filters),
      { signal },
    );
  },
  getAdminJobs(
    filters: { status?: string; page?: number; page_size?: number },
    signal?: AbortSignal,
  ) {
    return request<ApiResponse<PageResponse<ProcessingJob>>>(
      withQuery("/api/v1/admin/jobs", filters),
      { signal },
    );
  },
  retryAdminJob(jobId: string) {
    return request<ApiResponse<ProcessingJob>>(
      `/api/v1/admin/jobs/${jobId}/retry`,
      { method: "POST" },
    );
  },
  getAdminHighlights(filters: HighlightFilters, signal?: AbortSignal) {
    return request<ApiResponse<PageResponse<PlatformHighlight>>>(
      withQuery("/api/v1/admin/highlights", filters),
      { signal },
    );
  },
  createAdminHighlight(input: {
    match_id: string;
    player_id?: string | null;
    highlight_type: HighlightType;
    timestamp_ms: number;
    title: string;
    video_url?: string | null;
    thumbnail_url?: string | null;
    duration_ms?: number | null;
  }) {
    return request<ApiResponse<PlatformHighlight>>("/api/v1/admin/highlights", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    });
  },
  updateAdminHighlight(
    highlightId: string,
    input: { title?: string; highlight_type?: HighlightType },
  ) {
    return request<ApiResponse<PlatformHighlight>>(
      `/api/v1/admin/highlights/${highlightId}`,
      {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(input),
      },
    );
  },
  deleteAdminHighlight(highlightId: string) {
    return request<void>(`/api/v1/admin/highlights/${highlightId}`, {
      method: "DELETE",
    });
  },
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
  getMatch(matchId: string, organizerToken?: string | null, signal?: AbortSignal) {
    return request<ApiResponse<MatchSummary>>(`/api/v1/matches/${matchId}`, {
      signal,
      headers: organizerToken ? { "X-Organizer-Token": organizerToken } : undefined,
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
    organizerToken: string | null | undefined,
    input: UpdateMatchStateInput,
  ) {
    return request<ApiResponse<MatchSummary>>(`/api/v1/matches/${matchId}`, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
        ...(organizerToken ? { "X-Organizer-Token": organizerToken } : {}),
      },
      body: JSON.stringify(input),
    });
  },
  createProcessingJob(
    matchId: string,
    organizerToken: string | null | undefined,
    video: File,
  ) {
    const body = new FormData();
    body.append("video", video);
    return request<ApiResponse<ProcessingJob>>(
      `/api/v1/matches/${matchId}/processing-jobs`,
      {
        method: "POST",
        headers: organizerToken ? { "X-Organizer-Token": organizerToken } : undefined,
        body,
      },
    );
  },
  getProcessingJobs(
    matchId: string,
    organizerToken?: string | null,
    signal?: AbortSignal,
  ) {
    return request<ApiResponse<ProcessingJob[]>>(
      `/api/v1/matches/${matchId}/processing-jobs`,
      {
        signal,
        headers: organizerToken ? { "X-Organizer-Token": organizerToken } : undefined,
      },
    );
  },
  retryProcessingJob(jobId: string, organizerToken?: string | null) {
    return request<ApiResponse<ProcessingJob>>(
      `/api/v1/processing-jobs/${jobId}/retry`,
      {
        method: "POST",
        headers: organizerToken ? { "X-Organizer-Token": organizerToken } : undefined,
      },
    );
  },
  getAssignments(
    matchId: string,
    organizerToken?: string | null,
    signal?: AbortSignal,
  ) {
    return request<ApiResponse<JerseyAssignment[]>>(
      `/api/v1/matches/${matchId}/assignments`,
      {
        signal,
        headers: organizerToken ? { "X-Organizer-Token": organizerToken } : undefined,
      },
    );
  },
  correctAssignment(
    matchId: string,
    assignmentId: string,
    organizerToken: string | null | undefined,
    input: CorrectAssignmentInput,
  ) {
    return request<ApiResponse<JerseyAssignment>>(
      `/api/v1/matches/${matchId}/assignments/${assignmentId}`,
      {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          ...(organizerToken ? { "X-Organizer-Token": organizerToken } : {}),
        },
        body: JSON.stringify(input),
      },
    );
  },
  changeJersey(
    matchId: string,
    assignmentId: string,
    organizerToken: string | null | undefined,
    input: CorrectAssignmentInput,
  ) {
    return request<ApiResponse<JerseyAssignment>>(
      `/api/v1/matches/${matchId}/assignments/${assignmentId}/change-jersey`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(organizerToken ? { "X-Organizer-Token": organizerToken } : {}),
        },
        body: JSON.stringify(input),
      },
    );
  },
};
