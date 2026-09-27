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
  status: "scheduled" | "live" | "completed" | "cancelled";
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
