# Precedent - temporal backtest report

Every number below is produced by `uv run python -m pipeline.eval` (offline, never in the serving path) against the committed processed dataset (revision `7dbc5b38ba6efdc439933b00c2f4b4a7405dd681`, valuations through 2026-06-12). The engine under test is the exact serving code: `find_comps` + `summarize_pool`. Backtests are re-run with the frozen config whenever the processed artifacts are repaired (most recently: restoring Elo ratings for 27 compact-named UEFA clubs); the tuning search itself predates such repairs and is only repeated on a full retune.

## Protocol

- **Rolling origin, date-exact.** Every held-out transition is simulated at its own transfer date t; a comp is usable only if its v_after_date <= t (one shared, unit-tested rule). The query's own row can never inform itself: its outcome lands >= 180 days after t.
- **Splits.** Validation = seasons (2020, 2021) (2,791 queries) for tuning, confidence thresholds and the calibration decision; test = seasons (2022, 2023, 2024) (7,376 queries), scored exactly once after the freeze. Season 2025 is excluded (right-censored: only transfers whose 12-month valuation happened to arrive early are observable).
- **Historical context.** Queries are rebuilt as-of t: value = v_before, age at transfer, origin/destination league and club context from that season's tables, recency measured from the query's own season. One documented deviation from live serving: the backtest reads destination strength as-of the query's season, where the live product uses the latest season (a faithful historical simulation keeps both sides of the comparison <= t).
- **Skips.** Test: 986 of 8,362 transitions unbuildable ({'null_to_league': 986}); validation: 404 ({'null_to_league': 404}). Refusals (insufficient precedent) are reported next to every metric, never dropped.
- **Metrics.** Pinball loss on the log multiplier (quantile-equivariant, so every method is scored on the same target), empirical coverage of the q25-q75 range vs its nominal 50%, interval width ln(q75/q25), MdAPE of the median.

## Headline: test seasons, pooled

| method | n scored | refusal rate | coverage (nominal 50%) | width (median, log) | pinball (log, mean) | pinball q50 | MdAPE |
|---|---|---|---|---|---|---|---|
| Precedent (tuned comps engine) | 7375 | 0.01% | 50.7% | 0.542 | 0.1621 | 0.1859 | 28.6% |
| B0 - value unchanged (x1.0) | 7376 | 0.00% | - | - | - | 0.2049 | 33.3% |
| B1 - global quantiles (availability-filtered) | 7376 | 0.00% | 48.5% | 0.652 | 0.1852 | 0.2063 | 33.3% |
| B2 - age x position quantiles | 7376 | 0.00% | 53.7% | 0.598 | 0.1654 | 0.1881 | 28.6% |
| Skyline - LightGBM quantile (never served) | 7376 | 0.00% | 43.5% | 0.454 | 0.1552 | 0.1775 | 26.8% |

Precedent's range is honest out-of-sample: **50.7% of actual 12-month outcomes land inside the served q25-q75 band** (nominal 50%). It beats or matches every naive baseline on every metric while refusing only 0.01% of queries. The LightGBM skyline - same features, same availability discipline, no traceability - is ~4.2% better on pinball but materially *miscalibrated* (44% coverage): the traceability tax on sharpness is small, and the comp-pool quantiles buy back honest uncertainty.

## Test seasons, by season

| season | n scored | refusal rate | coverage (nominal 50%) | width (median, log) | pinball (log, mean) | pinball q50 | MdAPE |
|---|---|---|---|---|---|---|---|
| 2022 | 2148 | 0.05% | 49.3% | 0.555 | 0.1645 | 0.1881 | 28.9% |
| 2023 | 2479 | 0.00% | 51.1% | 0.542 | 0.1680 | 0.1927 | 28.6% |
| 2024 | 2748 | 0.00% | 51.3% | 0.529 | 0.1549 | 0.1780 | 27.6% |

## Segments (test, cells under 100 transitions suppressed)

### age_band

| age_band | n scored | refusal rate | coverage (nominal 50%) | width (median, log) | pinball (log, mean) | pinball q50 | MdAPE |
|---|---|---|---|---|---|---|---|
| 22-25 | 2664 | 0.00% | 50.3% | 0.585 | 0.1691 | 0.1937 | 30.0% |
| 26-29 | 2138 | 0.00% | 51.9% | 0.507 | 0.1384 | 0.1568 | 25.0% |
| 30+ | 1382 | 0.07% | 52.2% | 0.457 | 0.1319 | 0.1511 | 25.0% |
| <22 | 1191 | 0.00% | 47.4% | 0.713 | 0.2240 | 0.2608 | 36.6% |

