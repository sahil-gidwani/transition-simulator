from datetime import date

import polars as pl
from factories import make_competitions

from pipeline.transforms.common import european_league_ids
from pipeline.transforms.elo import (
    attach_universe_flags,
    build_elo_mapping,
    elo_asof,
    unify_mirrors,
)


def _mirror(rows: list[tuple[str, date, float]]) -> pl.DataFrame:
    return pl.DataFrame(
        rows,
        schema={"elo_name": pl.String, "snapshot_date": pl.Date, "elo": pl.Float64},
        orient="row",
    )


def _clubs(rows: list[tuple[int, str, str | None]], league: str = "AA1") -> pl.DataFrame:
    return pl.DataFrame(
        [(cid, name, code, league) for cid, name, code in rows],
        schema={
            "club_id": pl.Int64,
            "name": pl.String,
            "club_code": pl.String,
            "domestic_competition_id": pl.String,
        },
        orient="row",
    )


# The default test league is European; tests opt out to exercise the exclusion.
_EUROPEAN = frozenset({"AA1"})


_NO_TEAM_MAPPING = pl.DataFrame(schema={"team_opta": pl.String, "team_clubelo": pl.String})
_NO_MANUAL = pl.DataFrame(
    schema={
        "elo_name": pl.String,
        "club_id": pl.Int64,
        "tm_name": pl.String,
        "note": pl.String,
    }
)


def _map_one(
    name: str,
    elo_names: list[str],
    club_code: str | None = None,
    manual: pl.DataFrame = _NO_MANUAL,
    bridge: dict[int, str] | None = None,
    league: str = "AA1",
) -> tuple[str | None, str]:
    out = build_elo_mapping(
        _clubs([(1, name, club_code)], league),
        elo_names,
        bridge or {},
        _NO_TEAM_MAPPING,
        manual,
        _EUROPEAN,
    )
    return out["elo_name"][0], out["stage"][0]


def test_unify_prefers_daily_on_snapshot_collision() -> None:
    day = date(2024, 7, 1)
    bimonthly = _mirror([("Lille", day, 1500.0)])
    daily = _mirror([("Lille", day, 1600.0)])
    out = unify_mirrors(bimonthly, daily)
    assert out.height == 1
    assert out["source"].to_list() == ["daily"]
    assert out["elo"].to_list() == [1600.0]


def test_unify_percentile_is_rank_over_snapshot() -> None:
    day = date(2024, 7, 1)
    bimonthly = _mirror([("A", day, 1400.0), ("B", day, 1500.0), ("C", day, 1600.0)])
    out = unify_mirrors(bimonthly, _mirror([])).sort("elo")
    assert out["elo_pct"].to_list() == [0.0, 0.5, 1.0]


def test_unify_single_club_snapshot_has_null_percentile() -> None:
    out = unify_mirrors(_mirror([("A", date(2024, 7, 1), 1400.0)]), _mirror([]))
    assert out["elo_pct"].to_list() == [None]


def test_manual_fix_overrides_automatic_stages() -> None:
    manual = pl.DataFrame(
        [("Steaua", 1, "SC Fotbal Club FCSB SA", "lineage")],
        schema=_NO_MANUAL.schema,
        orient="row",
    )
    # Without the manual row, "Betis" would exact-match; the manual target wins.
    elo_name, stage = _map_one("Betis", ["Betis", "Steaua"], manual=manual)
    assert (elo_name, stage) == ("Steaua", "manual")


def test_exact_normalized_match() -> None:
    assert _map_one("FC Barcelona", ["Barcelona"]) == ("Barcelona", "1_exact_normalized")


def test_ambiguous_normalized_elo_names_never_automatch() -> None:
    # Both raw Elo names normalize to "cska sofia" (digits drop): unsafe.
    elo_name, stage = _map_one("CSKA Sofia", ["CSKA Sofia", "CSKA 1948 Sofia"])
    assert (elo_name, stage) == (None, "unmapped")


