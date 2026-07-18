# Precedent

Transfer valuations, backed by named precedent. Precedent answers the question a club owner
actually asks — "if we sign this player, what happens to their value?" — with evidence: real,
named players who made comparable moves, and what happened to their market value in the
12 months after.

## Documentation

The full docs map (with reading paths) lives at [docs/README.md](docs/README.md):
[architecture](docs/architecture.md) · [methodology](docs/methodology.md) ·
[API reference](docs/api.md) · [pipeline](docs/pipeline.md) ·
[frontend](docs/frontend.md) · [decision log](docs/decisions.md) ·
[future scope](docs/future-scope.md) · [data notes](docs/data-notes.md) ·
[eval report](docs/eval-report.md) · [pipeline report](docs/pipeline-report.md).

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

One command, zero configuration — the processed data ships in the repo, so nothing is
downloaded and no keys are needed:

```bash
docker compose up --build
```

Open http://localhost:8080. nginx serves the built client and proxies `/api` to the API
container, so the browser talks to a single origin. Set `PRECEDENT_APP_PORT` in `.env` to
publish a different port. If your network uses a TLS-inspecting proxy, see
[docker/certs/README.md](docker/certs/README.md).

## Data & pipeline

The server reads **only** the lean parquet artifacts committed in `server/data/processed/`
(about 6 MB), so cloning the repo is enough to run the app — no data download needed.
Rebuilding those artifacts from raw data is an offline concern (full stage walkthrough and
data dictionary: [docs/pipeline.md](docs/pipeline.md)):

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
`docs/data-notes.md` for the audit. Club and league strength are **derived from player
valuations** (squad value = sum of members' latest valuations at season start) rather than
read from the upstream clubs table, whose market-value field is unreliable, or from wage
bills and federation coefficients, which the dataset simply does not carry. That strength is
enriched with rating history from public [ClubElo](http://clubelo.com) mirrors (data:
clubelo.com) and the reep cross-provider ID register (CC0).

**Gates.** `pipeline.build` fails loudly — non-zero exit, nothing written — unless every
gate passes: the source pin matches, row-count floors hold, the measured valuation
freshness equals the pinned date (catching frozen-valuation vintages), and the transfer
funnel reproduces the audited counts **exactly** (175,043 raw → 19,706 non-loan
transitions across all seasons; the *shipped* comps universe is the 19,407 of those from
season 2012/13 on, inside a 37,602-row transitions table that keeps loans flagged — the
distinction, precisely: [docs/pipeline.md](docs/pipeline.md#the-funnel-precisely)).
The full gate table, funnel, coverage stats and caveats land in
[docs/pipeline-report.md](docs/pipeline-report.md) and `data/processed/meta.json`.

**Artifacts.**

| artifact | one row per | notes |
|---|---|---|
| `players.parquet` | in-scope player | current value carries its own as-of date |
| `player_values.parquet` | valuation event | full market-value history for profile pages |
| `club_seasons.parquet` | club-season | derived squad value, tercile, season-start Elo; league from games where played (snapshot only where no match data exists, else unassigned — flagged via `league_source`) |
| `league_seasons.parquet` | league-season | strength + display tier (fixed ln-strength thresholds with two-season hysteresis; null below an 8-club membership floor, flagged via `stats_valid`), display name + country |
| `transitions.parquet` | qualifying transfer | v_before/v_after, multiplier, transfer-date Elo, `suspected_loan` flag |
| `profile_stats.parquet` | player-season-league | per-90s, GK stats, peer percentiles (450-min floor) |
| `elo_mapping.parquet` | covered club | ClubElo name mapping (automatic stages run for UEFA leagues only — ClubElo rates Europe); unmapped/excluded clubs stay, flagged |

Key definitions (applied uniformly, everywhere): **v_before** = last valuation in the 180
days strictly before the transfer (transfer-day revaluations are excluded — they already
price the move); **v_after** = the first valuation from 6 months
post-transfer, accepted up to 18 months (the window is deliberate: Transfermarkt
revaluations land roughly twice a season, so a hard 12-month cut would drop comps whose
nearest honest valuation arrives a few months either side — the realized horizon centers
near 10 months, see `docs/eval-report.md`);
**suspected loan** = both legs of a zero-fee round-trip within 18 months (excluded
from the comps universe; loans converted to permanent moves are structurally invisible —
stated, not papered over). Playing-time features are nullable by design: appearance
coverage only exists for 14 legacy leagues from 2012 (all 31 from 2024) and never gates
comp eligibility. `server/data/manual/elo_manual_fixes.csv` (committed) carries the few
ClubElo name fixes automation cannot make; the build validates every row.

## Methodology

This section is the compressed version; the full detail — exact ladder labels, the ten
distance terms with tuned weights, the quantile math, the club-honesty decision flow and
the destination-sensitivity evidence — is in [docs/methodology.md](docs/methodology.md).

**What "comparable" means.** A comp is a historical transition (see the definitions above)
that passes every hard filter: same position group; age at transfer within ±4 years of the
player's age today; origin league tier within ±1 of the player's current league;
**destination league strength within ±0.5 of the target league's** (ln squad-value units,
so ±0.5 ≈ a 1.6× median-squad-value band — a continuous band, not a tier match, which is
what makes a Premier League query different from an MLS query); pre-move value within
0.5–3× of the player's current value; suspected loans excluded; seasons 2012/13 onward.
When fewer than 6 comps match, the search widens one step at a time — age ±4.5 years →
value bracket 0.2–5× → origin tier ±2 → destination band ±0.9 → destination band ±1.0 +
origin-league filter dropped (club-level terms ignored) — and every widening is labelled in
the response (`pool_quality.relaxation_steps`), never silent. Two asymmetries are
deliberate: the destination is the question the user asked, so its band widens last and is
never dropped (a comp with no honest destination strength is never eligible), while the
origin is a control, so a coarse tier band plus a continuous origin-strength ranking term
is enough.

**Ranking.** Matched comps are ordered by a weighted distance over: log-value gap, age gap,
origin and destination league strength gaps (log median derived squad value, baked into the
artifact as-of the comp's own season; Elo percentile added when both sides have one),
destination/origin **club value percentile** gaps (the club's squad-value percentile within
its league-season, 1.0 = richest — the continuous signal that separates a Real Madrid from
a relegation budget; used only when a target club is chosen), sub-position mismatch,
pre-move playing-time gap, and recency. A missing feature drops its term for that comp with
weight renormalization — nulls never gate eligibility and never penalize. The weights and
band widths are tuned by the temporal backtest (random search on validation seasons 2020–21
under a date-exact availability rule) and frozen with a provenance comment and config hash
(`7309dc25f471`) in `server/app/services/constants.py`. Club-level honesty is judged on the
pair of searches: when the chosen club's midpoint sits within 2% of the league-only answer,
the response says so (`pool_quality.club_indistinct`) and the stated confidence is capped at
the league-only tier — reweighting the same evidence must never *raise* confidence. The
response also counts how many pool comps went to a club of comparable within-league standing
(`pool_quality.club_standing_support`); zero support means the club term extrapolated (no
precedent at that standing exists — true for every €60M+ move to a bottom-third budget), and
the scout's read states that cause explicitly instead of dressing reweighted noise up as
club-level insight.

**League tiers** (display and origin-filter semantics only — the engine's destination side
is continuous): fixed ln-strength thresholds pinned in `pipeline/config.py` (anchored in
the observed natural gaps, ≈ €98M/€24M/€12M median squad value), with two-season
hysteresis so a knife-edge league doesn't flap tiers year to year. Thresholds are nominal
EUR by design — "no covered league had an Elite-sized median in 2012" is the honest
statement, and the origin filter's ±1 band absorbs that drift.

**The range.** The prediction is the similarity-weighted 25th/50th/75th percentile of the
comp pool's 12-month value multipliers, applied to the player's current value — a weighted-
neighbour quantile, not a model output, so every number traces back to the named comps in
the response (the API returns the full quantile pool; the UI shows the closest six by
default). **The horizon rule** is identical for every comp everywhere: "value after" is
the first valuation from 6 months post-transfer, accepted up to 18 (a nominal 12-month
horizon whose realized median lands near 10 months).

**Confidence and refusal.** High/Medium/Low is driven by pool size, dispersion (IQR of log
multipliers) and how far the search had to widen (thresholds documented in
`server/app/services/constants.py`). Fewer than 2 usable comps means **no range at all** —
the API says "insufficient precedent" and shows the closest evidence it has instead.

**No survivorship bias.** Outcomes never enter the similarity distance: a decliner ranks
exactly as its similarity earns, and declines are shown, not filtered.

**Validation.** A temporal backtest replays 7,376 held-out transfers from test seasons
2022–24 through the exact serving code, each simulated at its own transfer date with a
date-exact availability rule (a comp is usable only once its 12-month outcome was
observable at that date). The served q25–q75 range covered **50.7% of actual outcomes
against a nominal 50%**, with a median width of ×1.7 and a 28.6% median absolute error on
the midpoint — beating or matching the value-unchanged, global-quantile and
age×position-quantile baselines on every metric while refusing only 0.01% of queries. A
LightGBM quantile regressor on the same features (built offline as a reference, never
served) is ~4% sharper on pinball loss but materially miscalibrated (43.5% coverage): the
price of full traceability is small, and the comp-pool quantiles keep the uncertainty
honest. Weights were tuned on validation seasons 2020–21, strictly before all test seasons,
and frozen before test was scored exactly once. One honest gap, reported rather than
hidden: the *high* confidence tier under-covers (45.5% on validation, 41.5% on test) — read
it as "strong precedent agreement", not a guaranteed 50% band. Full protocol, per-segment tables and
known biases: [docs/eval-report.md](docs/eval-report.md).

**Known biases** (also quantified in the eval report): Transfermarkt values are validated
but systematically underestimate realized fees, with bias varying by tier and value decile
— and Precedent both predicts and conditions on them (circularity, more below). Injuries
and contract situations are not controlled; playing time only partially
(`minutes_share_pre`). Comp availability shrinks as a backtest query moves back in time, so
backtest pools are thinner than serving pools for the same player today — reported refusal
rates are upper bounds for serving.

## Limitations — what would need to change to trust this with real money

Precedent is an evidence tool, not a valuation oracle. The gap between "useful in a
boardroom conversation" and "bankable" is exactly the list below, stated so nobody has to
discover it the hard way:

- **Matching is not causation.** Comps answer "what happened to similar players who made
  similar moves", not "what this move would cause". Players who moved to a given
  destination were selected by clubs (and agents) on information the dataset cannot see;
  no matching on observables removes that selection.
- **The confounders, named.** Age is controlled (hard filter + ranking term). Playing time
  is partially controlled: `minutes_share_pre` covers ~53% of the evaluated queries and is
  skipped (and flagged) where unknown. Injuries are NOT controlled — the
  dataset has no injury table, and a value collapse after a cruciate tear looks identical
  to a footballing decline. Contract length and agent dynamics are absent entirely, and
  both move real prices. Market-wide inflation: outcomes are 12-month *multipliers*, which
  is relative and therefore partially normalizes market drift, and the recency term
  down-weights old comps — but nothing in the engine models inflation explicitly; that is
  the exact extent of the control, no more. (Roadmap: injury data and era-normalized
  strength, [docs/future-scope.md](docs/future-scope.md).)
- **Valuation-source circularity.** Transfermarkt values partly reflect crowd
  expectations, and Precedent both predicts them and conditions on them. If the crowd is
  systematically wrong about a class of player, this product will be confidently wrong
  alongside it — market value is also not the same thing as a transfer fee, which embeds
  contract leverage, fees structure and negotiation. (Roadmap: fee-vs-value modeling,
  [docs/future-scope.md](docs/future-scope.md).)
- **Per-tier calibration gaps.** The pooled interval is honest (~50% coverage), but the
  *high*-confidence tier under-covers (~42–45%) — tight, unrelaxed pools are systematically
  overconfident. Until a per-tier calibration lands, read confidence tiers as evidence
  agreement, not probability guarantees. (Roadmap: the calibration machinery already
  exists, switched off by evidence — [docs/future-scope.md](docs/future-scope.md).)
- **A real deployment needs a live feed and monitoring.** The repo ships a pinned,
  audit-gated snapshot (values as of the date shown in the footer). Real money needs
  scheduled re-ingestion behind those same gates, drift monitors on coverage and interval
  width, and re-tuning on a cadence — none of which exists here by design.

How each of these would be addressed, with the evidence that motivates it:
[docs/future-scope.md](docs/future-scope.md).
