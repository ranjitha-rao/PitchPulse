export type TeamId = "hfc" | "nga";
export type Mode = "casual" | "analyst" | "player";
export type Lang = "en" | "es" | "ar";

export interface PlayerMeta {
  id: string;
  name: string;
  short: string;
  number: number;
  position: string;
  slot: [number, number];
}

export interface TeamMeta {
  id: TeamId;
  name: string;
  short: string;
  formation: string;
  color: string;
  players: PlayerMeta[];
}

export interface Meta {
  match: Record<string, string>;
  teams: Record<TeamId, TeamMeta>;
  langs: Lang[];
  modes: Mode[];
  model_captions: boolean;
  agents: AgentMeta[];
  event_count: number;
}

export interface MatchEvent {
  event_id: string;
  clock_ms: number;
  period: number;
  type: string;
  team_id: TeamId | null;
  player_id: string | null;
  receiver_id?: string;
  start_xy?: [number, number];
  end_xy?: [number, number];
  outcome?: string;
  ball_speed_kmh?: number;
  qualifiers?: Record<string, unknown>;
}

export interface AgentMeta {
  id: string;
  name: string;
  role: string;
}

export interface TraceStep {
  agent: string;
  action: string;
  detail: string;
  ok: boolean | null;
}

export interface Fact {
  id: string;
  label?: string;
  value: string | number | boolean;
  unit?: string;
}

export interface Cue {
  cue_id: string;
  version: number;
  clock_in_ms: number;
  minute: number;
  duration_ms: number;
  slot: "banner" | "lower_third" | "player_tag" | "stat_bug" | "player_card";
  template: string;
  priority: number;
  mode: Mode;
  team_id: TeamId | null;
  player_id: string | null;
  data: Record<string, unknown>;
  text: Partial<Record<Lang, string>>;
  variants?: Record<"casual" | "analyst", Partial<Record<Lang, string>>>;
  dir: Partial<Record<Lang, "rtl" | "ltr">>;
  explain: { facts: Fact[]; drivers: string[]; storyline: string | null };
  source: "template" | "model";
  trace?: TraceStep[];
  name?: string;
  receivedAt?: number;
}

export interface TimelinePoint {
  minute: number;
  win_prob: { home: number; draw: number; away: number };
  control_diff: number;
  chaos: number;
  pressure_index: Record<TeamId, number>;
  field_tilt_home: number;
  tempo: number;
  xg: Record<TeamId, number>;
  score: Record<TeamId, number>;
}

export interface MatchState {
  clock_ms: number;
  period: number;
  score: Record<TeamId, number>;
  win_prob: { home: number; draw: number; away: number };
  rolling: {
    control: Record<TeamId, number>;
    pressure_index: Record<TeamId, number>;
    completion: Record<TeamId, number>;
    chaos: number;
    control_diff: number;
    field_tilt_home: number;
    tempo: number;
    xg_share_home: number;
    possession_home: number;
  } | null;
  teams: Record<TeamId, Record<string, number>>;
  records: Record<string, { value: number; player_id: string; clock_ms: number } | null>;
}

export interface Recap {
  title: string;
  lines: string[];
  text: string;
}

export interface Profile {
  mode: Mode;
  club: TeamId | null;
  player: string | null;
  lang: Lang;
}
