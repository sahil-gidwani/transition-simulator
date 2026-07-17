"""league_seasons.parquet + club_seasons.parquet access.

Query-side context (destinations, the player's current club/league) always
comes from the LATEST season's rows; historical strength (for comp-side
distance terms) is exposed as a (league, season, strength) frame. The
offline backtest builds season-exact query contexts via league_at/club_at.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import polars as pl


@dataclass(frozen=True)
class LeagueSeason:
    league: str
    league_name: str | None
    country: str | None
    season: int
    tier: int
    strength: float | None
    n_clubs: int


@dataclass(frozen=True)
class ClubSeason:
    club_id: int
    club_name: str
    league: str
    season: int
    tercile: int
    squad_value_eur: int
    elo_pct: float | None


def _league(row: dict[str, Any]) -> LeagueSeason:
    return LeagueSeason(
        league=row["league"],
        league_name=row["league_name"],
        country=row["country"],
        season=row["season"],
        tier=row["tier"],
        strength=row["strength"],
        n_clubs=row["n_clubs"],
    )


def _club(row: dict[str, Any]) -> ClubSeason:
    return ClubSeason(
        club_id=row["club_id"],
        club_name=row["club_name"],
        league=row["league"],
        season=row["season"],
        tercile=row["tercile"],
        squad_value_eur=row["squad_value_eur"],
        elo_pct=row["elo_pct"],
    )


class SeasonsRepo:
    def __init__(self, league_seasons: pl.DataFrame, club_seasons: pl.DataFrame) -> None:
        self._league_seasons = league_seasons
        self._club_seasons = club_seasons
        max_season = league_seasons["season"].max()
        self.latest_season: int = max_season if isinstance(max_season, int) else 0

    def leagues_latest(self) -> list[LeagueSeason]:
        """Latest-season leagues, strongest first (tier asc, strength desc, league asc)."""
        rows = (
            self._league_seasons.filter(pl.col("season") == self.latest_season)
            .sort(
                ["tier", "strength", "league"],
                descending=[False, True, False],
                nulls_last=True,  # a null-strength league must not top its tier
            )
            .iter_rows(named=True)
        )
        return [_league(row) for row in rows]

    def league_latest(self, league: str) -> LeagueSeason | None:
        rows = self._league_seasons.filter(
            (pl.col("league") == league) & (pl.col("season") == self.latest_season)
        )
        if rows.is_empty():
            return None
        return _league(rows.row(0, named=True))

    def clubs_latest(self, league: str) -> list[ClubSeason]:
        rows = (
            self._club_seasons.filter(
                (pl.col("league") == league) & (pl.col("season") == self.latest_season)
            )
            .sort("club_name")
            .iter_rows(named=True)
        )
        return [_club(row) for row in rows]

    def club_latest(self, club_id: int) -> ClubSeason | None:
        rows = self._club_seasons.filter(
            (pl.col("club_id") == club_id) & (pl.col("season") == self.latest_season)
        )
        if rows.is_empty():
            return None
        return _club(rows.row(0, named=True))

    def league_at(self, league: str, season: int) -> LeagueSeason | None:
        """League context as-of a specific season (backtest queries are historical)."""
        rows = self._league_seasons.filter(
            (pl.col("league") == league) & (pl.col("season") == season)
        )
        if rows.is_empty():
            return None
        return _league(rows.row(0, named=True))

    def club_at(self, club_id: int, season: int) -> ClubSeason | None:
        """Club context as-of a specific season (backtest queries are historical)."""
        rows = self._club_seasons.filter(
            (pl.col("club_id") == club_id) & (pl.col("season") == season)
        )
        if rows.is_empty():
            return None
        return _club(rows.row(0, named=True))

    def strength_frame(self) -> pl.DataFrame:
        """(league, season, strength) for vectorized comp-side joins."""
        return self._league_seasons.select("league", "season", "strength")