### position_group

| position_group | n scored | refusal rate | coverage (nominal 50%) | width (median, log) | pinball (log, mean) | pinball q50 | MdAPE |
|---|---|---|---|---|---|---|---|
| DEF | 2391 | 0.04% | 51.6% | 0.538 | 0.1583 | 0.1817 | 28.2% |
| ATT | 2243 | 0.00% | 50.2% | 0.570 | 0.1673 | 0.1916 | 29.9% |
| MID | 2100 | 0.00% | 50.3% | 0.517 | 0.1547 | 0.1774 | 26.5% |
| GK | 641 | 0.00% | 49.9% | 0.579 | 0.1824 | 0.2095 | 33.3% |

### tier_jump

| tier_jump | n scored | refusal rate | coverage (nominal 50%) | width (median, log) | pinball (log, mean) | pinball q50 | MdAPE |
|---|---|---|---|---|---|---|---|
| same | 3981 | 0.03% | 51.4% | 0.524 | 0.1568 | 0.1796 | 27.3% |
| unknown | 1205 | 0.00% | 50.5% | 0.588 | 0.1687 | 0.1926 | 30.0% |
| up | 1178 | 0.00% | 48.0% | 0.598 | 0.1827 | 0.2112 | 33.3% |
| down | 1011 | 0.00% | 50.8% | 0.521 | 0.1511 | 0.1730 | 25.9% |

### value_bracket

| value_bracket | n scored | refusal rate | coverage (nominal 50%) | width (median, log) | pinball (log, mean) | pinball q50 | MdAPE |
|---|---|---|---|---|---|---|---|
| <1M | 3102 | 0.03% | 52.4% | 0.560 | 0.1724 | 0.1973 | 28.6% |
| 1-5M | 2675 | 0.00% | 49.3% | 0.560 | 0.1621 | 0.1866 | 30.0% |
| 5-15M | 1052 | 0.00% | 49.0% | 0.533 | 0.1544 | 0.1760 | 28.1% |
| >=15M | 546 | 0.00% | 50.5% | 0.424 | 0.1185 | 0.1366 | 22.2% |

### minutes_known

| minutes_known | n scored | refusal rate | coverage (nominal 50%) | width (median, log) | pinball (log, mean) | pinball q50 | MdAPE |
|---|---|---|---|---|---|---|---|
| True | 3808 | 0.00% | 50.2% | 0.532 | 0.1569 | 0.1798 | 28.0% |
| False | 3567 | 0.03% | 51.2% | 0.553 | 0.1676 | 0.1923 | 28.9% |

## Tuning (validation seasons only)

Random search: 300 sampled configs + the hand-set priors (trial 0), seed 20260718, scored on mean validation pinball with refusals imputed at the global-baseline pinball (so refusing cannot game the objective); constraints: refusal rate within 1pt of hand-set, coverage inside a loose 35-65% sanity band. The candidate scorer is a numpy twin of the serving engine; its parity with `find_comps` + `summarize_pool` is pinned by synthetic tests and a runtime gate on real queries (both passed).

| method | n scored | refusal rate | coverage (nominal 50%) | width (median, log) | pinball (log, mean) | pinball q50 | MdAPE |
|---|---|---|---|---|---|---|---|
| Hand-set priors | 2789 | 0.07% | 48.8% | 0.573 | 0.1748 | 0.1990 | 30.6% |
| Tuned (winner 7309dc25f471) | 2787 | 0.14% | 51.6% | 0.580 | 0.1700 | 0.1946 | 28.6% |
| Tuned, league-only ablation (club withheld) | 2787 | 0.14% | 51.9% | 0.585 | 0.1709 | 0.1956 | 28.4% |
| Skyline reference | 2791 | 0.00% | 40.3% | 0.444 | 0.1711 | 0.1967 | 29.2% |

Winner: trial 85, config hash `7309dc25f471` (imputed score 0.17000 vs hand-set 0.17471, ~2.7% better). The tuned weights moved the priors substantially - the heaviest terms are now W_ELO 1.43, W_DEST_CLUB_VALUE 0.92, W_RECENCY 0.32: with the destination a continuous question (strength band + club value percentile), destination-club similarity carries most of the distance mass, while the age and value gaps matter less than assumed once their hard filters have done the bounding. Frozen into `app/services/constants.py` (provenance comment + hash) before any test query was scored.

Top 10 trials by validation score:

