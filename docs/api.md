# API reference

Six endpoints under `/api`, JSON only. All examples below were captured verbatim from a
local server running the pinned build (`built_at` 2026-07-18); long lists are trimmed where
marked. Response shapes are the Pydantic models in `server/app/schemas/`.

Guarantees that hold for every response:

| Guarantee | Mechanism |
|---|---|
| Every number traces to named comps | the full quantile pool is returned in `comps`, not just the headline range |
| Ranges, never single numbers | `prediction` carries low/mid/high; there is no point-estimate field |
| Fewer than 2 usable comps ⇒ no range | `prediction` and `direction` are `null`, `confidence` is `insufficient` |
| Widened searches say so | `pool_quality.relaxation_steps` carries the exact ladder labels |
| Stale data is dated, not hidden | valuations carry `market_value_asof`; the build carries `max_valuation_date` |

Errors always use one envelope — see [Errors](#errors). Semantics of the engine fields
(ladder, confidence, club honesty) are specified in [methodology.md](methodology.md).

## GET /api/health

Liveness plus the data build's identity — answers only once the artifacts are loaded, so it
doubles as the readiness probe.

```json
{
  "status": "ok",
  "version": "0.1.0",
  "data": {
    "repo": "ngeorgea/transfermarkt-player-scores",
    "revision": "7dbc5b38ba6efdc439933b00c2f4b4a7405dd681",
    "built_at": "2026-07-18T18:43:24+00:00",
    "max_valuation_date": "2026-06-12",
    "censor_horizon": "2025-12-14",
    "comps_universe_size": 19407
  }
}
```

## GET /api/players/search?q=

Search semantics:

- Fewer than 2 characters after normalization returns `[]` (never an error).
- Ranking: full-name prefix match beats token-prefix match beats any-substring match;
  within a rank, results sort by market value descending (nulls last), capped at 20.
- Diacritics fold to bare letters — `q=ozil` finds Mesut Özil. (The fold deliberately
  differs from the pipeline's club-name matcher; see
  [architecture.md](architecture.md#cross-cutting-plumbing).)

`value_delta_12m` is the 12-month value trend: current value divided by the latest
valuation dated at least 365 days ago, minus 1 (`0.2` = +20%). It is `null` when no
baseline that old exists, and zero-value baselines are skipped.

`GET /api/players/search?q=maddison`:

```json
[
  {
    "player_id": 294057,
    "name": "James Maddison",
    "age": 29,
    "position_group": "MID",
    "sub_position": "Attacking Midfield",
    "club_name": "Tottenham Hotspur Football Club",
    "league_id": "GB1",
    "league_name": "Premier League",
    "market_value_eur": 20000000,
    "market_value_asof": "2026-06-03",
    "value_delta_12m": -0.5238095238095238
  },
  { "player_id": 221561, "name": "Marcus Maddison", "…": "… trimmed (2 more results)" }
]
```

## GET /api/players/{player_id}

Full profile: bio, current value with as-of date, the complete valuation history behind the
profile chart, and the player's own transfers for chart annotation.

`GET /api/players/294057` (value history trimmed — the real response carries all 35
points):

```json
{
  "player_id": 294057,
  "name": "James Maddison",
  "position_group": "MID",
  "sub_position": "Attacking Midfield",
  "date_of_birth": "1996-11-23",
  "age": 29,
  "foot": "right",
  "height_cm": 175,
  "club_id": 148,
  "club_name": "Tottenham Hotspur Football Club",
  "league_id": "GB1",
  "league_name": "Premier League",
  "league_tier": 1,
  "last_season": 2025,
  "market_value_eur": 20000000,
  "market_value_asof": "2026-06-03",
  "value_history": [
    { "date": "2014-10-26", "value_eur": 50000 },
    { "date": "2023-10-09", "value_eur": 70000000 },
    { "date": "2026-06-03", "value_eur": 20000000 }
  ],
  "transfers": [
    { "date": "2018-07-01", "from_club": "Norwich", "to_club": "Leicester" },
    { "date": "2023-07-01", "from_club": "Leicester", "to_club": "Tottenham" }
  ]
}
```

Unknown id → 404 `player_not_found`.

## GET /api/players/{player_id}/percentiles

Performance percentiles vs same-position, same-league peers for the player's latest
season. **Percentiles arrive display-oriented** — always "better than X% of peers", with
lower-is-better metrics (cards, goals conceded) already flipped server-side; clients must
never re-invert them. `direction` states which way the *raw value* reads, for sublabels
only.

Below the 450-minute floor, `below_floor` is `true` and every `percentile` is `null` — a
thin sample is flagged, not ranked. `GET /api/players/418560/percentiles`:

```json
{
  "player_id": 418560,
  "has_stats": true,
  "season": 2025,
  "league_id": "GB1",
  "minutes": 2959,
  "games_played": 35,
  "below_floor": false,
  "metrics": [
    { "metric": "goals_p90", "label": "Goals / 90", "value": 0.8212233781814575, "percentile": 100, "direction": "higher_better", "peer_n": 109 },
    { "metric": "assists_p90", "label": "Assists / 90", "value": 0.24332544207572937, "percentile": 81, "direction": "higher_better", "peer_n": 109 },
    { "metric": "ga_p90", "label": "Goals + assists / 90", "value": 1.0645488500595093, "percentile": 99, "direction": "higher_better", "peer_n": 109 },
    { "metric": "cards_p90", "label": "Cards / 90", "value": 0.06083136051893234, "percentile": 76, "direction": "lower_better", "peer_n": 109 }
  ]
}
```

Goalkeepers additionally get `conceded_p90` and `clean_sheet_rate` metrics.

## GET /api/destinations

Every league (with strength and median squad value) and its clubs (with squad value,
within-league value percentile, and whether an Elo rating is available) for the latest
season — the data behind the destination picker, so the UI can show the money behind the
choice. Trimmed to one league and two clubs:

```json
{
  "season": 2025,
  "leagues": [
    {
      "league_id": "ES1",
      "name": "Laliga",
      "country": "Spain",
      "tier": 1,
      "strength": 18.660091267730447,
      "median_squad_value_eur": 127050000,
      "clubs": [
        { "club_id": 418, "name": "Real Madrid Club de Fútbol", "tercile": 1, "squad_value_eur": 1205500000, "club_value_pct": 1.0, "elo_available": true },
        { "club_id": 3368, "name": "Levante Unión Deportiva S.A.D.", "tercile": 3, "squad_value_eur": 26700000, "club_value_pct": 0.05263157933950424, "elo_available": true }
      ]
    }
  ]
}
```

## POST /api/simulations

Body: `{"player_id": <int>, "destination": {"league_id": <str>, "club_id": <int, optional>}}`.

Response fields:

| Field | Meaning |
|---|---|
| `player`, `destination` | Echo of the resolved query (destination includes league tier and, if a club was chosen, its name and tercile) |
| `prediction` | The range — `low/mid/high_eur` and the underlying multipliers, `horizon_months` always 12. **`null` exactly when precedent is insufficient** |
| `direction` | `rise` / `decline` / `flat`, served so the UI arrow and the narrative can never disagree; `null` exactly when there is no range |
| `confidence` | `high` / `medium` / `low` / `insufficient` (tier definitions: [methodology.md](methodology.md#confidence-direction-refusal)) |
| `insufficient_precedent` | `true` iff `prediction` is `null` |
| `comps` | **The full quantile pool** (up to 41), ranked by similarity — every comp that shaped the range, decliners included |
| `shown_comps` | Server-driven UI default for how many comps to show expanded (6) |
| `pool_quality` | Search honesty: pool size, relaxation level and exact step labels, `expanded_search`, per-field nullability flags (`missing_age`, `missing_minutes`, `origin_tier_unknown`), `club_selected`, `elo_pool_coverage` (share of the pool where the Elo term was actually used), `dest_elo_available` (chosen club has a rating), `club_indistinct`, `club_standing_support` |
| `narrative` | The scout's read, assembled deterministically from the same fields |

Club-honesty field semantics: `club_indistinct` is `true` when the chosen club's midpoint
sits within the drift threshold of the league-only answer (confidence is then capped at the
league-only tier). `club_standing_support` counts pool comps whose destination club stood
within ±0.15 of the chosen club's within-league standing — **`0` means the club term
extrapolated** (no precedent at this standing), **`null` means no club (or no percentile)
was in play**.

### Example: league-level happy path

`{"player_id": 294057, "destination": {"league_id": "IT1"}}` — James Maddison (€20M) to
Serie A. Comps trimmed to 2 of 41:

```json
{
  "player": { "player_id": 294057, "name": "James Maddison", "position_group": "MID", "sub_position": "Attacking Midfield", "age": 29, "market_value_eur": 20000000, "market_value_asof": "2026-06-03" },
  "destination": { "league_id": "IT1", "league_name": "Serie A", "country": "Italy", "tier": 1, "club_id": null, "club_name": null, "club_tercile": null },
  "prediction": {
    "low_eur": 11632147, "mid_eur": 16000000, "high_eur": 19069675,
    "low_multiplier": 0.5816073300675034, "mid_multiplier": 0.8, "high_multiplier": 0.9534837688240517,
    "horizon_months": 12
  },
  "direction": "decline",
  "confidence": "medium",
  "insufficient_precedent": false,
  "comps": [
    {
      "player_id": 348795, "player_name": "Giovani Lo Celso", "season": 2024, "transfer_date": "2024-08-30",
      "age_at_transfer": 28.391511917114258, "from_club": "Tottenham", "to_club": "Real Betis",
      "from_league": "GB1", "to_league": "ES1", "v_before_eur": 16000000, "v_after_eur": 15000000,
      "multiplier": 0.9375, "delta_pct": -0.0625, "similarity": 0.9128760737287237,
      "tags": ["similar market value", "same age profile", "same sub-position (Attacking Midfield)", "similar playing time", "recent move"]
    },
    {
      "player_id": 293200, "player_name": "Nikola Vlašić", "season": 2023, "transfer_date": "2023-08-08",
      "age_at_transfer": 25.842573165893555, "from_club": "West Ham", "to_club": "Torino",
      "from_league": "GB1", "to_league": "IT1", "v_before_eur": 17000000, "v_after_eur": 10000000,
      "multiplier": 0.5882352941176471, "delta_pct": -0.4117647058823529, "similarity": 0.8273064225688833,
      "tags": ["similar market value", "same sub-position (Attacking Midfield)", "recent move"]
    }
  ],
  "shown_comps": 6,
  "pool_quality": {
    "pool_size": 41, "relaxation_level": 0, "relaxation_steps": [], "expanded_search": false,
    "club_selected": false, "elo_pool_coverage": 0.0, "dest_elo_available": false,
    "missing_age": false, "missing_minutes": false, "origin_tier_unknown": false,
    "club_indistinct": false, "club_standing_support": null
  },
  "narrative": "The precedent points down. Across 41 comparable moves, a player in James Maddison's situation moving to Serie A typically lands at -20% within 12 months, with the middle half of outcomes between -42% and -5% — a range of €11.6M to €19.1M (medium confidence). Closest precedents: Giovani Lo Celso (Tottenham → Real Betis, 2024, -6%); Nikola Vlašić (West Ham → Torino, 2023, -41%); Pierre-Emile Højbjerg (Tottenham → Marseille, 2025, -25%). 31 of the 41 comparable moves lost value."
}
```

Note the decliners: 31 of 41 comps lost value and they are all in the pool — selection is
by similarity only, never by outcome.

### Example: club-level honesty (standing support = 0)

`{"player_id": 418560, "destination": {"league_id": "ES1", "club_id": 3368}}` — a €200M
forward pointed at the league's smallest budget. Honesty-relevant subset of the response:

```json
{
  "prediction": {
    "low_eur": 154029205, "mid_eur": 200000000, "high_eur": 226967197,
    "low_multiplier": 0.7701460228059706, "mid_multiplier": 1.0, "high_multiplier": 1.1348359865288218,
    "horizon_months": 12
  },
  "confidence": "medium",
  "pool_quality": {
    "pool_size": 41, "relaxation_level": 2,
    "relaxation_steps": ["age band widened to +/-4.5 years", "value bracket widened to 0.2-5x"],
    "expanded_search": true, "club_selected": true,
    "elo_pool_coverage": 0.9512195121951219, "dest_elo_available": true,
    "missing_age": false, "missing_minutes": false, "origin_tier_unknown": false,
    "club_indistinct": true, "club_standing_support": 0
  },
  "narrative": "… No comparable move on record went to a club of Levante Unión Deportiva S.A.D.'s standing in its league, so this range reflects the league more than the club. (… trimmed)"
}
```

The same query pointed at Real Madrid (club 418) returns `club_standing_support: 29` with
`club_indistinct: true` — plenty of precedent at that standing, but the club choice barely
moves the league-level answer, and the response says so.

### Example: refusal

`{"player_id": 27992, "destination": {"league_id": "AUS1"}}` — a 40-year-old €3.5M
midfielder to the A-League: zero comparable moves on record, even fully widened. No range
is invented:

```json
{
  "player": { "player_id": 27992, "name": "Luka Modrić", "position_group": "MID", "sub_position": "Central Midfield", "age": 40, "market_value_eur": 3500000, "market_value_asof": "2026-05-29" },
  "destination": { "league_id": "AUS1", "league_name": "A League Men", "country": "Australia", "tier": 4, "club_id": null, "club_name": null, "club_tercile": null },
  "prediction": null,
  "direction": null,
  "confidence": "insufficient",
  "insufficient_precedent": true,
  "comps": [],
  "shown_comps": 6,
  "pool_quality": {
    "pool_size": 0, "relaxation_level": 5,
    "relaxation_steps": [
      "age band widened to +/-4.5 years",
      "value bracket widened to 0.2-5x",
      "origin league tier widened to +/-2",
      "destination league band widened to +/-0.9 (~2.5x squad value)",
      "destination league band widened to +/-1 (~2.7x squad value); origin league filter dropped; club-level terms ignored"
    ],
    "expanded_search": true, "club_selected": false, "elo_pool_coverage": 0.0,
    "dest_elo_available": false, "missing_age": false, "missing_minutes": false,
    "origin_tier_unknown": false, "club_indistinct": false, "club_standing_support": null
  },
  "narrative": "Insufficient precedent: no comparable moves to A League Men on record even after widening the search, so no responsible value range can be given. To find this precedent the search was expanded (destination league band widened to +/-1 (~2.7x squad value); origin league filter dropped; club-level terms ignored)."
}
```

## Errors

One envelope for every failure: `{"error": {"code", "message", "detail"}}`. All captured:

**404 `player_not_found`** — `GET /api/players/999999999`:

```json
{"error": {"code": "player_not_found", "message": "No player with id 999999999", "detail": null}}
```

**404 `destination_not_found`** — unknown league (or club) in a simulation request:

```json
{"error": {"code": "destination_not_found", "message": "No destination league 'XX9'", "detail": null}}
```

**409 `player_without_value`** — simulating a player with no market valuation on record;
there is no baseline to anchor a range, so this is a domain conflict, not a missing page:

```json
{"error": {"code": "player_without_value", "message": "Jamie Young has no market valuation on record - a simulation needs a current value to anchor the predicted range", "detail": null}}
```

**422 `validation_error`** — malformed body; `detail` carries the validator output:

```json
{"error": {"code": "validation_error", "message": "Request validation failed", "detail": [{"type": "missing", "loc": ["body", "destination"], "msg": "Field required", "input": {"player_id": 294057}}]}}
```

**500 `internal_error`** — anything unexpected; the message stays a generic
`"Internal server error"` on purpose (shape from `app/core/errors.py`, not captured).
`http_error` covers non-domain HTTP failures (e.g. unknown paths) in the same envelope.