def test_token_subset_requires_unique_hit() -> None:
    assert _map_one("Rangers Glasgow", ["Rangers"]) == ("Rangers", "2_token_subset")
    elo_name, stage = _map_one("United City", ["United", "City"])
    assert (elo_name, stage) == (None, "unmapped")


def test_token_prefix_stage() -> None:
    assert _map_one("Borussia Moenchengladbach", ["Gladbach FC Borussia"]) == (
        "Gladbach FC Borussia",
        "3_token_prefix",
    ) or _map_one("Borussia Moenchengladbach", ["Borussia Moenchengl"]) == (
        "Borussia Moenchengl",
        "3_token_prefix",
    )


def test_acronym_stage() -> None:
    assert _map_one("Paris Saint Germain", ["PSG"]) == ("PSG", "4_acronym")


def test_club_code_slug_is_a_candidate() -> None:
    elo_name, stage = _map_one("Some Legal Name SA", ["Eindhoven"], club_code="eindhoven")
    assert (elo_name, stage) == ("Eindhoven", "1_exact_normalized")


def test_difflib_below_cutoff_stays_unmapped() -> None:
    elo_name, stage = _map_one("Gornik Zabrze", ["Gornik Leczna"])
    assert (elo_name, stage) == (None, "unmapped")


def test_difflib_close_match_maps() -> None:
    elo_name, stage = _map_one("Feyenoord Rotterdam NV", ["Feyenoord Roterdam"])
    assert stage in {"3_token_prefix", "6_difflib"}
    assert elo_name == "Feyenoord Roterdam"


def test_reep_bridge_resolves_spelling_via_normalization() -> None:
    elo_name, stage = _map_one("Unrecognizable Holding PLC", ["Man City"], bridge={1: "MAN CITY"})
    assert (elo_name, stage) == ("Man City", "0_reep_id_bridge")


def test_unmapped_club_keeps_its_row() -> None:
    out = build_elo_mapping(
        _clubs([(1, "Palmeiras", None)]), ["Barcelona"], {}, _NO_TEAM_MAPPING, _NO_MANUAL, _EUROPEAN
    )
    assert out.height == 1
    assert not out["mapped"][0]
    assert out["stage"][0] == "unmapped"


def test_non_uefa_club_skips_every_automatic_stage() -> None:
    # Exact doppelganger AND an id-bridge entry: both would hit, both are
    # false by construction outside UEFA (ClubElo covers Europe only).
    elo_name, stage = _map_one("Palmeiras", ["Palmeiras"], league="BRA1")
    assert (elo_name, stage) == (None, "excluded_non_uefa")
    elo_name, stage = _map_one("Palmeiras", ["Palmeiras"], league="BRA1", bridge={1: "Palmeiras"})
    assert (elo_name, stage) == (None, "excluded_non_uefa")


def test_manual_fix_still_maps_non_uefa_club() -> None:
    manual = pl.DataFrame(
        [("Palmeiras", 1, "SE Palmeiras", "curated")], schema=_NO_MANUAL.schema, orient="row"
    )
    elo_name, stage = _map_one("SE Palmeiras", ["Palmeiras"], manual=manual, league="BRA1")
    assert (elo_name, stage) == ("Palmeiras", "manual")


def test_one_token_elo_never_matches_three_token_name_by_subset() -> None:
    # The River Plate shape: "atletico" alone is a subset of the long legal name.
    elo_name, stage = _map_one("Club Atletico River Plate", ["Atletico"])
    assert (elo_name, stage) == (None, "unmapped")


def test_one_token_elo_never_matches_three_token_name_by_prefix() -> None:
    # The Vissel Kobe shape: "kobenhavn" starts with the token "kobe".
    elo_name, stage = _map_one("Rakuten Vissel Kobe", ["Kobenhavn"])
    assert (elo_name, stage) == (None, "unmapped")


