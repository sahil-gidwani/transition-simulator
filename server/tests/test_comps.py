"""Comps engine: hard filters, null policies, ranking, relaxation, survivorship."""

from __future__ import annotations

from datetime import date
from typing import Any

import polars as pl
import pytest
from api_factories import (
    make_club_seasons,
    make_league_seasons,
    make_players_processed,
    make_profile_stats,
    make_store,
    make_transitions,
)

from app.core.clock import FixedClock
from app.core.errors import ApiError
from app.repositories.players import PlayerRecord
from app.repositories.seasons import ClubSeason, LeagueSeason
from app.repositories.transitions import TransitionsRepo
from app.services.comps import QueryContext, build_query_context, find_comps
from app.services.constants import LADDER, POOL_K

SEASON_MIN = 2012

_PLAYER = PlayerRecord(
    player_id=1,
    name="Query Player",
    position_group="ATT",
    sub_position="Centre-Forward",
    date_of_birth=date(1998, 6, 15),
    foot="right",
    height_cm=180,
    current_club_id=10,
    current_club_name="Alpha FC",
    current_league="AA1",
    market_value_eur=10_000_000,
    market_value_asof=date(2026, 6, 1),
    last_season=2025,
)


def _query(**overrides: Any) -> QueryContext:
    fields: dict[str, Any] = {
        "player": _PLAYER,
        "value_eur": 10_000_000,
        "age": 25.0,
        "origin_tier": 1,
        "origin_strength": 18.0,
        "origin_tercile": 1,
        "minutes_share": 0.8,
        "latest_season": 2025,
    }
    fields.update(overrides)
    return QueryContext(**fields)


_DEST_LEAGUE = LeagueSeason(
    league="BB1",
    league_name="beta-league",
    country="Betaland",
    season=2025,
    tier=1,
    strength=18.0,
    n_clubs=18,
)
_DEST_CLUB = ClubSeason(
    club_id=21,
    club_name="Dest FC",
    league="BB1",
    season=2025,
    tercile=2,
    squad_value_eur=100_000_000,
    elo_pct=0.7,
)


def _strengths() -> pl.DataFrame:
    rows = [
        {"league": league, "season": season, "strength": 18.0}
        for league in ("AA1", "BB1", "CC1")
        for season in range(2010, 2026)
    ]
    return pl.DataFrame(
        rows, schema={"league": pl.String, "season": pl.Int16, "strength": pl.Float64}
    )


def _strengths_from(rows: list[dict[str, Any]]) -> pl.DataFrame:
    return pl.DataFrame(
        rows, schema={"league": pl.String, "season": pl.Int16, "strength": pl.Float64}
    )


def _find(
    universe: pl.DataFrame,
    query: QueryContext | None = None,
    club: ClubSeason | None = None,
    strengths: pl.DataFrame | None = None,
):  # type: ignore[no-untyped-def]
    return find_comps(
        query or _query(),
        _DEST_LEAGUE,
        club,
        universe,
        strengths if strengths is not None else _strengths(),
        SEASON_MIN,
    )


def _conforming(n: int, **overrides: Any) -> list[dict[str, Any]]:
    return [{"player_id": 100 + i, **overrides} for i in range(n)]


# --- hard filters ---------------------------------------------------------------


def test_position_group_never_relaxes() -> None:
    result = _find(make_transitions([{"position_group": "MID", "sub_position": None}]))
    assert result.pool == []
    assert result.quality.relaxation_level == len(LADDER) - 1


def test_age_band_is_inclusive_and_excludes_beyond() -> None:
    universe = make_transitions(
        [
            {"player_id": 100, "age_at_transfer": 22.0},  # exactly -3.0
            {"player_id": 101, "age_at_transfer": 28.0},  # exactly +3.0
            {"player_id": 102, "age_at_transfer": 25.0},
            {"player_id": 103, "age_at_transfer": 29.5},  # outside
        ]
    )
    result = _find(universe)
    assert result.quality.relaxation_level == 0
    assert sorted(c.player_id for c in result.pool) == [100, 101, 102]


def test_value_bracket_is_inclusive_and_excludes_beyond() -> None:
    universe = make_transitions(
        [
            {"player_id": 100, "v_before": 4_000_000},  # exactly 0.4x
            {"player_id": 101, "v_before": 25_000_000},  # exactly 2.5x
            {"player_id": 102, "v_before": 10_000_000},
            {"player_id": 103, "v_before": 3_900_000},  # 0.39x - outside
        ]
    )
    result = _find(universe)
    assert result.quality.relaxation_level == 0
    assert sorted(c.player_id for c in result.pool) == [100, 101, 102]


def test_destination_tier_equality_holds_at_every_ladder_level() -> None:
    result = _find(make_transitions([{"to_tier": 2}]))
    assert result.pool == []
    assert result.quality.relaxation_level == len(LADDER) - 1


