from datetime import date

import polars as pl
from factories import make_players, make_transfers, make_valuations

from pipeline.transforms.loans import flag_suspected_loans
from pipeline.transforms.transfers import annotate_scope, clean_transfers
from pipeline.transforms.transitions import (
    TRANSITIONS_SCHEMA,
    assemble_transitions,
    attach_player_attrs,
    elo_keys,
    filter_universe_rows,
    minutes_anchors,
)
from pipeline.transforms.windows import attach_outcomes, attach_v_after, attach_v_before

_T = date(2020, 7, 1)


def _base_rows(transfer_rows: list[dict[str, object]]) -> pl.DataFrame:
    transfers = make_transfers(transfer_rows)
    valuations = make_valuations(
        [
            {"player_id": pid, "date": d, "market_value_in_eur": v}
            for pid in {int(r.get("player_id", 1)) for r in transfer_rows}
            for d, v in [
                (date(2011, 5, 1), 1_000_000),  # v_before for a 2011 transfer
                (date(2012, 8, 1), 1_500_000),  # ... and its v_after
                (date(2020, 5, 1), 2_000_000),
                (date(2020, 11, 1), 3_000_000),  # v_before for a winter return leg
                (date(2021, 7, 1), 5_000_000),
            ]
        ]
    )
    cleaned, _ = clean_transfers(transfers)
    tf = annotate_scope(cleaned, covered_ids=[10, 20])
    tf, _ = flag_suspected_loans(tf)
    tf = attach_v_before(tf, valuations)
    tf = attach_v_after(tf, valuations)
    tf = attach_outcomes(tf, max_val_date=date(2026, 6, 12))
    return attach_player_attrs(tf, make_players([{"player_id": 1}]))


def _empty_enrichment(rows: pl.DataFrame) -> tuple[pl.DataFrame, ...]:
    club_seasons = pl.DataFrame(
        schema={
            "club_id": pl.Int64,
            "season": pl.Int32,
            "league": pl.String,
            "tercile": pl.Int8,
        }
    )
    league_seasons = pl.DataFrame(schema={"league": pl.String, "season": pl.Int32, "tier": pl.Int8})
    minutes = pl.DataFrame(schema={"anchor_id": pl.Int64, "minutes_share": pl.Float64})
    elo = rows.select(
        "row_idx",
        elo=pl.lit(None, dtype=pl.Float64),
        elo_pct=pl.lit(None, dtype=pl.Float64),
    )
    return club_seasons, league_seasons, minutes, elo


def test_pre_2012_seasons_are_excluded() -> None:
    rows = _base_rows(
        [
            {"player_id": 1, "transfer_date": date(2011, 8, 1)},
            {"player_id": 1, "transfer_date": _T},
        ]
    )
    # Give the 2011 row window values too, so only the season filter can drop it.
    universe = filter_universe_rows(rows)
    assert universe["season"].to_list() == [2020]


def test_loans_are_kept_and_flagged() -> None:
    rows = _base_rows(
        [
            {"player_id": 1, "transfer_date": _T, "transfer_fee": 0.0},
            {
                "player_id": 1,
                "transfer_date": date(2020, 12, 1),
                "from_club_id": 20,
                "to_club_id": 10,
                "transfer_fee": 0.0,
            },
        ]
    )
    universe = filter_universe_rows(rows)
    assert universe.height == 2
    assert universe["suspected_loan"].to_list() == [True, True]


def test_missing_enrichment_never_drops_rows() -> None:
    rows = filter_universe_rows(_base_rows([{"player_id": 1, "transfer_date": _T}]))
    club_seasons, league_seasons, minutes, elo = _empty_enrichment(rows)
    out = assemble_transitions(rows, club_seasons, league_seasons, minutes, elo, elo)
    assert out.height == 1
    assert out["from_league"].to_list() == [None]
    assert out["to_tier"].to_list() == [None]
    assert out["minutes_share_pre"].to_list() == [None]
    assert out["from_elo"].to_list() == [None]


def test_enrichment_joins_land_on_the_right_side() -> None:
    rows = filter_universe_rows(_base_rows([{"player_id": 1, "transfer_date": _T}]))
    club_seasons = pl.DataFrame(
        [(10, 2020, "AA1", 1), (20, 2020, "BB1", 3)],
        schema={
            "club_id": pl.Int64,
            "season": pl.Int32,
            "league": pl.String,
            "tercile": pl.Int8,
        },
        orient="row",
    )
    league_seasons = pl.DataFrame(
        [("AA1", 2020, 1), ("BB1", 2020, 2)],
        schema={"league": pl.String, "season": pl.Int32, "tier": pl.Int8},
        orient="row",
    )
    minutes = pl.DataFrame(
        [(int(rows["row_idx"][0]), 0.75)],
        schema={"anchor_id": pl.Int64, "minutes_share": pl.Float64},
        orient="row",
    )
    elo_from = rows.select("row_idx", elo=pl.lit(1800.0), elo_pct=pl.lit(0.9))
    elo_to = rows.select("row_idx", elo=pl.lit(1500.0), elo_pct=pl.lit(0.4))
    out = assemble_transitions(rows, club_seasons, league_seasons, minutes, elo_from, elo_to)
    row = out.row(0, named=True)
    assert (row["from_league"], row["to_league"]) == ("AA1", "BB1")
    assert (row["from_tier"], row["to_tier"]) == (1, 2)
    assert (row["from_tercile"], row["to_tercile"]) == (1, 3)
    assert (row["from_elo"], row["to_elo"]) == (1800.0, 1500.0)
    assert row["minutes_share_pre"] == 0.75
    assert row["multiplier"] == 2.5


def test_schema_contract() -> None:
    rows = filter_universe_rows(_base_rows([{"player_id": 1, "transfer_date": _T}]))
    club_seasons, league_seasons, minutes, elo = _empty_enrichment(rows)
    out = assemble_transitions(rows, club_seasons, league_seasons, minutes, elo, elo)
    assert dict(out.schema) == TRANSITIONS_SCHEMA


def test_minutes_anchors_and_elo_keys_shapes() -> None:
    rows = filter_universe_rows(_base_rows([{"player_id": 1, "transfer_date": _T}]))
    anchors = minutes_anchors(rows)
    assert anchors["window_start"].to_list() == [date(2019, 7, 2)]
    assert anchors["window_end"].to_list() == [_T]
    assert anchors["base_club_id"].to_list() == [10]
    keys = elo_keys(rows, "to")
    assert keys["club_id"].to_list() == [20]
    assert keys["asof_date"].to_list() == [_T]
