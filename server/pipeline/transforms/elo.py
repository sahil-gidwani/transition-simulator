"""ClubElo: mirror merge, deterministic name-mapping ladder, as-of rating lookups.

Rating data comes from two public ClubElo mirrors (data: clubelo.com). Mapping
ClubElo names to Transfermarkt clubs uses the audited ladder (committed manual
fixes first, then seven automatic stages, each requiring a unique hit). Clubs
in non-UEFA leagues are structurally excluded from the automatic stages -
ClubElo rates European clubs only. Unmapped and excluded clubs stay in the
output with mapped=False - a flagged fallback, never a silent drop.
"""

from __future__ import annotations

import difflib
from collections.abc import Mapping, Sequence

import polars as pl

from pipeline.config import ELO_ASOF_TOLERANCE_DAYS
from pipeline.naming import acronyms, normalize_club_name, tokens_prefix_match


def unify_mirrors(bimonthly: pl.DataFrame, daily: pl.DataFrame) -> pl.DataFrame:
    """Union of both mirrors with a within-snapshot percentile per rating.

    Duplicate (elo_name, snapshot_date) rows prefer the daily mirror. The
    percentile is computed within (source, snapshot_date) because the two
    mirrors rank different club universes; a single-club snapshot has no
    meaningful percentile (null).
    """
    both = pl.concat(
        [
            bimonthly.select("elo_name", "snapshot_date", "elo", source=pl.lit("bimonthly")),
            daily.select("elo_name", "snapshot_date", "elo", source=pl.lit("daily")),
        ]
    )
    both = both.sort(["elo_name", "snapshot_date", "source"]).unique(
        subset=["elo_name", "snapshot_date"], keep="last", maintain_order=True
    )
    n = pl.len().over("source", "snapshot_date")
    rank = pl.col("elo").rank(method="average").over("source", "snapshot_date")
    return both.with_columns(
        elo_pct=pl.when(n > 1).then((rank - 1.0) / (n - 1.0)).otherwise(None)
    ).sort(["elo_name", "snapshot_date"])


def _resolve_bridge_name(
    bridge_name: str, elo_names: set[str], norm_to_elo: dict[str, str]
) -> str | None:
    """A bridged name is only usable when it resolves to one mirror spelling."""
    if bridge_name in elo_names:
        return bridge_name
    return norm_to_elo.get(normalize_club_name(bridge_name))


def _short_vs_long(elo_tokens: frozenset[str], tm_tokens: frozenset[str]) -> bool:
    """A 1-token Elo name may not fuzzy-match a >=3-token TM name.

    Single generic tokens ("atletico", "sporting") survive inside long legal
    names of unrelated clubs; the shipped false positives all had this shape.
    """
    return len(elo_tokens) == 1 and len(tm_tokens) >= 3


