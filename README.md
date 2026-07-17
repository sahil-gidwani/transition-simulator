# Precedent

Transfer valuations, backed by named precedent. Precedent answers the question a club owner
actually asks — "if we sign this player, what happens to their value?" — with evidence: real,
named players who made comparable moves, and what happened to their market value in the
12 months after.

## Quickstart

### Dev

```bash
# Client tooling + git hooks (Node 22 is pinned via Volta)
npm install

# Server (fetches Python 3.12 automatically)
cd server && uv sync && cd ..

# Both dev servers in one command: client on :5173, API on :8000
npm run dev
```

Or run them separately: `npm run dev -w client` and `npm run dev:api`. Other root scripts:
`npm run test`, `npm run lint`, `npm run typecheck` — each covers client and server.

Open http://localhost:5173. Environment variables are documented in `.env.example`;
everything defaults sanely with no `.env` present.

### Docker

Coming soon — `docker compose up` will bring up the full app with zero manual steps.

## Data & pipeline

The server reads **only** the lean parquet artifacts committed in `server/data/processed/`
(under 5 MB), so cloning the repo is enough to run the app — no data download needed.
Rebuilding those artifacts from raw data is an offline concern:

```bash
cd server
uv sync --group data                                  # adds polars to the env
uv run --group data python scripts/download_data.py  # raw tables -> data/raw/ (gitignored)
uv run --group data python scripts/explore.py        # audit gates; non-zero exit on failure
uv run python -m pipeline.build                      # data/raw/ -> data/processed/ + report
```

**Source.** The primary tables are a
[transfermarkt-datasets](https://github.com/dcaribou/transfermarkt-datasets) build (CC0),
downloaded from a Hugging Face mirror **pinned to an immutable revision** (the exact SHA
lives in `pipeline/config.py` and is recorded in `data/raw/MANIFEST.json`). Kaggle builds of
the same dataset have shipped regressions (a collapsed transfers table; frozen valuations),
so the pipeline refuses to run against anything but the pinned, audit-gated revision — see
`docs/data-notes.md` for the audit. Club strength is enriched with rating history from
public [ClubElo](http://clubelo.com) mirrors (data: clubelo.com) and the reep cross-provider
ID register (CC0).

**Gates.** `pipeline.build` fails loudly — non-zero exit, nothing written — unless every
gate passes: the source pin matches, row-count floors hold, the measured valuation
freshness equals the pinned date (catching frozen-valuation vintages), and the transfer
funnel reproduces the audited counts **exactly** (175,043 raw → 19,706 comps universe).
The full gate table, funnel, coverage stats and caveats land in
[docs/pipeline-report.md](docs/pipeline-report.md) and `data/processed/meta.json`.

**Artifacts.**

| artifact | one row per | notes |
|---|---|---|
| `players.parquet` | in-scope player | current value carries its own as-of date |
| `player_values.parquet` | valuation event | full market-value history for profile pages |
| `club_seasons.parquet` | club-season | derived squad value, tercile, season-start Elo |
| `league_seasons.parquet` | league-season | strength + tier (per-season rank quartiles), display name + country |
| `transitions.parquet` | qualifying transfer | v_before/v_after, multiplier, transfer-date Elo, `suspected_loan` flag |
| `profile_stats.parquet` | player-season-league | per-90s, GK stats, peer percentiles (450-min floor) |
| `elo_mapping.parquet` | covered club | ClubElo name mapping; unmapped clubs stay, flagged |

Key definitions (applied uniformly, everywhere): **v_before** = last valuation in the 180
days strictly before the transfer (transfer-day revaluations are excluded — they already
price the move); **v_after** = valuation nearest 12 months after, within a 6–18 month
window; **suspected loan** = both legs of a zero-fee round-trip within 18 months (excluded
from the comps universe; loans converted to permanent moves are structurally invisible —
stated, not papered over). Playing-time features are nullable by design: appearance
coverage only exists for 14 legacy leagues from 2012 (all 31 from 2024) and never gates
comp eligibility. `server/data/manual/elo_manual_fixes.csv` (committed) carries the few
ClubElo name fixes automation cannot make; the build validates every row.

## Methodology

**What "comparable" means.** A comp is a historical transition (see the definitions above)
that passes every hard filter: same position group; age at transfer within ±3 years of the
player's age today; origin league tier within ±1 of the player's current league; destination
league tier equal to the target league's; pre-move value within 0.4–2.5× of the player's
current value; suspected loans excluded; seasons 2012/13 onward. When fewer than 3 comps
match, the search widens one step at a time — age ±5 years → value bracket 0.25–4× →
origin tier ±2 → origin-league filter dropped (club-level terms ignored) — and every
widening is labelled in the response (`pool_quality.relaxation_steps`), never silent.

**Ranking.** Matched comps are ordered by a weighted distance over: log-value gap, age gap,
origin and destination league strength gaps (log median derived squad value, read at the
comp's own season; Elo percentile added when both sides have one), destination/origin club
tercile gaps (only when a target club is chosen), sub-position mismatch, pre-move
playing-time gap, and recency. A missing feature drops its term for that comp with weight
renormalization — nulls never gate eligibility and never penalize. The weights are hand-set
priors recorded with a provenance comment in `server/app/services/constants.py`; the
temporal backtest (next milestone) tunes and overwrites them.

**The range.** The prediction is the similarity-weighted 25th/50th/75th percentile of the
comp pool's 12-month value multipliers, applied to the player's current value — a weighted-
neighbour quantile, not a model output, so every number traces back to the named comps in
the response (the API returns the full quantile pool; the UI shows the closest six by
default). **The 12-month horizon** is identical for every comp everywhere: "value after" is
the valuation nearest 12 months post-transfer within a 6–18-month window.

**Confidence and refusal.** High/Medium/Low is driven by pool size, dispersion (IQR of log
multipliers) and how far the search had to widen (thresholds documented in
`server/app/services/constants.py`). Fewer than 2 usable comps means **no range at all** —
the API says "insufficient precedent" and shows the closest evidence it has instead.

**No survivorship bias.** Outcomes never enter the similarity distance: a decliner ranks
exactly as its similarity earns, and declines are shown, not filtered.