def test_null_destination_tier_is_never_eligible() -> None:
    result = _find(make_transitions([{"to_tier": None, "to_tercile": None, "to_league": None}]))
    assert result.pool == []


def test_pre_scope_seasons_are_excluded() -> None:
    universe = make_transitions(
        [*_conforming(3), {"player_id": 200, "season": 2011, "transfer_date": date(2011, 8, 1)}]
    )
    result = _find(universe)
    assert 200 not in [c.player_id for c in result.pool]


def test_suspected_loans_never_reach_the_engine() -> None:
    repo = TransitionsRepo(
        make_transitions([{"player_id": 100}, {"player_id": 200, "suspected_loan": True}])
    )
    result = _find(repo.comps_universe)
    assert [c.player_id for c in result.pool] == [100]


# --- query-side null policies ----------------------------------------------------


def test_null_query_age_skips_the_age_filter_and_flags_it() -> None:
    universe = make_transitions([*_conforming(2), {"player_id": 200, "age_at_transfer": 45.0}])
    result = _find(universe, _query(age=None))
    assert 200 in [c.player_id for c in result.pool]
    assert result.quality.missing_age is True


def test_null_origin_tier_skips_the_origin_filter_and_flags_it() -> None:
    universe = make_transitions([{"player_id": 100, "from_tier": 4}])
    result = _find(universe, _query(origin_tier=None, origin_strength=None))
    assert [c.player_id for c in result.pool] == [100]
    assert result.quality.relaxation_level == len(LADDER) - 1  # still thin, but eligible
    assert result.quality.origin_tier_unknown is True


def test_null_query_minutes_share_is_flagged() -> None:
    result = _find(make_transitions(_conforming(3)), _query(minutes_share=None))
    assert result.quality.missing_minutes is True


# --- relaxation ladder ------------------------------------------------------------


def test_thin_pool_widens_age_first() -> None:
    universe = make_transitions(
        [*_conforming(2), {"player_id": 200, "age_at_transfer": 29.5}]  # within +/-5 only
    )
    result = _find(universe)
    assert result.quality.relaxation_level == 1
    assert result.quality.expanded_search is True
    assert result.quality.relaxation_steps == [LADDER[1].label]
    assert 200 in [c.player_id for c in result.pool]


def test_then_value_bracket_widens() -> None:
    universe = make_transitions(
        [*_conforming(2), {"player_id": 200, "v_before": 30_000_000}]  # 3.0x
    )
    result = _find(universe)
    assert result.quality.relaxation_level == 2
    assert 200 in [c.player_id for c in result.pool]


def test_then_origin_tier_widens_to_two() -> None:
    universe = make_transitions([*_conforming(2), {"player_id": 200, "from_tier": 3}])
    result = _find(universe)
    assert result.quality.relaxation_level == 3
    assert 200 in [c.player_id for c in result.pool]
    assert result.quality.relaxation_steps == [LADDER[1].label, LADDER[2].label, LADDER[3].label]


def test_null_comp_origin_tier_admitted_only_at_the_last_level() -> None:
    universe = make_transitions(
        [{"player_id": 200, "from_tier": None, "from_tercile": None, "from_league": None}]
    )
    result = _find(universe)
    assert [c.player_id for c in result.pool] == [200]
    assert result.quality.relaxation_level == len(LADDER) - 1


def test_relaxation_stops_as_soon_as_the_pool_is_big_enough() -> None:
    result = _find(make_transitions(_conforming(3)))
    assert result.quality.relaxation_level == 0
    assert result.quality.expanded_search is False
    assert result.quality.relaxation_steps == []


# --- ranking ---------------------------------------------------------------------


def test_closer_value_ranks_first() -> None:
    universe = make_transitions(
        [
            {"player_id": 100, "v_before": 20_000_000},
            {"player_id": 101, "v_before": 10_000_000},
            {"player_id": 102, "v_before": 15_000_000},
        ]
    )
    result = _find(universe)
    assert [c.player_id for c in result.pool] == [101, 102, 100]
    assert result.pool[0].similarity > result.pool[1].similarity


def test_outcome_never_enters_the_distance() -> None:
    universe = make_transitions(
        [
            {"player_id": 100, "multiplier": 0.5, "delta_pct": -0.5, "v_after": 5_000_000},
            {"player_id": 101, "multiplier": 1.5, "delta_pct": 0.5, "v_after": 15_000_000},
            {"player_id": 102, "v_before": 12_000_000},
        ]
    )
    result = _find(universe)
    decliner = next(c for c in result.pool if c.player_id == 100)
    riser = next(c for c in result.pool if c.player_id == 101)
    assert decliner.similarity == pytest.approx(riser.similarity)


