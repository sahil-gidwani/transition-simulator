"""Narrative templates: direction, precedent naming, honest caveats, determinism."""

from __future__ import annotations

from datetime import date
from typing import Any

from app.repositories.players import PlayerRecord
from app.services.comps import PoolQuality, ScoredComp
from app.services.narrative import build_narrative, format_eur
from app.services.valuation import ValueRange

TODAY = date(2026, 7, 17)


def _player(**overrides: Any) -> PlayerRecord:
    fields: dict[str, Any] = {
        "player_id": 1,
        "name": "Query Player",
        "position_group": "ATT",
        "sub_position": "Centre-Forward",
        "date_of_birth": date(1998, 6, 15),
        "foot": "right",
        "height_cm": 180,
        "current_club_id": 10,
        "current_club_name": "Alpha FC",
        "current_league": "AA1",
        "market_value_eur": 10_000_000,
        "market_value_asof": date(2026, 6, 1),
        "last_season": 2025,
    }
    fields.update(overrides)
    return PlayerRecord(**fields)


def _comp(name: str, delta_pct: float, **overrides: Any) -> ScoredComp:
    fields: dict[str, Any] = {
        "player_id": 100,
        "player_name": name,
        "transfer_date": date(2023, 7, 1),
        "season": 2023,
        "age_at_transfer": 25.0,
        "sub_position": "Centre-Forward",
        "from_club_name": "Origin FC",
        "to_club_name": "Dest FC",
        "from_league": "AA1",
        "to_league": "BB1",
        "v_before": 10_000_000,
        "v_after": round(10_000_000 * (1 + delta_pct)),
        "multiplier": 1 + delta_pct,
        "delta_pct": delta_pct,
        "distance": 0.1,
        "similarity": 0.9,
        "tags": [],
        "elo_term_used": False,
    }
    fields.update(overrides)
    return ScoredComp(**fields)


def _quality(**overrides: Any) -> PoolQuality:
    fields: dict[str, Any] = {
        "pool_size": 8,
        "relaxation_level": 0,
        "relaxation_steps": [],
        "expanded_search": False,
        "club_selected": False,
        "elo_pool_coverage": 0.8,
        "dest_elo_available": False,
        "missing_age": False,
        "missing_minutes": False,
        "origin_tier_unknown": False,
    }
    fields.update(overrides)
    return PoolQuality(**fields)


def _range(q25: float, q50: float, q75: float, value: int = 10_000_000) -> ValueRange:
    return ValueRange(
        q25_multiplier=q25,
        q50_multiplier=q50,
        q75_multiplier=q75,
        q25_eur=round(value * q25),
        q50_eur=round(value * q50),
        q75_eur=round(value * q75),
        iqr_log=0.2,
    )


def test_format_eur() -> None:
    assert format_eur(38_500_000) == "€38.5M"
    assert format_eur(12_000_000) == "€12M"
    assert format_eur(900_000) == "€900k"
    assert format_eur(500) == "€500"


def test_upward_read_names_the_range_and_precedents() -> None:
    pool = [_comp("Riser One", 0.30), _comp("Riser Two", 0.20), _comp("Flat One", 0.02)]
    text = build_narrative(
        _player(), "Premier League", _range(1.05, 1.2, 1.4), "medium", pool, _quality(), TODAY
    )
    assert "points up" in text
    assert "+20% within 12 months" in text
    assert "€10.5M to €14M" in text
    assert "medium confidence" in text
    assert "Riser One (Origin FC → Dest FC, 2023, +30%)" in text
    assert "Riser Two" in text


def test_downward_read() -> None:
    pool = [_comp("Faller", -0.3), _comp("Faller Two", -0.2)]
    text = build_narrative(
        _player(), "Beta League", _range(0.6, 0.75, 0.9), "low", pool, _quality(), TODAY
    )
    assert "points down" in text
    assert "-25% within 12 months" in text


