# Decision log

The calls that shaped Precedent, in the order they were made, each with its commit. Dates
are commit dates; deep detail lives in the linked docs — an entry here records *why the
fork in the road went this way*.

## 2026-07-17 — Pin the dataset and gate the ingest (e0b47ab, 4f18232)

Upstream builds of the source dataset have shipped real regressions (a transfers table
that lost three quarters of its rows; valuations silently frozen months stale). Rather
than trusting "latest", acquisition pins an exact revision, and the build fails fast if
the raw snapshot doesn't match the pin or the audited row counts. Alternative — build
against latest and hope — was rejected after the audit found the regressions *before* any
engine code existed. Consequence: reproducibility for free, and a defined re-ingestion
procedure (re-audit, re-pin) instead of silent drift. Details: [data-notes.md](data-notes.md).

## 2026-07-17 — Structural loan detection and the 6–18-month outcome window (c52e77c)

The source has no loan flag — loans parse exactly like free transfers — so loans are
detected by shape (zero-fee round-trips within ~18 months) and excluded from the comps
universe; a loan's "outcome" measures the parent club's asset management, not a transfer.
The outcome itself is fixed to one horizon everywhere: value-after is the first valuation
from 6 months post-transfer, accepted up to 18 — wide enough to catch sparse valuation
schedules, narrow enough to stay "a year later". Consequence: every comp, chart and
backtest number shares one definition of "after". Details: [pipeline.md](pipeline.md).

## 2026-07-17 — Derive squad values; never trust the upstream club value (6c388aa)

