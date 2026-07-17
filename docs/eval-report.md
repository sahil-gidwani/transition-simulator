# Precedent - temporal backtest report

Every number below is produced by `uv run python -m pipeline.eval` (offline, never in the serving path) against the committed processed dataset (revision `7dbc5b38ba6efdc439933b00c2f4b4a7405dd681`, valuations through 2026-06-12). The engine under test is the exact serving code: `find_comps` + `summarize_pool`.

## Protocol

- **Rolling origin, date-exact.** Every held-out transition is simulated at its own transfer date t; a comp is usable only if its v_after_date <= t (one shared, unit-tested rule). The query's own row can never inform itself: its outcome lands >= 180 days after t.
- **Splits.** Validation = seasons (2020, 2021) (3,173 queries) for tuning, confidence thresholds and the calibration decision; test = seasons (2022, 2023, 2024) (8,299 queries), scored exactly once after the freeze. Season 2025 is excluded (right-censored: only transfers whose 12-month valuation happened to arrive early are observable).
- **Historical context.** Queries are rebuilt as-of t: value = v_before, age at transfer, origin/destination league and club context from that season's tables, recency measured from the query's own season. One documented deviation from live serving: the backtest reads destination strength as-of the query's season, where the live product uses the latest season (a faithful historical simulation keeps both sides of the comparison <= t).
- **Skips.** Test: 63 of 8,362 transitions unbuildable ({'null_to_league': 63}); validation: 22 ({'null_to_league': 22}). Refusals (insufficient precedent) are reported next to every metric, never dropped.
- **Metrics.** Pinball loss on the log multiplier (quantile-equivariant, so every method is scored on the same target), empirical coverage of the q25-q75 range vs its nominal 50%, interval width ln(q75/q25), MdAPE of the median.

## Headline: test seasons, pooled

| method | n scored | refusal rate | coverage (nominal 50%) | width (median, log) | pinball (log, mean) | pinball q50 | MdAPE |
|---|---|---|---|---|---|---|---|
| Precedent (tuned comps engine) | 8291 | 0.10% | 50.5% | 0.533 | 0.1619 | 0.1856 | 28.5% |
| B0 - value unchanged (x1.0) | 8299 | 0.00% | - | - | - | 0.2054 | 33.3% |
| B1 - global quantiles (availability-filtered) | 8299 | 0.00% | 48.4% | 0.652 | 0.1857 | 0.2070 | 33.3% |
| B2 - age x position quantiles | 8299 | 0.00% | 53.2% | 0.598 | 0.1658 | 0.1888 | 28.6% |
| Skyline - LightGBM quantile (never served) | 8299 | 0.00% | 43.0% | 0.456 | 0.1564 | 0.1787 | 27.4% |

Precedent's range is honest out-of-sample: **50.5% of actual 12-month outcomes land inside the served q25-q75 band** (nominal 50%). It beats every naive baseline on every metric while refusing only 0.1% of queries. The LightGBM skyline - same features, same availability discipline, no traceability - is ~3.4% better on pinball but materially *miscalibrated* (43% coverage): the traceability tax on sharpness is small, and the comp-pool quantiles buy back honest uncertainty.

## Test seasons, by season

| season | n scored | refusal rate | coverage (nominal 50%) | width (median, log) | pinball (log, mean) | pinball q50 | MdAPE |
|---|---|---|---|---|---|---|---|
| 2022 | 2466 | 0.04% | 49.2% | 0.538 | 0.1649 | 0.1890 | 28.9% |
| 2023 | 2737 | 0.22% | 49.4% | 0.531 | 0.1671 | 0.1906 | 28.0% |
| 2024 | 3088 | 0.03% | 52.4% | 0.533 | 0.1549 | 0.1786 | 27.8% |

## Segments (test, cells under 100 transitions suppressed)

### age_band

| age_band | n scored | refusal rate | coverage (nominal 50%) | width (median, log) | pinball (log, mean) | pinball q50 | MdAPE |
|---|---|---|---|---|---|---|---|
| 22-25 | 3004 | 0.13% | 49.9% | 0.588 | 0.1703 | 0.1956 | 30.2% |
| 26-29 | 2400 | 0.04% | 51.0% | 0.482 | 0.1380 | 0.1564 | 25.0% |
| 30+ | 1565 | 0.13% | 51.8% | 0.443 | 0.1277 | 0.1458 | 23.1% |
| <22 | 1322 | 0.08% | 49.1% | 0.784 | 0.2269 | 0.2634 | 39.6% |

### position_group

| position_group | n scored | refusal rate | coverage (nominal 50%) | width (median, log) | pinball (log, mean) | pinball q50 | MdAPE |
|---|---|---|---|---|---|---|---|
| DEF | 2697 | 0.00% | 50.9% | 0.522 | 0.1562 | 0.1791 | 26.4% |
| ATT | 2521 | 0.04% | 50.9% | 0.571 | 0.1684 | 0.1925 | 29.7% |
| MID | 2343 | 0.09% | 50.3% | 0.511 | 0.1545 | 0.1776 | 27.8% |
| GK | 730 | 0.68% | 47.5% | 0.557 | 0.1847 | 0.2119 | 33.3% |