| trial | hash | score | refusal rate | coverage |
|---|---|---|---|---|
| #85 | 7309dc25f471 | 0.17000 | 0.14% | 51.6% |
| #298 | c0b36358539a | 0.17014 | 0.14% | 51.9% |
| #246 | 5a2a716ffde2 | 0.17019 | 0.18% | 52.3% |
| #163 | 6af2002e9a7f | 0.17039 | 0.18% | 52.6% |
| #297 | 76687731bcf3 | 0.17066 | 0.18% | 51.4% |
| #235 | 8ea1126e47d4 | 0.17069 | 0.18% | 52.2% |
| #178 | ab60985a380f | 0.17072 | 0.07% | 52.1% |
| #275 | 2fe284f8a2a3 | 0.17088 | 0.04% | 53.8% |
| #139 | b98ed9691daa | 0.17097 | 0.14% | 52.4% |
| #245 | 02dfd53d9dde | 0.17102 | 0.07% | 51.7% |

## Confidence tiers

Tiers partition rather than rank, so they were searched on a small honesty grid (324 settings): a tier is honest when its validation coverage brackets the nominal 50% and higher confidence means narrower ranges. On the current validation records 72/324 settings pass that screen, but the shipped thresholds were frozen before the test seasons were scored; re-picking them after later data repairs would be post-hoc tuning, so the hand-set thresholds are kept until the next full retune. At those thresholds the high tier under-covers (45.5% on validation) - treat the *high* label as "strong precedent agreement", not "50% band guaranteed".

How the served tiers actually performed on test:

| confidence | n scored | refusal rate | coverage (nominal 50%) | width (median, log) | pinball (log, mean) | pinball q50 | MdAPE |
|---|---|---|---|---|---|---|---|
| medium | 4078 | 0.00% | 49.2% | 0.481 | 0.1416 | 0.1620 | 25.0% |
| low | 2832 | 0.00% | 54.2% | 0.717 | 0.1965 | 0.2260 | 33.3% |
| high | 465 | 0.00% | 41.5% | 0.314 | 0.1328 | 0.1506 | 23.5% |
| insufficient | 0 | 100.00% | - | - | - | - | - |

## Calibration decision

Pooled validation coverage was 51.6% - inside the 45-55% trigger band - so **no calibration was applied**: all `CAL_SHIFT_*` stay 0.0 and the served endpoints remain the nominal weighted q25/q75 of the pool. (The machinery exists and is tested: shifts would move endpoints to quantile levels (0.25-d, 0.75+d) of the same pool, keeping them order statistics of the shown comps. Re-deciding it per-tier after seeing the tier table above would be post-hoc fitting, so it is left as the documented next step for the high tier.) Test coverage came in at 50.7% pooled - the uncalibrated intervals are honest.

## Skyline cross-check: importances vs tuned weights

Gain importances of the quantile GBM (mean across folds and quantile levels) next to the frozen distance weights:

| GBM feature | gain |
|---|---|
| age_at_transfer | 2823 |
| ln_v_before | 1923 |
| to_elo_pct | 1883 |
| to_strength | 1609 |
| minutes_share_pre | 1583 |
| from_elo_pct | 1556 |
| to_club_value_pct | 1377 |
| from_strength | 1351 |
| from_club_value_pct | 1287 |
| sub_position_code | 1162 |
| season | 888 |
| tier_diff | 182 |
| to_tier | 85 |
| from_tier | 57 |
| position_code | 40 |

| distance weight | tuned value |
|---|---|
| W_LOG_VALUE | 0.211 |
| W_AGE | 0.052 |
| W_DEST_STRENGTH | 0.093 |
| W_ORIGIN_STRENGTH | 0.172 |
| W_ELO | 1.435 |
| W_DEST_CLUB_VALUE | 0.925 |
| W_ORIGIN_CLUB_VALUE | 0.181 |
| W_MINUTES | 0.070 |
| W_SUB_POSITION | 0.296 |
| W_RECENCY | 0.318 |

The GBM's top gain features (age_at_transfer, ln_v_before, to_elo_pct) and the heaviest tuned weights (W_ELO 1.43, W_DEST_CLUB_VALUE 0.92, W_RECENCY 0.32) can be read side by side. Where both agree the signal is robust; where the GBM leans on a feature the tuned weights keep small (or vice versa), that term is the candidate for the next search round with wider ranges - the comparison is printed here precisely so those divergences stay visible rather than smoothed over.

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

Seeds: search 20260718, skyline 20260718. Winning config hash `7309dc25f471`. All stages are deterministic; raw records live in `server/data/eval/` (gitignored, reproducible).
