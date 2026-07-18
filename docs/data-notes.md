# Data notes — acquisition audit (2026-07-17, hardened 2026-07-18)

Every number below is computed by [`server/scripts/explore.py`](../server/scripts/explore.py)
against the pinned raw build and written to `server/data/raw/audit/audit_report.{md,json}`
(gitignored, reproducible: re-runs are byte-identical). This document is the curated read of
that report and feeds the README methodology.

## Source & version pin

**Primary tables:** the [transfermarkt-datasets](https://github.com/dcaribou/transfermarkt-datasets)
build (12 CSV tables, CC0), acquired from the HuggingFace mirror
[`ngeorgea/transfermarkt-player-scores`](https://huggingface.co/datasets/ngeorgea/transfermarkt-player-scores)
**pinned to revision `7dbc5b38ba6efdc439933b00c2f4b4a7405dd681`** (upstream sync of 2026-06-29).

Why a pinned mirror revision instead of Kaggle's `davidcariboo/player-scores`:

1. **Kaggle builds published after 2026-05-12 are defective** — transfers.csv collapsed from
   157,186 rows (2026-04-30 build) to ~40,674 (upstream discussion #374, unfixed as of
   2026-07-17). The Kaggle distribution was also reporting valuations frozen at 2026-02-27
   (issue #377). The mirror build has neither defect: 175,043 transfers and valuations
   through 2026-06-12.
2. **Immutability.** An HF revision SHA is a content-addressed pin; Kaggle dataset versions
   have no stable offline identifier. `scripts/download_data.py` holds the pin and a Kaggle
   fallback path (`--source kaggle --kaggle-version N`); any newly downloaded vintage must
   re-pass the audit gates below before being trusted.

## Audit gates (all PASS on the pinned build)

| Gate | Threshold | Actual |
|---|---|---|
| transfers rows | ≥ 150,000 | **175,043** |
| player_valuations rows | ≥ 500,000 | **656,301** |
| players rows | ≥ 30,000 | **48,380** |
| players schema | 26 cols incl. `international_caps` | **26 cols, present** |

**Value freshness cut-off: `max(player_valuations.date) = 2026-06-12`.** Every "current
value" the product shows carries this as-of date (upstream valuations are event-based;
~stale players keep older dates). The UI must surface it.

## Coverage shape (matters for features, not for the transition universe)

Transfers (1993→) and valuations (2000-01-20→) are complete for all covered leagues.
**Match data (games/appearances) is not:**

- 14 "legacy" leagues have games/appearances from **2012**: GB1, ES1, IT1, L1, FR1, NL1,
  PO1, BE1, TR1, GR1, SC1, DK1, RU1, UKR1 (~5,500–6,000 games/season, 22–26 appearance
  rows per game, ≤11% games without appearance rows — the 2024/25 gap bug (#349) is fixed:
  2024 legacy density is the best in the series at 26.5 apps/game, 7% zero-rows).
- 9 further European leagues only get match data from **2024**: A1, C1, KR1, NO1, PL1,
  RO1, SE1, SER1, TS1.
- The 8 newly added non-European leagues (MLS1, BRA1, ARG1, JAP1, RSK1, MEX1, AUS1, SA1)
  are **recent-only, no backfill**: games 2024–2025 only, and their appearance rows are
  still sparse (89–96% of their 2024/25 games have zero appearance rows).

Consequence: minutes-based features (`minutes_share_pre`) and performance percentiles are
computable only where appearances exist; they stay nullable and never gate comp
eligibility (per CLAUDE.md). Transitions from all 31 leagues remain usable.

## The feasibility funnel (the product's universe)

```
raw transfer rows                   175,043
cleaned (dated, deduped, no self)   174,917   [-118 duplicate (player,date), -8 self-moves]
in scope (both clubs covered)        46,601   (26.6%)
  out of scope                      128,316   [from-side only in scope: 17,246;
                                               to-side only: 33,708; neither: 77,362;
                                               pseudo-club moves (retired/unknown/ban): 8,588]
with v_before (≤180d, strict)        42,817   (91.9% of in-scope)
observable for v_after               39,510   [transfer ≤ 2025-12-14; censored: 3,307]
with v_after in [180,540]d           38,284   (96.9% of observable)
minus suspected loans                19,706   ← THE COMPS UNIVERSE
```

- **Windows.** `v_before` = last valuation strictly before the transfer date within 180
  days (strict, because Transfermarkt often posts a transfer-day revaluation that already
  prices the move — allowing it would leak the outcome; the strictness costs only 767
  transfers). `v_after` = first valuation in [t+180d, t+540d] (existence-equivalent to
  "nearest to +12 months in the 6–18 month window" used product-wide).
- **Right-censoring.** Transfers after 2025-12-14 (`max_val_date − 180d`) cannot have a
  v_after yet; they are reported as censored (3,307), not as conversion failures.
- Out-of-scope is dominated by moves touching clubs outside the covered first-tier
  leagues (second tiers, youth/reserve sides, non-covered countries) — full career
  histories ship in transfers.csv. Youth/reserve squads are already excluded by the scope
  filter (0 youth-club rows in the final universe — verified).

Usable transitions per season: 195 (2012) → 962 (2017) → 1,854 (2021) → 3,124 (2024);
2025 partial at 2,127 (censoring).

## Loan exclusion rule (proposal)

Upstream has **no loan flag**; loans, end-of-loans and paid loans all parse to
`transfer_fee = 0` — identical to free transfers (fee coding in cleaned rows: zero 54.9%,
positive 10.0%, null/unknown 35.1%). Detection is structural:

- Round-trip pairing: A→B then B→A for the same player within 548 days (~18 months),
  greedy 1:1 by shortest gap. Found: **30,722 pairs with both fees 0** (suspected loans),
  2,815 with any fee > 0 (buy-backs — kept), 2,162 with unknown fees (kept, counted as
  ambiguous).
- **Rule: exclude both legs when both fees are exactly 0.** Flags 58,602 rows (33.5% of
  cleaned; 61.1% of all fee-zero rows). Return-gap quantiles p25/p50/p75 = 148/197/330
  days — consistent with half-season and full-season loans.
- Spot-verified: Conor Gallagher's Charlton/Swansea/Crystal Palace loan spells all flag;
  his permanent moves (incl. the Chelsea→Atlético decliner, ×0.8) don't.
- **Known residual:** loans converted to permanent transfers never round-trip and are
  structurally invisible; stated in the README rather than papered over.

## Valuation cadence & season cut-off recommendation

Updates per player-year (p50; share of player-years with ≥2 updates): 2000–2011: 2 (53%),
2012–2019: 2 (68%), 2020+: 2 (76%). Value distribution across all rows: p50 €500k,
p75 €1.5M, p90 €5M, p99 €32M.

**Recommendation: transition universe starts at season 2012/13** (appearances begin 2012;
cadence materially better; pre-2012 usable counts are thin anyway). Retrieval should
weight recency so the 2021+ bulk dominates; the backtest (Prompt 5) validates on recent
seasons only.

## League scope proposal

Keep **all 31 covered first-tier leagues** in the transition universe — every league
clears ~200 usable transitions (top: IT1 1,679 in / GB1 1,574 / L1 1,245 / FR1 1,174 /
TR1 1,150; bottom: AUS1 209, RSK1 232). Non-European leagues carry two documented feature
gaps: no ClubElo (below) and no pre-2024 match data. Their club-strength signal comes
from derived squad values only, flagged in `pool_quality`.

## Comp-pool density preview (relaxation-ladder pressure)

Grid over position group (4) × age band (4) × v_before bracket (5) × origin tier ×
destination tier (per-season squad-value quartile tiers, preview-grade): 19,700 of 19,706
usable transitions graded; 769 non-empty cells; median cell 9, p90 65, max 335.
Transition-weighted: **97% land in cells with ≥5 comps, 82% ≥20, 64% ≥50** — the
relaxation ladder fires for the ~3% tail and for rare cross-tier jumps, exactly the cases
the UI labels "expanded search".

## Club strength: ClubElo mapping probe

Mirrors (attribution: [clubelo.com](http://clubelo.com)):
- A (`xgabora/Club-Football-Match-Data-2000-2025`): bi-monthly 2000-07-01 → 2025-06-01,
  895 clubs, 19 countries.
- B (`tonyelhabr/club-rankings` release asset): daily 2023-03-27 → 2026-01-14, 860 clubs,
  57 countries (all UEFA).

Mapping the 773 comps-universe clubs (39,412 transition touches) by a deterministic
ladder — reep id-bridge → exact normalized name → token subset → token prefix → acronym →
team-mapping.csv → difflib 0.85 (uniqueness required at every fuzzy stage; ambiguous
normalized Elo names excluded):

- **82.4% of transition touches mapped** (591/773 clubs) — *probe-grade, since revised
  down*: the probe's fuzzy stages produced false positives (River Plate → "Atlético",
  Inter Miami → Inter Milan, Columbus Crew → Crewe Alexandra…). The shipped pipeline now
  structurally excludes non-UEFA leagues from automatic mapping and refuses 1-token-vs-
  ≥3-token fuzzy matches; **honest touch coverage is 75.2%** (see "2026-07-18 hardening"
  below and `docs/pipeline-report.md`).
- The unmapped remainder is dominated by the structural gap: **ClubElo covers UEFA
  countries only** — SA1/RSK1 0%, JAP1 4%, MLS1 10%, BRA1 32%, MEX1 43% coverage in the
  probe, and 0% by construction in the shipped mapping.
  European leagues sit at 61–100% (worst: RO1 61%, UKR1 67%, RU1 75%).
- Remaining European misses are legal-name artifacts destined for the pipeline's manual
  fix CSV (top: Lille, RB Leipzig, Real Betis, CSKA Moskva, Krylya Sovetov, FCSB, Farul
  Constanța, Espanyol).
- `team-mapping.csv` maps Opta↔ClubElo names, not Transfermarkt — it contributed only
  1.8%; the name ladder plus the reep bridge carry the probe.

Pipeline decision (per CLAUDE.md): Elo is an **as-of-date enrichment with a flagged
fallback**, never an eligibility gate; unmapped clubs rely on squad-value terciles.

## reep register (CC0)

- 444,707 people; 207,872 with `key_transfermarkt` (15 duplicate TM ids — dedupe on join).
- **99.1%** of the 12,307 players in in-scope transfers match by TM id.
- Useful bridges (fill rate among matched): wikidata 98.6%, soccerway 94.5%, wyscout
  88.4%, sofascore 88.0%, opta 71.4%, **fbref 68.6%** (backs the FBref↔TM mapping),
  worldfootball 66.4%. `reep_teams.csv` additionally carries a small TM↔ClubElo id bridge
  (20 of our clubs) used as stage 0 above.
- ⚠️ `key_sofifa` is the legacy fifa.com archive ID (Wikidata P1469), **not** a SoFIFA
  site ID — never use it as the TM↔SoFIFA join. EA-attribute joins (stretch) go by
  normalized name + exact DOB instead.

## What we discard, and why

| Discarded | Count | Why |
|---|---|---|
| duplicate (player, date) rows | 118 | upstream PK violations |
| self-transfers (from == to) | 8 | re-registrations, no market move |
| out-of-scope transfers | 128,316 | one/both clubs outside covered first-tier leagues (incl. 8,588 pseudo-club rows: retired/without club/unknown/ban) |
| in-scope without v_before | 3,784 | no valuation within 180d pre-transfer (mostly early-era or fringe players) |
| censored for v_after | 3,307 | transfer too recent for the 6–18-month horizon — returns to the pool as valuations accrue |
| observable without v_after | 1,226 | player dropped out of valuation coverage |
| suspected loans | 18,578 | structural round-trip rule above |

## 2026-07-18 hardening: membership, Elo mapping, league-stat floor

Three correctness fixes to the "similar league / similar club" inputs, applied in the
pipeline and re-gated (`docs/pipeline-report.md` carries the regenerated gate table):

1. **Games-derived membership is authoritative.** club_seasons used to label every valued
   club with `coalesce(games league, current-day snapshot league)`; the snapshot padded
   historical league-seasons with phantom members. The latest GB1 season carried **37
   "members"** (20 real + 17 relegated/defunct, incl. Wigan/Reading/Huddersfield) and its
   shipped median squad value (€244M) was literally Southampton's. Now, where a (league,
   season) has games-derived membership at all, snapshot-only clubs are NOT members:
   their rows keep squad value/Elo with `league = null`, `league_source = "none"`. The
   snapshot fallback survives only for league-seasons with no match data (pre-2024
   non-legacy leagues). Measured after the fix: GB1 latest = **20 clubs, median €457.1M**;
   club-season rows split games 3,902 / snapshot 3,335 / none 2,746 (of 9,983).
   Transitions inherit the rule through their (club_id, season) join: **4,808 of 37,602**
   transitions (2,191 of the 19,407 comps universe) now carry a null `to_league` — these
   include verified wrong-division rows that previously shipped as tier-1 precedent
   (Coady→Leicester 2023, Winks→Leicester 2023, Harrison→Leeds 2024, Azaz→Southampton
   2025, Mikautadze→Metz 2024 — all second-division moves). A null destination is never
   eligible as a comp for a league-filtered query. `players.current_league` (a current-day
   fact about a current player) still comes from the snapshot deliberately.
2. **Elo mapping is Europe-only by construction.** ClubElo rates UEFA clubs; the automatic
   ladder previously ran for all 31 leagues and manufactured false positives (~20 Argentine
   and Brazilian clubs → "Atlético" = Atlético Madrid at elo_pct 0.98, Inter Miami → Inter
   Milan, Columbus Crew → Crewe Alexandra, Vissel Kobe → FC København, Sporting KC →
   Sporting CP, SC Internacional → Porto via its URL slug). Non-UEFA clubs (confederation
   ≠ "europa" in competitions.csv) now skip every automatic stage (flagged stage
   `excluded_non_uefa`); a 1-token ClubElo name may no longer fuzzy-match a ≥3-token TM
   name. **elo_touch_coverage fell from an inflated 0.8434 to an honest 0.7518**; the gate
   floor is re-pinned at 0.74. Future hardening if more coverage is needed: both mirrors
   carry an Elo-side country column (dropped at load today) that would support a
   country-consistency constraint for European fuzzy matches.
3. **League stats below an 8-club floor are null, flagged.** Pre-2024, snapshot-only
   history leaves stubs like RSK1 2013 with n_clubs = 1; a one-club "league median" is not
   a strength signal. league_seasons now carries `stats_valid`; below the floor, strength/
   tier and member terciles are null, and the stub does not consume a tier-quartile rank
   slot. 9 of 434 league-seasons are flagged. The engine refuses null-tier destinations
   (insufficient precedent); the backtest counts them as skipped
   (`dest_league_stats_invalid`).

Downstream consequence, measured on the latest season: MLS1 drops out of tier 1 and BE1
rises into it under the current rank-quartile tiers; the remaining quota artifacts of
rank-quartile bucketing (a 31-league season always splits 8/8/8/7, holding e.g. MEX1 at
€40M median inside tier 1 with GB1 at €457M) are addressed separately by the fixed
ln-strength display tiers.

## Reproducing

```bash
cd server
uv run --group data python scripts/download_data.py   # needs KAGGLE_* only for --source kaggle
uv run --group data python scripts/explore.py          # exits non-zero if any gate fails
```
