# Future scope

Deliberately deferred work, each item with the evidence that motivates it and how it would
land. Items marked **[retune-gated]** touch the engine's tuned constants, so they require
a full `pipeline.eval` retune — tune on validation, freeze by hand with updated
provenance, score test once — per the freeze workflow in
[pipeline.md](pipeline.md#the-eval-harness).

## Era-normalized league strength — [retune-gated]

**What.** League strength is absolute `ln(EUR median squad value)`, so market inflation
slowly lifts every league: a mid-strength league in 2025 sits where a top league sat a
decade ago, and the destination band admits cross-era comps that are league-tier
mismatches in spirit. Observed in practice: a Portuguese-league query surfacing 2013
Ligue 1 moves as precedent, and a thin pool producing a Portuguese-league midpoint *above*
the same player's Spanish-league midpoint (an n=6 pool inversion).

**How it lands.** Normalize strength within-era (e.g. season-relative percentile or
detrended ln value) or add an era term to the distance, then retune — the recency weight
currently shoulders this alone.

## A dominant-precedent-league caveat in pool_quality

**What.** At some strength bands, the available evidence is dominated by a single league —
most weak-league precedent for star players is recent moves to one destination market
(Saudi Pro League transfers of the Núñez / Durán / Diaby class). The range is honest, but
the reader should know the evidence is not diverse.

**How it lands.** Serve "evidence at this strength comes mostly from X" in `pool_quality`
(a per-league share of the pool), rendered as one more banner line. Additive and
presentation-only: no filter or weight changes, so no retune needed.

## Per-tier calibration for the high-confidence tier

**What.** The known open finding: the high tier under-covers its nominal band
([methodology.md](methodology.md#confidence-direction-refusal) has the numbers and the
0/324-at-freeze story). The calibration machinery — per-tier interval widening — already
exists in `valuation.py`, is unit-tested, and is switched off because pooled validation
coverage never triggered it.

**How it lands.** Once more validation data exists (another season or two of observable
outcomes), re-run the thresholds stage per-tier; if the high tier's under-coverage
persists, a small `CAL_SHIFT_HIGH` widening is the honest fix. Constants change ⇒ reviewed
freeze commit with updated provenance.

## Richer enrichment through the reep register — [retune-gated]

**What.** The cross-provider ID register (reep, CC0) already ships as the Elo-mapping ID
bridge and matches 99.1% of in-scope players by Transfermarkt id — the hard identity
problem is solved. Two enrichments were scoped in the original data research and
deliberately deferred: Understat xG (big-5 + Russian leagues, 2014+) and EA FC edition
attributes (FIFA 15–FC 24 archives, joined by normalized name + birth date). Today's
engine uses **no per-performance features in matching** — `minutes_share_pre` is a
playing-time control, not a form signal — so pre-transfer form is the largest unexploited
similarity dimension.

**How it lands.** As nullable profile facts first (zero engine risk), then as distance
terms under the existing null policy (nulls drop with weight renormalization — essential,
since xG is null outside the covered leagues). Any distance change is retune-gated.

## Injury data — the missing confounder

**What.** The dataset has no injury table, and the engine's known blind spot follows: a
value collapse after a cruciate tear is indistinguishable from footballing decline, both
as a comp outcome and as a query baseline. This is the top confounder named in the
README's limitations.

**How it lands.** An injury-history source joined by player id would serve first as a
profile fact and a comp annotation ("value fell during a 9-month layoff"), and eventually
as a filter or distance term [retune-gated]. Sourcing is the hard part — coverage and
licensing vary widely.

## The live deployment path

**What.** Everything here is a snapshot product by design: one pinned dataset revision,
gates sized to that audit, no runtime network. A production deployment needs the loop
closed.

**How it lands.** Scheduled re-ingestion behind the *same* gates (re-audit, re-pin,
rebuild — the pin makes updates deliberate), drift monitors on the two backtest headline
metrics (coverage and interval width) so engine decay is seen rather than suspected, and a
retune cadence with the freeze protocol unchanged. The pieces exist; the scheduler and the
monitoring surface do not.

## Smaller items with evidence behind them

- **Fee-vs-value modeling.** The product predicts market value; transfer *fees* are a
  related but distinct quantity (the circularity limitation in the README). The transitions
  artifact already carries `transfer_fee_eur` where known — a fee-vs-value view is mostly a
  presentation problem.
- **Boardroom memo export.** The simulation response is already a self-contained argument
  (range, named comps, caveats); rendering it as a one-page brief is UI work with no engine
  surface.
- **Wider tuning search where the skyline disagrees.** The LightGBM skyline's feature
  importances disagree with the tuned weights in places — a signal that the random search's
  ranges may be clipping useful regions. [retune-gated]
- **Compare beyond pairs.** The tray caps at two pins (a deliberate pairwise design,
  [frontend.md](frontend.md#compare-pins-and-the-tray)); a destination-shortlist matrix is
  the natural extension.

## Where the README's limitations point

| Limitation (README) | Addressed by |
|---|---|
| Matching is not causation | not fixable by features — stated honestly; injury data and form features (above) shrink the confounder set |
| The confounders, named (injuries, contracts) | [Injury data](#injury-data--the-missing-confounder), [reep enrichment](#richer-enrichment-through-the-reep-register--retune-gated) |
| Valuation-source circularity | [Fee-vs-value modeling](#smaller-items-with-evidence-behind-them) |
| Per-tier calibration gaps | [Per-tier calibration](#per-tier-calibration-for-the-high-confidence-tier) |
| Live feed and monitoring | [The live deployment path](#the-live-deployment-path) |
