"""Historical query construction: transitions row -> serving inputs."""

from __future__ import annotations

from typing import Any

import pytest
from api_factories import make_club_seasons, make_league_seasons, make_transitions

from app.repositories.seasons import SeasonsRepo
from pipeline.eval.contexts import EvalQuery, SkippedQuery, build_eval_query


def _seasons() -> SeasonsRepo:
    # 2025 rows exist with DIFFERENT context so latest-season leakage is caught.
    return SeasonsRepo(
        make_league_seasons(
            [
                {"league": "AA1", "season": 2023, "tier": 1, "strength": 17.0},
                {"league": "BB1", "season": 2023, "tier": 2, "strength": 18.5},
                {"league": "AA1", "season": 2025, "tier": 3, "strength": 10.0},
                {"league": "BB1", "season": 2025, "tier": 3, "strength": 10.0},
            ]
        ),
        make_club_seasons(
            [
                {"club_id": 21, "season": 2023, "tercile": 2, "elo_pct": 0.75},
                {"club_id": 21, "season": 2025, "tercile": 3, "elo_pct": 0.25},
            ]
        ),
    )


def _row(**overrides: Any) -> dict[str, Any]:
    return make_transitions([overrides]).row(0, named=True)


def _build(**overrides: Any) -> EvalQuery | SkippedQuery:
    return build_eval_query(_row(**overrides), _seasons())


def test_field_mapping_is_at_transfer_not_latest() -> None:
    eq = _build()
    assert isinstance(eq, EvalQuery)
    assert eq.query.value_eur == 10_000_000  # v_before, not any later value
    assert eq.query.age == pytest.approx(25.0)
    assert eq.query.origin_tier == 1
    assert eq.query.origin_club_value_pct == pytest.approx(0.9)  # baked at-transfer value
    assert eq.query.origin_strength == pytest.approx(17.0)  # AA1 @ 2023, not @ 2025
    assert eq.query.minutes_share == pytest.approx(0.8, abs=1e-6)
    assert eq.query.latest_season == 2023  # recency measured from t
    assert eq.query.player.position_group == "ATT"
    assert eq.query.player.sub_position == "Centre-Forward"
    assert eq.query.player.market_value_eur == 10_000_000
    assert eq.dest_league.season == 2023
    assert eq.dest_league.tier == 2  # BB1 @ 2023, not @ 2025
    assert eq.dest_club is not None
    assert (eq.dest_club.tercile, eq.dest_club.elo_pct) == (2, 0.75)
    assert eq.actual_multiplier == pytest.approx(1.2)
    assert eq.minutes_known is True


def test_null_age_and_minutes_pass_through_as_none() -> None:
    eq = _build(age_at_transfer=None, minutes_share_pre=None)
    assert isinstance(eq, EvalQuery)
    assert eq.query.age is None
    assert eq.query.minutes_share is None
    assert eq.minutes_known is False


def test_null_origin_columns_pass_through_as_none() -> None:
    eq = _build(from_tier=None, from_club_value_pct=None)
    assert isinstance(eq, EvalQuery)
    assert eq.query.origin_tier is None
    assert eq.query.origin_club_value_pct is None


def test_null_from_league_drops_origin_strength_only() -> None:
    eq = _build(from_league=None, from_tier=None, from_tercile=None)
    assert isinstance(eq, EvalQuery)
    assert eq.query.origin_strength is None
    assert eq.query.player.current_league == ""


def test_unknown_from_league_season_drops_origin_strength_only() -> None:
    eq = _build(from_league="ZZ9")
    assert isinstance(eq, EvalQuery)
    assert eq.query.origin_strength is None


def test_null_to_league_is_a_counted_skip() -> None:
    skipped = _build(to_league=None, to_tier=None, to_tercile=None)
    assert isinstance(skipped, SkippedQuery)
    assert skipped.reason == "null_to_league"


def test_missing_dest_league_season_is_a_counted_skip() -> None:
    skipped = _build(to_league="ZZ9")
    assert isinstance(skipped, SkippedQuery)
    assert skipped.reason == "dest_league_missing"


def test_missing_dest_club_season_degrades_to_league_level() -> None:
    eq = _build(to_club_id=999)
    assert isinstance(eq, EvalQuery)
    assert eq.dest_club is None  # serving semantics: club terms drop


def test_nonpositive_v_before_is_a_counted_skip() -> None:
    skipped = _build(v_before=0)
    assert isinstance(skipped, SkippedQuery)
    assert skipped.reason == "nonpositive_v_before"