def test_survivorship_guard_most_similar_decliner_tops_the_pool() -> None:
    universe = make_transitions(
        [
            # The decliner is the closest match (exact value)...
            {
                "player_id": 100,
                "v_before": 10_000_000,
                "multiplier": 0.6,
                "delta_pct": -0.4,
                "v_after": 6_000_000,
            },
            # ...the risers are further away.
            {"player_id": 101, "v_before": 22_000_000, "multiplier": 1.4, "delta_pct": 0.4},
            {"player_id": 102, "v_before": 23_000_000, "multiplier": 1.5, "delta_pct": 0.5},
        ]
    )
    result = _find(universe)
    top = result.pool[0]
    assert top.player_id == 100
    assert top.delta_pct < 0


def test_null_term_neither_penalizes_nor_rewards() -> None:
    # All active terms identical; season 2025 so even recency contributes zero.
    shared: dict[str, Any] = {"season": 2025, "transfer_date": date(2025, 7, 1)}
    universe = make_transitions(
        [
            {"player_id": 100, "minutes_share_pre": 0.8, **shared},  # exact minutes match
            {"player_id": 101, "minutes_share_pre": None, **shared},  # unknown minutes
            {"player_id": 102, "minutes_share_pre": 0.2, **shared},  # bad minutes gap
        ]
    )
    result = _find(universe)
    by_id = {c.player_id: c for c in result.pool}
    assert by_id[100].distance == pytest.approx(by_id[101].distance)  # both zero here
    assert by_id[102].distance > by_id[101].distance


def test_pool_is_capped_at_pool_k() -> None:
    universe = make_transitions(_conforming(POOL_K + 6))
    result = _find(universe)
    assert result.quality.pool_size == POOL_K
    assert len(result.pool) == POOL_K


# --- league strength terms ---------------------------------------------------------


def test_destination_strength_gap_outweighs_an_equal_origin_gap() -> None:
    # X's gap is on the DESTINATION side, Y's identical gap on the ORIGIN side;
    # W_DEST_STRENGTH > W_ORIGIN_STRENGTH so Y must rank ahead of X. A swapped
    # from/to strength join inverts this order, so this test pins the sides.
    strengths = _strengths_from(
        [
            {"league": "AA1", "season": 2023, "strength": 18.0},
            {"league": "BB1", "season": 2023, "strength": 18.0},
            {"league": "XD1", "season": 2023, "strength": 16.0},
            {"league": "YO1", "season": 2023, "strength": 16.0},
        ]
    )
    universe = make_transitions(
        [
            {"player_id": 100, "to_league": "XD1"},  # dest gap 2, origin gap 0
            {"player_id": 101, "from_league": "YO1"},  # dest gap 0, origin gap 2
            {"player_id": 102},  # both gaps 0: sanity anchor
        ]
    )
    result = _find(universe, strengths=strengths)
    assert [c.player_id for c in result.pool] == [102, 101, 100]


def test_comp_strength_is_read_at_the_comp_season_not_the_latest() -> None:
    # BB1 was far weaker in 2022; a 2022 comp must carry THAT season's gap.
    # A season-misaligned join makes both comps near-equal (recency alone).
    strengths = _strengths_from(
        [
            {"league": "AA1", "season": 2022, "strength": 18.0},
            {"league": "AA1", "season": 2023, "strength": 18.0},
            {"league": "BB1", "season": 2022, "strength": 10.0},
            {"league": "BB1", "season": 2023, "strength": 18.0},
        ]
    )
    universe = make_transitions(
        [
            {"player_id": 100},  # season 2023: dest strength 18 -> gap 0
            {"player_id": 101, "season": 2022, "transfer_date": date(2022, 7, 1)},  # gap 8
        ]
    )
    result = _find(universe, strengths=strengths)
    by_id = {c.player_id: c for c in result.pool}
    assert by_id[101].distance - by_id[100].distance > 1.0  # far beyond the recency delta


def test_missing_strength_rows_never_drop_a_comp() -> None:
    strengths = _strengths_from([{"league": "BB1", "season": 2023, "strength": 18.0}])
    universe = make_transitions([{"player_id": 100, "from_league": "ZZ9"}])
    result = _find(universe, strengths=strengths)
    assert [c.player_id for c in result.pool] == [100]  # null strength: term drops, row stays


def test_null_comp_sub_position_is_neutral_in_ranking() -> None:
    # The documented policy for a null comp feature: the term drops with
    # renormalization. A refactor to ne_missing()/fill_null would silently
    # score unknown sub-positions as full mismatches.
    shared: dict[str, Any] = {"season": 2025, "transfer_date": date(2025, 7, 1)}
    universe = make_transitions(
        [
            {"player_id": 100, **shared},  # exact sub-position match
            {"player_id": 101, "sub_position": None, **shared},  # unknown: neutral
            {"player_id": 102, "sub_position": "Right Winger", **shared},  # true mismatch
        ]
    )
    result = _find(universe)
    by_id = {c.player_id: c for c in result.pool}
    assert by_id[100].distance == pytest.approx(by_id[101].distance)
    assert by_id[102].distance > by_id[101].distance