### tier_jump

| tier_jump | n scored | refusal rate | coverage (nominal 50%) | width (median, log) | pinball (log, mean) | pinball q50 | MdAPE |
|---|---|---|---|---|---|---|---|
| same | 5439 | 0.13% | 50.5% | 0.524 | 0.1592 | 0.1824 | 27.9% |
| down | 1454 | 0.00% | 49.3% | 0.517 | 0.1582 | 0.1817 | 28.4% |
| up | 1397 | 0.07% | 51.3% | 0.602 | 0.1759 | 0.2021 | 31.2% |

Suppressed (<100 transitions): unknown - 1 transitions in total.

### value_bracket

| value_bracket | n scored | refusal rate | coverage (nominal 50%) | width (median, log) | pinball (log, mean) | pinball q50 | MdAPE |
|---|---|---|---|---|---|---|---|
| <1M | 3681 | 0.19% | 51.0% | 0.533 | 0.1713 | 0.1958 | 28.6% |
| 1-5M | 2980 | 0.00% | 50.0% | 0.557 | 0.1618 | 0.1865 | 29.7% |
| 5-15M | 1084 | 0.00% | 49.0% | 0.538 | 0.1545 | 0.1768 | 28.6% |
| >=15M | 546 | 0.18% | 51.8% | 0.432 | 0.1142 | 0.1299 | 21.9% |

### minutes_known

| minutes_known | n scored | refusal rate | coverage (nominal 50%) | width (median, log) | pinball (log, mean) | pinball q50 | MdAPE |
|---|---|---|---|---|---|---|---|
| True | 4314 | 0.07% | 49.2% | 0.518 | 0.1588 | 0.1821 | 28.3% |
| False | 3977 | 0.13% | 51.8% | 0.552 | 0.1653 | 0.1895 | 28.6% |

## Tuning (validation seasons only)

Random search: 300 sampled configs + the hand-set priors (trial 0), seed 20260718, scored on mean validation pinball with refusals imputed at the global-baseline pinball (so refusing cannot game the objective); constraints: refusal rate within 1pt of hand-set, coverage inside a loose 35-65% sanity band. The candidate scorer is a numpy twin of the serving engine; its parity with `find_comps` + `summarize_pool` is pinned by synthetic tests and a runtime gate on real queries (both passed).

| method | n scored | refusal rate | coverage (nominal 50%) | width (median, log) | pinball (log, mean) | pinball q50 | MdAPE |
|---|---|---|---|---|---|---|---|
| Hand-set priors | 3163 | 0.32% | 51.4% | 0.564 | 0.1700 | 0.1924 | 28.2% |
| Tuned (winner ff9f546e0b3c) | 3168 | 0.16% | 53.2% | 0.562 | 0.1676 | 0.1904 | 28.0% |
| Tuned, league-only ablation (club withheld) | 3168 | 0.16% | 52.7% | 0.564 | 0.1684 | 0.1911 | 28.3% |
| Skyline reference | 3173 | 0.00% | 41.0% | 0.455 | 0.1684 | 0.1934 | 29.3% |

Winner: trial 300, config hash `ff9f546e0b3c` (imputed score 0.16763 vs hand-set 0.16997, ~1.4% better with half the refusals). The tuned weights moved the priors substantially: age similarity and destination-club tercile matter most; sub-position, minutes share and recency matter far less than assumed. Frozen into `app/services/constants.py` (provenance comment + hash) before any test query was scored.

Top 10 trials by validation score:

| trial | hash | score | refusal rate | coverage |
|---|---|---|---|---|
| #300 | ff9f546e0b3c | 0.16763 | 0.16% | 53.2% |
| #184 | e111a7a347ef | 0.16770 | 0.32% | 54.3% |
| #231 | c48c1314bd89 | 0.16770 | 0.22% | 53.0% |
| #258 | da3a682863f6 | 0.16785 | 0.09% | 52.2% |
| #223 | ab434006f9be | 0.16795 | 0.09% | 53.2% |
| #177 | dcc66b186002 | 0.16799 | 0.09% | 53.0% |
| #187 | f7bb00674dfa | 0.16799 | 0.19% | 53.5% |
| #109 | 188ac4862e56 | 0.16800 | 0.28% | 52.4% |
| #119 | 3e04e6626a50 | 0.16802 | 0.28% | 52.7% |
| #91 | 3e48fa10ffee | 0.16804 | 0.16% | 52.7% |

## Confidence tiers

Tiers partition rather than rank, so they were searched on a small honesty grid (324 settings): a tier is honest when its validation coverage brackets the nominal 50% and higher confidence means narrower ranges. **No setting was honest (0/324)**: under every candidate, the high tier under-covers (33.8% at the hand-set thresholds, n=151) - tight, unrelaxed pools are systematically overconfident. The hand-set thresholds were therefore kept, and this is an open finding, not a hidden one: treat the *high* label as "strong precedent agreement", not "50% band guaranteed".

