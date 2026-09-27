export interface ApiResponse<T> {
  data: T;
  timestamp: string;
}

export interface ApiProblem {
  type?: string;
  title: string;
  status: number;
  detail: string;
  instance?: string;
  errorCode?: string;
  timestamp?: string;
  errors?: Record<string, string>;
}

export interface ServiceHealth {
  status: "UP" | "DOWN";
  service: string;
}

export interface MatchTeam {
  id: string;
  name: string;
  side: "home" | "away" | null;
}

export interface MatchSummary {
  id: string;
  title: string | null;
  venue_name: string;
  starts_at: string;
  expected_ends_at: string | null;
  ended_at: string | null;
  home_score: number | null;
  away_score: number | null;
  status:
    | "scheduled"
    | "live"
    | "processing"
    | "completed"
    | "failed"
    | "cancelled";
  teams: MatchTeam[];
}

export interface PlayerSummary {
  id: string;
  display_name: string;
}

export interface JerseyAssignment {
  id: string;
  match_id: string;
  team: MatchTeam;
  player: PlayerSummary;
  jersey_number: number;
  started_at: string;
  ended_at: string | null;
  supersedes_id: string | null;
  conflict_override: boolean;
  override_actor: string | null;
  override_reason: string | null;
}

export interface MatchCreated {
  match: MatchSummary;
  join_token: string;
  organizer_token: string;
}

export interface JoinContext {
  match: MatchSummary;
  players: PlayerSummary[];
}

export interface JerseyHistoryItem {
  assignment_id: string;
  jersey_number: number;
  started_at: string;
  ended_at: string | null;
}

export interface MatchPlayer {
  id: string;
  display_name: string;
  team: MatchTeam;
  current_jersey: number | null;
  jersey_history: JerseyHistoryItem[];
  rating: number | null;
  distance_m: number | null;
  avg_speed_kmh: number | null;
  max_speed_kmh: number | null;
  sprint_count: number | null;
  active_seconds: number | null;
  activity_count: number | null;
  peak_speed_at_ms: number | null;
  analytics_status: AnalyticsStatus;
}

export type AnalyticsStatus =
  | "processing"
  | "available"
  | "unavailable"
  | "failed";

export interface PositionSample {
  timestamp_ms: number;
  x: number;
  y: number;
}

export interface IntensityBucket {
  from_minute: number;
  to_minute: number;
  intensity: number;
}

export interface PlayerAnalyticsEvent {
  id: string;
  event_type:
    | "sprint"
    | "peak_speed"
    | "high_intensity_period"
    | "custom";
  timestamp_ms: number;
  speed_kmh: number | null;
  title: string;
}

export interface PlayerAnalyticsDetail {
  match: MatchSummary;
  player: MatchPlayer;
  position_samples: PositionSample[];
  intensity_buckets: IntensityBucket[];
  events: PlayerAnalyticsEvent[];
}

export interface PlayerComparison {
  left: MatchPlayer;
  right: MatchPlayer;
}

export type ProcessingStatus =
  | "queued"
  | "processing"
  | "completed"
  | "failed"
  | "cancelled";

export type ProcessingStage =
  | "queued"
  | "uploading"
  | "validating"
  | "preprocessing"
  | "detecting_players"
  | "tracking_players"
  | "calibrating_field"
  | "calculating_metrics"
  | "persisting_results"
  | "completed";

export interface ProcessingJob {
  id: string;
  match_id: string;
  retry_of_id: string | null;
  status: ProcessingStatus;
  progress: number | null;
  stage: ProcessingStage;
  source_type: "uploaded_video";
  provider: string;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  failed_at: string | null;
  error_code: string | null;
  error_message: string | null;
}