The upstream clubs table's market-value field is unreliable, so club and league strength
are derived by aggregating player valuations (July 1 snapshot, staleness-capped). Every
strength, tier and percentile in the product traces back to player-level data the audit
already validated. Details: [pipeline.md](pipeline.md#stage-walkthrough).

## 2026-07-17 — An Elo name-matching ladder with a committed manual-fix file (134187f)

ClubElo has no shared id with the source data, so clubs match through ordered stages, most
trusted first, each automatic stage requiring a unique hit. The escape hatch is data, not
code: a reviewed CSV of manual fixes that the build validates (and warns about when a fix
becomes auto-findable). Consequence: mapping failures are visible, diffable and
individually reviewable. Details: [pipeline.md](pipeline.md#stage-walkthrough).

## 2026-07-17 — Hard gates and atomic promotion in the build (ea82c18)

Artifacts are written to a temp dir, gated (funnel counts by *exact equality*, freshness
by *exact date*), and only then promoted. A failing gate can't ship half a build, and a
passing build is a statement: "this equals what was audited." The exactness is the point —
a drifted count is a question to answer, not a tolerance to absorb.
Details: [pipeline.md](pipeline.md#write-to-temp-gate-promote).

## 2026-07-17 — One DataStore, an injectable Clock, one error envelope (4d40209)

All parquet access sits behind repositories loaded once at startup; time enters through a
`Clock` protocol that defaults to the real system date (staleness is surfaced with as-of
dates, never hidden by pinning "today" to the dataset); every failure shares one
`{"error": {code, message, detail}}` envelope. These three seams make the server testable
with synthetic stores and a fixed clock — and keep handlers thin.
Details: [architecture.md](architecture.md).

## 2026-07-17 — The prediction is a weighted quantile band, not a model (43d2927)

The range is literally the middle half of the named comps' outcomes, similarity-weighted.
A gradient-boosted model was later built as a skyline (eb55f09) and confirmed the trade:
~4% sharper on pinball loss but materially miscalibrated (43.5% coverage on a nominal
50%), and — decisively — unable to answer "*which* named players is this number made of?".
The traceability tax was paid knowingly. Details:
[methodology.md](methodology.md#the-range), [eval-report.md](eval-report.md).

## 2026-07-17 — Deterministic narrative, no LLM (4066929)

The scout's read is assembled from templates over the same fields the API serves.
Identical inputs give identical words; no hallucination surface, nothing to cache, and the
narrative can never claim what the data doesn't show. The cost — prose that is plainly
templated — is acceptable in a product whose selling point is traceability.
Details: [methodology.md](methodology.md#the-narrative).

## 2026-07-18 — A temporal backtest with a date-exact availability rule (81de8bc–2e73d05)

Before the engine's numbers were trusted, a backtest was built that replays held-out
transfers through the *exact serving code*, each at its own transfer date, where a comp is
usable only if its outcome valuation existed by then. Split-by-season alone would have
leaked: a 2021 comp whose after-valuation landed in 2022 must be invisible to a 2021
query. Details: [pipeline.md](pipeline.md#the-eval-harness).

## 2026-07-18 — Tuning that refusal can't game (cb893e3)

Retrieval weights come from a random search scored on validation pinball — with refused
queries *imputed at the naive baseline's loss*. Without imputation, the search would learn
to refuse hard queries and look brilliant on the rest. A numpy parity gate proves the fast
search scorer matches the real engine before any trial counts.
Details: [pipeline.md](pipeline.md#the-eval-harness).

## 2026-07-18 — Confidence thresholds kept hand-set; calibration off by evidence (9e4ce5d)

An honesty grid over 324 threshold settings found none whose "high" tier actually covered
its band at freeze time, so the hand-set thresholds stayed, and their known weakness
(high-tier under-coverage) is documented and worded into the product rather than tuned
away. Interval calibration exists in code but every shift is 0.0: pooled validation
coverage fell inside the trigger band, so no correction was earned.
Details: [methodology.md](methodology.md#confidence-direction-refusal).

## 2026-07-18 — Weights frozen by hand, with provenance (a8853ff, later e58389f)

The tuning winner is frozen into `constants.py` in a reviewed commit carrying method,
seed and config hash; pipeline code cannot write into `app/`. Test seasons are scored
exactly once, after the freeze. Any future retune must repeat the whole ritual — that is a
feature. Details: [methodology.md](methodology.md#ranking).

## 2026-07-18 — POST /simulations is a query, not a mutation (5a29a8d)

A simulation is a deterministic read of an immutable-per-build dataset, so the client
caches it like one: `staleTime: Infinity`, instant back-navigation, no 4xx retries.
Modeling it as a mutation would have thrown away caching for a request with no side
effects. Details: [frontend.md](frontend.md#server-state-post-as-query).

## 2026-07-18 — UEFA-only Elo with a short-vs-long guard (93a6225, eb42ce0)

An adversarial pass over the Elo mapping found false positives (Inter Miami → Inter Milan;
Columbus Crew → Crewe Alexandra): ClubElo only covers UEFA countries, so any non-UEFA
"match" is wrong by construction — non-UEFA clubs now skip automatic matching entirely,
and a guard blocks 1-token names from fuzzy-matching ≥3-token ones. The guard's
casualties (real UEFA clubs with compact names) were individually restored through the
manual CSV, and the coverage gate re-pinned above the honest level.
Details: [data-notes.md](data-notes.md).

## 2026-07-18 — Games-derived league membership becomes authoritative (b497470, e004d10)

The same audit found phantom league members: snapshot membership had 37 clubs in a
20-club league, and the shipped "Premier League median squad value" was literally
Southampton's. Membership is now derived from who actually played, with the snapshot
surviving only where no match data exists at all — plus an 8-club floor below which league
stats are null and flagged rather than fabricated. Consequence: several thousand
transitions lost a resolvable league and honestly fail destination filters now.
Details: [data-notes.md](data-notes.md), [pipeline.md](pipeline.md#stage-walkthrough).

## 2026-07-18 — Engine v2: a continuous destination strength band (ba7a38a)

Engine v1 filtered destinations by tier *equality*, which put the Premier League and MLS
in one bucket and gave the big five leagues a single shared candidate set — destination
choice barely moved the answer. The v2 hard filter is a band on continuous league
strength that widens on the ladder and is never dropped. League differentiation became
real and measurable (a €20M midfielder's Premier-League-vs-Serie-A midpoint spread went
from ~4% to ~12%, on genuinely different pools). Re-tuned and re-frozen (e58389f).
Details: [methodology.md](methodology.md#what-the-destination-actually-changes--evidence).

## 2026-07-18 — Clubs enter the distance as a continuous percentile (4b4e2e5)

Club terciles were constant across elite pools (every plausible destination for a star is
"top third"), so the tercile term cancelled out of the weighted quantiles entirely. The
engine now uses `club_value_pct` — the club's continuous within-league squad-value
percentile — baked into each transition as-of its own season; terciles survive only as
display copy. Details: [methodology.md](methodology.md#ranking).

## 2026-07-18 — The verdict direction is served (77deb32)

The client used to re-derive rise/decline from the multiplier with its own thresholds —
a silent-divergence bug waiting for the first retune. Now one server function feeds both
the narrative's wording and a served `direction` field the client renders as-is; the arrow
and the words cannot disagree. Details: [api.md](api.md#post-apisimulations).

## 2026-07-18 — Club-level honesty: drift-only indistinct, capped confidence (fcae8ca, 90927ec)

Choosing a club re-weights league evidence rather than conjuring club precedent, and the
product says so. The final design keys the "indistinct" flag on midpoint drift alone
(above the pool cap, club terms reshuffle *which* comps make the cut without moving the
answer — pool identity is noise), caps stated confidence at the league-only tier, and
words the caveat cause-first: "no precedent at this standing" (the club term extrapolated)
beats "the club barely moves the answer".
Details: [methodology.md](methodology.md#club-level-honesty).