def test_last_ladder_level_ignores_club_terms_for_ranking() -> None:
    # Two comps admitted only at the last level, differing ONLY in club-side
    # context. The level's label promises club terms are ignored: distances
    # must match and Elo coverage read zero despite the club having a rating.
    base: dict[str, Any] = {"from_tier": None, "from_league": None, "from_tercile": None}
    universe = make_transitions(
        [
            {"player_id": 100, "to_tercile": 2, "to_elo_pct": 0.7, **base},
            {"player_id": 101, "to_tercile": 3, "to_elo_pct": 0.1, **base},
        ]
    )
    result = _find(universe, club=_DEST_CLUB)
    assert result.quality.relaxation_level == len(LADDER) - 1
    assert result.quality.dest_elo_available is True
    assert result.quality.elo_pool_coverage == 0.0
    by_id = {c.player_id: c for c in result.pool}
    assert by_id[100].distance == pytest.approx(by_id[101].distance)


# --- Elo fallback -----------------------------------------------------------------


def test_elo_coverage_counts_comps_with_the_term_active() -> None:
    universe = make_transitions(
        [
            {"player_id": 100, "to_elo_pct": 0.7},
            {"player_id": 101, "to_elo_pct": 0.4},
            {"player_id": 102, "to_elo_pct": None, "to_elo": None},
        ]
    )
    result = _find(universe, club=_DEST_CLUB)
    assert result.quality.dest_elo_available is True
    assert result.quality.elo_pool_coverage == pytest.approx(2 / 3)


def test_missing_destination_elo_flags_the_fallback() -> None:
    club = ClubSeason(
        club_id=22,
        club_name="No Elo FC",
        league="BB1",
        season=2025,
        tercile=2,
        squad_value_eur=50_000_000,
        elo_pct=None,
    )
    result = _find(make_transitions(_conforming(3, to_elo_pct=0.5)), club=club)
    assert result.quality.dest_elo_available is False
    assert result.quality.elo_pool_coverage == 0.0


# --- build_query_context -----------------------------------------------------------


def _store_for_context(player_overrides: dict[str, Any]) -> Any:
    return make_store(
        players=make_players_processed([{"player_id": 1, **player_overrides}]),
        league_seasons=make_league_seasons([{"league": "AA1", "tier": 2, "strength": 17.5}]),
        club_seasons=make_club_seasons([{"club_id": 10, "league": "AA1", "tercile": 1}]),
        profile_stats=make_profile_stats([{"player_id": 1, "minutes_share": 0.65}]),
    )


def test_build_query_context_resolves_origin_and_minutes() -> None:
    store = _store_for_context({})
    player = store.players.get(1)
    assert player is not None
    query = build_query_context(player, store, FixedClock(date(2026, 7, 17)))
    assert query.value_eur == 10_000_000
    assert query.age == pytest.approx(28.09, abs=0.01)
    assert query.origin_tier == 2
    assert query.origin_strength == pytest.approx(17.5)
    assert query.origin_tercile == 1
    assert query.minutes_share == pytest.approx(0.65, abs=1e-6)
    assert query.latest_season == 2025


def test_build_query_context_without_value_raises_409() -> None:
    store = _store_for_context({"market_value_eur": None, "market_value_asof": None})
    player = store.players.get(1)
    assert player is not None
    with pytest.raises(ApiError) as excinfo:
        build_query_context(player, store, FixedClock(date(2026, 7, 17)))
    assert excinfo.value.status_code == 409
    assert excinfo.value.code == "player_without_value"


def test_build_query_context_with_zero_value_raises_409_not_a_crash() -> None:
    # Upstream uses 0 as a no-valuation sentinel; if a future vintage ships it
    # as a latest value, simulations must refuse cleanly, not hit log(0).
    store = _store_for_context({"market_value_eur": 0})
    player = store.players.get(1)
    assert player is not None
    with pytest.raises(ApiError) as excinfo:
        build_query_context(player, store, FixedClock(date(2026, 7, 17)))
    assert excinfo.value.status_code == 409
    assert excinfo.value.code == "player_without_value"


def test_build_query_context_tolerates_missing_context_rows() -> None:
    store = make_store(players=make_players_processed([{"player_id": 1, "date_of_birth": None}]))
    player = store.players.get(1)
    assert player is not None
    query = build_query_context(player, store, FixedClock(date(2026, 7, 17)))
    assert query.age is None
    assert query.origin_tier is None
    assert query.origin_tercile is None
    assert query.minutes_share is None