def test_flat_read_is_called_mixed() -> None:
    pool = [_comp("A", 0.4), _comp("B", -0.35)]
    text = build_narrative(
        _player(), "Beta League", _range(0.7, 1.0, 1.35), "low", pool, _quality(), TODAY
    )
    assert "broadly flat" in text


def test_decliner_share_caveat() -> None:
    pool = [
        _comp("Up One", 0.3),
        _comp("Up Two", 0.2),
        _comp("Down One", -0.1),
        _comp("Down Two", -0.4),
    ]
    text = build_narrative(
        _player(), "Beta League", _range(0.8, 1.1, 1.3), "medium", pool, _quality(), TODAY
    )
    assert "2 of the 4 comparable moves lost value." in text


def test_small_pool_caveat() -> None:
    pool = [_comp("A", 0.1), _comp("B", 0.2), _comp("C", 0.15)]
    text = build_narrative(
        _player(),
        "Beta League",
        _range(1.0, 1.15, 1.25),
        "low",
        pool,
        _quality(pool_size=3),
        TODAY,
    )
    assert "Thin evidence: only 3 comparable moves" in text


def test_expanded_search_caveat_names_the_last_step() -> None:
    quality = _quality(
        expanded_search=True,
        relaxation_level=2,
        relaxation_steps=["age band widened to +/-5 years", "value bracket widened to 0.25-4x"],
    )
    pool = [_comp("A", 0.1) for _ in range(6)]
    text = build_narrative(
        _player(), "Beta League", _range(1.0, 1.1, 1.2), "low", pool, quality, TODAY
    )
    assert "the search was expanded (value bracket widened to 0.25-4x)" in text


def test_elo_fallback_caveat_only_when_a_club_was_selected() -> None:
    pool = [_comp("A", 0.1) for _ in range(6)]
    with_club = build_narrative(
        _player(),
        "Dest FC",
        _range(1.0, 1.1, 1.2),
        "low",
        pool,
        _quality(club_selected=True, dest_elo_available=False),
        TODAY,
    )
    league_only = build_narrative(
        _player(),
        "Beta League",
        _range(1.0, 1.1, 1.2),
        "low",
        pool,
        _quality(club_selected=False, dest_elo_available=False),
        TODAY,
    )
    assert "Club-strength ratings are unavailable" in with_club
    assert "Club-strength ratings" not in league_only


def test_stale_valuation_caveat() -> None:
    pool = [_comp("A", 0.1) for _ in range(6)]
    stale = build_narrative(
        _player(market_value_asof=date(2024, 6, 1)),
        "Beta League",
        _range(1.0, 1.1, 1.2),
        "low",
        pool,
        _quality(),
        TODAY,
    )
    fresh = build_narrative(
        _player(), "Beta League", _range(1.0, 1.1, 1.2), "low", pool, _quality(), TODAY
    )
    assert "valuation is dated 2024-06-01" in stale
    assert "valuation is dated" not in fresh


def test_insufficient_precedent_has_no_range_but_names_closest_evidence() -> None:
    pool = [_comp("Lone Comp", -0.2)]
    text = build_narrative(
        _player(),
        "Beta League",
        None,
        "insufficient",
        pool,
        _quality(
            pool_size=1,
            expanded_search=True,
            relaxation_steps=["origin league filter dropped; club-level terms ignored"],
        ),
        TODAY,
    )
    assert "Insufficient precedent" in text
    assert "only 1 comparable move" in text
    assert "no responsible value range" in text
    assert "Lone Comp" in text
    assert "€" not in text  # never a number band without precedent


def test_insufficient_with_empty_pool_reads_no_moves() -> None:
    text = build_narrative(
        _player(), "Beta League", None, "insufficient", [], _quality(pool_size=0), TODAY
    )
    assert "no comparable moves" in text


def test_narrative_is_deterministic() -> None:
    pool = [_comp("A", 0.1), _comp("B", -0.2)]
    args = (_player(), "Beta League", _range(0.9, 1.05, 1.2), "low", pool, _quality(), TODAY)
    assert build_narrative(*args) == build_narrative(*args)