def test_one_token_elo_never_matches_three_token_name_by_difflib() -> None:
    # String-similar above the 0.85 cutoff, but 1 Elo token vs 3 TM tokens.
    elo_name, stage = _map_one("Abcdefghijklmnopqrst X Y", ["Abcdefghijklmnopqrsu"])
    assert (elo_name, stage) == (None, "unmapped")


def test_european_league_ids_filters_by_confederation_and_type() -> None:
    competitions = make_competitions(
        [
            {"competition_id": "AA1", "confederation": "europa"},
            {"competition_id": "BRA1", "confederation": "amerika"},
            {"competition_id": "CUP", "type": "domestic_cup", "confederation": "europa"},
        ]
    )
    assert european_league_ids(competitions) == ["AA1"]


def test_one_token_elo_still_matches_two_token_name() -> None:
    # The Inter-Miami shape is legitimate inside Europe (e.g. "Inter Turku");
    # outside Europe it must be caught by the confederation exclusion, not
    # this guard.
    assert _map_one("Inter Miami", ["Inter"]) == ("Inter", "2_token_subset")


def test_attach_universe_flags() -> None:
    mapping = build_elo_mapping(
        _clubs([(1, "FC Barcelona", None), (2, "Palmeiras", None)]),
        ["Barcelona"],
        {},
        _NO_TEAM_MAPPING,
        _NO_MANUAL,
        _EUROPEAN,
    )
    touches = pl.DataFrame(
        [(1, 5)], schema={"club_id": pl.Int64, "universe_touches": pl.Int64}, orient="row"
    )
    out = attach_universe_flags(mapping, touches)
    assert out["in_universe"].to_list() == [True, False]
    assert out["universe_touches"].to_list() == [5, 0]


def _asof_setup() -> tuple[pl.DataFrame, pl.DataFrame]:
    unified = unify_mirrors(
        _mirror(
            [
                ("Barcelona", date(2024, 6, 1), 1900.0),
                ("Barcelona", date(2024, 7, 1), 1950.0),
            ]
        ),
        _mirror([]),
    )
    mapping = build_elo_mapping(
        _clubs([(1, "FC Barcelona", None), (2, "Palmeiras", None)]),
        ["Barcelona"],
        {},
        _NO_TEAM_MAPPING,
        _NO_MANUAL,
        _EUROPEAN,
    )
    return unified, mapping


def test_elo_asof_nearest_at_or_before_wins() -> None:
    unified, mapping = _asof_setup()
    keys = pl.DataFrame(
        [(1, date(2024, 7, 15), "x")],
        schema={"club_id": pl.Int64, "asof_date": pl.Date, "tag": pl.String},
        orient="row",
    )
    out = elo_asof(keys, unified, mapping)
    assert out["elo"].to_list() == [1950.0]
    assert out["elo_date"].to_list() == [date(2024, 7, 1)]
    assert out["tag"].to_list() == ["x"]


def test_elo_asof_tolerance_edge() -> None:
    unified, mapping = _asof_setup()
    keys = pl.DataFrame(
        [(1, date(2024, 8, 15)), (1, date(2024, 8, 16))],
        schema={"club_id": pl.Int64, "asof_date": pl.Date},
        orient="row",
    )
    out = elo_asof(keys, unified, mapping)
    # 2024-07-01 snapshot is 45 days old on Aug 15 (in tolerance), 46 on Aug 16.
    assert out["elo"].to_list() == [1950.0, None]


def test_elo_asof_unmapped_club_gets_nulls_and_flag() -> None:
    unified, mapping = _asof_setup()
    keys = pl.DataFrame(
        [(2, date(2024, 7, 15)), (1, date(2024, 7, 15))],
        schema={"club_id": pl.Int64, "asof_date": pl.Date},
        orient="row",
    )
    out = elo_asof(keys, unified, mapping)
    assert out["elo_mapped"].to_list() == [False, True]
    assert out["elo"].to_list() == [None, 1950.0]
    assert out["club_id"].to_list() == [2, 1]  # caller order preserved