def build_elo_mapping(
    clubs: pl.DataFrame,
    elo_names: Sequence[str],
    reep_bridge: Mapping[int, str],
    team_mapping: pl.DataFrame,
    manual_fixes: pl.DataFrame,
    european_leagues: frozenset[str],
) -> pl.DataFrame:
    """One row per club: the matched ClubElo name and the ladder stage that won.

    Stage order: manual fixes override everything; then the audited automatic
    ladder (reep id-bridge, exact normalized, token subset, token prefix,
    acronym, team-mapping, difflib >= 0.85). Normalized Elo names shared by
    several distinct clubs are unsafe and excluded from all automatic stages.
    Clubs outside `european_leagues` skip every automatic stage (stage
    "excluded_non_uefa"): ClubElo covers Europe only, so any automatic hit
    there is false by construction.
    """
    name_set = set(elo_names)
    norm_groups: dict[str, list[str]] = {}
    for name in sorted(name_set):
        norm_groups.setdefault(normalize_club_name(name), []).append(name)
    norm_to_elo = {norm: names[0] for norm, names in norm_groups.items() if len(names) == 1}
    elo_tokens = {name: frozenset(norm.split()) for norm, name in norm_to_elo.items()}

    manual: dict[int, str] = {
        int(cid): str(name) for cid, name in manual_fixes.select("club_id", "elo_name").iter_rows()
    }
    opta_to_elo: dict[str, str] = {
        normalize_club_name(str(opta)): str(elo)
        for opta, elo in team_mapping.select("team_opta", "team_clubelo").iter_rows()
    }

    records: list[tuple[int, str, str, str | None, str]] = []
    rows = clubs.select("club_id", "name", "club_code", "domestic_competition_id").sort("club_id")
    for club_id_raw, tm_name_raw, club_code, league_raw in rows.iter_rows():
        club_id = int(club_id_raw)
        tm_name = str(tm_name_raw)
        league = str(league_raw)
        # Two name candidates: the (often legal) club name and the URL slug,
        # which tends to carry the common short name ("psv-eindhoven").
        candidates = [normalize_club_name(tm_name)]
        if club_code:
            code_norm = normalize_club_name(str(club_code).replace("-", " "))
            if code_norm and code_norm not in candidates:
                candidates.append(code_norm)

        hit: tuple[str, str] | None = None
        if club_id in manual:
            hit = (manual[club_id], "manual")
        excluded = hit is None and league not in european_leagues
        if hit is None and not excluded and club_id in reep_bridge:
            resolved = _resolve_bridge_name(reep_bridge[club_id], name_set, norm_to_elo)
            if resolved is not None:
                hit = (resolved, "0_reep_id_bridge")
        if hit is None and not excluded:
            for norm in candidates:
                if norm in norm_to_elo:
                    hit = (norm_to_elo[norm], "1_exact_normalized")
                    break
        if hit is None and not excluded:
            for stage_name, matcher in (
                (
                    "2_token_subset",
                    lambda et, tm: (
                        not _short_vs_long(et, tm) and bool(et) and (et <= tm or tm <= et)
                    ),
                ),
                (
                    "3_token_prefix",
                    lambda et, tm: not _short_vs_long(et, tm) and tokens_prefix_match(et, tm),
                ),
            ):
                stage_hits = {
                    name
                    for norm in candidates
                    for name, etoks in elo_tokens.items()
                    if matcher(etoks, frozenset(norm.split()))
                }
                if len(stage_hits) == 1:
                    hit = (next(iter(stage_hits)), stage_name)
                    break
        if hit is None and not excluded:
            acro_pool = {a for norm in candidates for a in acronyms(norm.split())}
            acro_hits = {
                name
                for name, etoks in elo_tokens.items()
                if len(etoks) == 1 and next(iter(etoks)) in acro_pool
            }
            if len(acro_hits) == 1:
                hit = (next(iter(acro_hits)), "4_acronym")
        if hit is None and not excluded:
            for norm in candidates:
                if norm in opta_to_elo:
                    hit = (opta_to_elo[norm], "5_team_mapping")
                    break
        if hit is None and not excluded:
            close = difflib.get_close_matches(candidates[0], sorted(norm_to_elo), n=1, cutoff=0.85)
            if close and not _short_vs_long(
                frozenset(close[0].split()), frozenset(candidates[0].split())
            ):
                hit = (norm_to_elo[close[0]], "6_difflib")

        if hit is not None:
            elo_name, stage = hit
        else:
            elo_name, stage = (None, "excluded_non_uefa" if excluded else "unmapped")
        records.append((club_id, tm_name, league, elo_name, stage))

    return pl.DataFrame(
        records,
        schema={
            "club_id": pl.Int64,
            "tm_name": pl.String,
            "league": pl.String,
            "elo_name": pl.String,
            "stage": pl.String,
        },
        orient="row",
    ).with_columns(mapped=pl.col("elo_name").is_not_null())


def attach_universe_flags(mapping: pl.DataFrame, touches: pl.DataFrame) -> pl.DataFrame:
    """Mark clubs of the transition universe and how often transitions touch them."""
    out = mapping.join(touches.select("club_id", "universe_touches"), on="club_id", how="left")
    out = out.with_columns(universe_touches=pl.col("universe_touches").fill_null(0).cast(pl.Int32))
    return out.with_columns(in_universe=pl.col("universe_touches") > 0).sort("club_id")


def elo_asof(keys: pl.DataFrame, unified: pl.DataFrame, mapping: pl.DataFrame) -> pl.DataFrame:
    """Ratings as of each key's date: nearest snapshot at or before it, max 45d old.

    keys carries (club_id, asof_date) plus passthrough columns; row count and
    order are preserved. Unmapped clubs (elo_mapped=False) and mapped clubs
    with no snapshot inside the tolerance get null rating columns.
    """
    keyed = keys.with_row_index("__row")
    joined = keyed.join(
        mapping.filter(pl.col("mapped")).select("club_id", "elo_name"),
        on="club_id",
        how="left",
    ).with_columns(elo_mapped=pl.col("elo_name").is_not_null())
    with_name = joined.filter(pl.col("elo_mapped"))
    without = joined.filter(~pl.col("elo_mapped"))

    snaps = unified.select(
        "elo_name", pl.col("snapshot_date").alias("elo_date"), "elo", "elo_pct"
    ).sort(["elo_name", "elo_date"])
    matched = with_name.sort("asof_date").join_asof(
        snaps,
        left_on="asof_date",
        right_on="elo_date",
        by="elo_name",
        strategy="backward",
        tolerance=f"{ELO_ASOF_TOLERANCE_DAYS}d",
    )
    missing = without.with_columns(
        elo_date=pl.lit(None, dtype=pl.Date),
        elo=pl.lit(None, dtype=pl.Float64),
        elo_pct=pl.lit(None, dtype=pl.Float64),
    )
    return (
        pl.concat([matched, missing.select(matched.columns)])
        .sort("__row")
        .drop("__row", "elo_name")
    )
