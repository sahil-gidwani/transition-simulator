// TypeScript mirrors of the server's Pydantic response models (server/app/schemas/).
// Dates arrive as ISO "YYYY-MM-DD" strings; all EUR amounts are integers.

export interface DataBuildInfo {
  repo: string;
  revision: string;
  built_at: string;
  max_valuation_date: string;
  censor_horizon: string;
  comps_universe_size: number;
}

export interface Health {
  status: string;
  version: string;
  data: DataBuildInfo;
}

export interface PlayerSearchResult {
  player_id: number;
  name: string;
  age: number | null;
  position_group: string;
  sub_position: string | null;
  club_name: string;
  league_id: string;
  league_name: string | null;
  market_value_eur: number | null;
  market_value_asof: string | null;
}

export interface ValuePoint {
  date: string;
  value_eur: number;
}

export interface PlayerProfile {
  player_id: number;
  name: string;
  position_group: string;
  sub_position: string | null;
  date_of_birth: string | null;
  age: number | null;
  foot: string | null;
  height_cm: number | null;
  club_id: number;
  club_name: string;
  league_id: string;
  league_name: string | null;
  league_tier: number | null;
  last_season: number;
  market_value_eur: number | null;
  market_value_asof: string | null;
  value_history: ValuePoint[];
}

export type Direction = 'higher_better' | 'lower_better';

export interface MetricPercentile {
  metric: string;
  label: string;
  value: number | null;
  /** Already display-oriented: always "better than X% of peers". Never re-invert. */
  percentile: number | null;
  direction: Direction;
  peer_n: number;
}

export interface PercentilesResponse {
  player_id: number;
  has_stats: boolean;
  season: number | null;
  league_id: string | null;
  minutes: number | null;
  games_played: number | null;
  below_floor: boolean;
  metrics: MetricPercentile[];
}

export interface DestinationClub {
  club_id: number;
  name: string;
  /** Squad-value rank within the league-season: 1 = top third, 3 = bottom third. */
  tercile: number;
  elo_available: boolean;
}

export interface DestinationLeague {
  league_id: string;
  name: string;
  country: string | null;
  tier: number;
  clubs: DestinationClub[];
}

export interface DestinationsResponse {
  season: number;
  leagues: DestinationLeague[];
}

export interface DestinationSpec {
  league_id: string;
  club_id?: number | null;
}

export interface SimulationRequest {
  player_id: number;
  destination: DestinationSpec;
}

export interface SimPlayer {
  player_id: number;
  name: string;
  position_group: string;
  sub_position: string | null;
  age: number | null;
  market_value_eur: number;
  market_value_asof: string | null;
}

export interface SimDestination {
  league_id: string;
  league_name: string;
  country: string | null;
  tier: number;
  club_id: number | null;
  club_name: string | null;
  club_tercile: number | null;
}

export interface Prediction {
  low_eur: number;
  mid_eur: number;
  high_eur: number;
  low_multiplier: number;
  mid_multiplier: number;
  high_multiplier: number;
  horizon_months: 12;
}

export interface CompCard {
  player_id: number;
  player_name: string;
  season: number;
  transfer_date: string;
  age_at_transfer: number | null;
  from_club: string;
  to_club: string;
  from_league: string | null;
  to_league: string;
  v_before_eur: number;
  v_after_eur: number;
  multiplier: number;
  /** Fraction: -0.3 means the value fell 30%. */
  delta_pct: number;
  similarity: number;
  tags: string[];
}

export interface PoolQuality {
  pool_size: number;
  relaxation_level: number;
  relaxation_steps: string[];
  expanded_search: boolean;
  club_selected: boolean;
  elo_pool_coverage: number;
  dest_elo_available: boolean;
  missing_age: boolean;
  missing_minutes: boolean;
  origin_tier_unknown: boolean;
  /** The chosen club returned the league-only pool with a near-identical midpoint. */
  club_indistinct: boolean;
}

export type Confidence = 'high' | 'medium' | 'low' | 'insufficient';

export type Direction = 'rise' | 'decline' | 'flat';

export interface SimulationResponse {
  player: SimPlayer;
  destination: SimDestination;
  prediction: Prediction | null;
  /** Served verdict direction (from the server's thresholds); null iff insufficient. */
  direction: Direction | null;
  confidence: Confidence;
  insufficient_precedent: boolean;
  /** The full quantile pool, most similar first; the range is computed from exactly these. */
  comps: CompCard[];
  /** UI default: render this many comps up front, the rest behind an expander. */
  shown_comps: number;
  pool_quality: PoolQuality;
  narrative: string;
}