export interface PageResponse<T> {
  items: T[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
}

export interface MatchListItem {
  match: MatchSummary;
  has_analytics: boolean;
}

export interface PlayerPerformanceSummary {
  match_id: string;
  match_title: string | null;
  venue_name: string;
  starts_at: string;
  team: MatchTeam;
  rating: number | null;
  distance_m: number | null;
  avg_speed_kmh: number | null;
  max_speed_kmh: number | null;
  sprint_count: number | null;
  active_seconds: number | null;
}

export interface PlayerDirectoryItem {
  id: string;
  display_name: string;
  is_temporary: boolean;
  recent_performance: PlayerPerformanceSummary | null;
}

export interface GlobalPlayerProfile {
  id: string;
  display_name: string;
  is_temporary: boolean;
  recent_performances: PlayerPerformanceSummary[];
}

export interface TeamDirectoryItem {
  id: string;
  name: string;
  player_count: number;
  match_count: number;
}

export interface TeamDetail {
  team: TeamDirectoryItem;
  players: PlayerDirectoryItem[];
  recent_matches: MatchListItem[];
}

export type HighlightType =
  | "goal"
  | "top_run"
  | "sprint"
  | "key_moment"
  | "manual"
  | "ai_detected";

export interface PlatformHighlight {
  id: string;
  match_id: string;
  match_title: string | null;
  player_id: string | null;
  player_name: string | null;
  highlight_type: HighlightType;
  timestamp_ms: number;
  title: string;
  video_url: string | null;
  thumbnail_url: string | null;
  duration_ms: number | null;
  created_at: string;
}

export interface LeaderboardEntry {
  player_id: string;
  display_name: string;
  match_count: number;
  value: number;
}

export interface TeamAnalyticsSummary {
  team_id: string;
  team_name: string;
  match_count: number;
  total_distance_m: number | null;
  average_speed_kmh: number | null;
  maximum_speed_kmh: number | null;
  sprint_count: number | null;
}

export interface AnalyticsLeaderboards {
  rating_leaders: LeaderboardEntry[];
  distance_leaders: LeaderboardEntry[];
  speed_leaders: LeaderboardEntry[];
  sprint_leaders: LeaderboardEntry[];
  team_analytics: TeamAnalyticsSummary[];
  date_from: string | null;
  date_to: string | null;
}

export interface DashboardData {
  quick_stats: {
    total_matches: number;
    completed_matches: number;
    total_players: number;
    total_teams: number;
    processed_matches: number;
  };
  recent_matches: MatchListItem[];
  upcoming_matches: MatchListItem[];
  processing_matches: MatchListItem[];
  top_players: LeaderboardEntry[];
  latest_highlights: PlatformHighlight[];
}

export interface TeamStats {
  team_id: string;
  total_distance_m: number | null;
  average_speed_kmh: number | null;
  maximum_speed_kmh: number | null;
  sprint_count: number | null;
  active_time_seconds: number | null;
}

export interface TimelineEvent {
  id: string;
  event_type:
    | "goal"
    | "substitution"
    | "jersey_change"
    | "high_intensity"
    | "ai_moment"
    | "custom";
  occurred_at: string;
  minute: number | null;
  title: string;
  description: string | null;
  player_id: string | null;
  team_id: string | null;
}

export interface MatchHighlight {
  id: string;
  highlight_type: string;
  title: string;
  video_url: string | null;
  thumbnail_url: string | null;
  duration_seconds: number | null;
  occurred_at: string | null;
  player_id: string | null;
}

export interface MatchDetail {
  match: MatchSummary;
  players: MatchPlayer[];
  team_stats: TeamStats[] | null;
  events: TimelineEvent[];
  highlights: MatchHighlight[];
}

export type UserRole = "user" | "admin";

export interface AuthUser {
  id: string;
  email: string;
  role: UserRole;
  player_id: string | null;
  created_at: string;
}

export interface AuthSession {
  user: AuthUser;
  access_token: string;
  token_type: "bearer";
  expires_at: string;
}

export interface AdminDashboard {
  total_matches: number;
  total_users: number;
  total_players: number;
  total_teams: number;
  failed_jobs: number;
  active_jobs: number;
  recent_matches: MatchListItem[];
}