How the served tiers actually performed on test:

| confidence | n scored | refusal rate | coverage (nominal 50%) | width (median, log) | pinball (log, mean) | pinball q50 | MdAPE |
|---|---|---|---|---|---|---|---|
| medium | 4784 | 0.00% | 48.7% | 0.474 | 0.1424 | 0.1625 | 25.0% |
| low | 3024 | 0.00% | 54.6% | 0.728 | 0.2003 | 0.2310 | 35.4% |
| high | 483 | 0.00% | 42.2% | 0.314 | 0.1151 | 0.1306 | 22.2% |
| insufficient | 0 | 100.00% | - | - | - | - | - |

## Calibration decision

Pooled validation coverage was 53.2% - inside the 45-55% trigger band - so **no calibration was applied**: all `CAL_SHIFT_*` stay 0.0 and the served endpoints remain the nominal weighted q25/q75 of the pool. (The machinery exists and is tested: shifts would move endpoints to quantile levels (0.25-d, 0.75+d) of the same pool, keeping them order statistics of the shown comps. Re-deciding it per-tier after seeing the tier table above would be post-hoc fitting, so it is left as the documented next step for the high tier.) Test coverage came in at 50.5% pooled - the uncalibrated intervals are honest.

## Skyline cross-check: importances vs tuned weights

Gain importances of the quantile GBM (mean across folds and quantile levels) next to the frozen distance weights:

| GBM feature | gain |
|---|---|
| age_at_transfer | 3021 |
| to_elo_pct | 2141 |
| ln_v_before | 2013 |
| from_elo_pct | 1820 |
| to_strength | 1699 |
| minutes_share_pre | 1667 |
| from_strength | 1456 |
| sub_position_code | 1173 |
| season | 900 |
| to_tercile | 257 |
| from_tercile | 182 |
| tier_diff | 169 |
| from_tier | 92 |
| to_tier | 70 |
| position_code | 40 |

| distance weight | tuned value |
|---|---|
| W_LOG_VALUE | 0.962 |
| W_AGE | 1.727 |
| W_DEST_STRENGTH | 0.387 |
| W_ORIGIN_STRENGTH | 0.101 |
| W_ELO | 0.106 |
| W_DEST_TERCILE | 1.479 |
| W_ORIGIN_TERCILE | 0.470 |
| W_MINUTES | 0.149 |
| W_SUB_POSITION | 0.070 |
| W_RECENCY | 0.117 |

Agreements: age dominates both; value and destination strength matter in both. Divergences worth knowing: the GBM leans on Elo percentiles (raw features, 31% missing) where retrieval tuning kept W_ELO low, and the GBM finds minutes_share_pre informative while the tuned W_MINUTES is small - candidates for a future search round with wider ranges.

## Horizon and right-censoring

"Value after" is the valuation nearest 12 months post-transfer within a 6-18 month window; because Transfermarkt revaluations land roughly twice a season, the realized horizon centers near 10 months for every season. The valuation history ends 2026-06-12 (censor horizon 2025-12-14), which truncates the window for late-2024-season transfers - the observed distribution below shows the effect stayed mild, but 2024's outcomes are the least settled of the test seasons:

| season | transitions | median days to v_after | p10 days to v_after |
|---|---|---|---|
| 2020 | 1341 | 266 | 191 |
| 2021 | 1854 | 284 | 187 |
| 2022 | 2483 | 309 | 218 |
| 2023 | 2755 | 304 | 214 |
| 2024 | 3124 | 311 | 227 |
| 2025 | 2127 | 292 | 214 |

## Known biases (also stated in the README)

- Transfermarkt values are validated but systematically underestimate fees, with bias varying by tier and value decile - and Precedent both predicts and conditions on them (circularity).
- Injuries and contract situations are not controlled; playing time only partially (minutes_share_pre, non-null for 53% of eval-season queries).
- Comps availability shrinks as the query moves back in time, so backtest pools are thinner than serving pools for the same player today; reported refusal rates are upper bounds for serving.

## Reproducibility

```
uv run python -m pipeline.eval backtest --phase validation --tag handset
uv run python -m pipeline.eval tune                    # parity gate + search
# freeze the printed constants block (reviewed commit), then:
uv run python -m pipeline.eval backtest --phase validation --tag tuned
uv run python -m pipeline.eval thresholds --tag tuned  # CONF_*/CAL_* decision
uv run python -m pipeline.eval backtest --phase test --tag tuned   # once
uv run python -m pipeline.eval skyline
uv run python -m pipeline.eval report
```

Seeds: search 20260718, skyline 20260718. Winning config hash `ff9f546e0b3c`. All stages are deterministic; raw records live in `server/data/eval/` (gitignored, reproducible).
