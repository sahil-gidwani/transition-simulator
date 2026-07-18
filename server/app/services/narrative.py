"""The scout's read: deterministic templates in club-owner language. No LLM.

Every sentence is a pure function of the simulation result, so the same
inputs always produce the same read. Caveats are honest by construction:
small pools, decliner counts, widened searches and stale valuations are
said out loud, never hidden.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from app.repositories.players import PlayerRecord
from app.services.comps import PoolQuality, ScoredComp
from app.services.constants import (
    DECLINER_CAVEAT_MIN_SHARE,
    NAMED_PRECEDENTS,
    SMALL_POOL_MAX,
    STALE_VALUE_DAYS,
)
from app.services.valuation import Confidence, ValueRange, direction_of


def format_eur(eur: int) -> str:
    """Club-owner numbers: 38_500_000 -> "38.5M", 900_000 -> "900k"."""
    sign = "-" if eur < 0 else ""
    magnitude = abs(eur)
    if magnitude >= 1_000_000:
        text = f"{magnitude / 1_000_000:.1f}".rstrip("0").rstrip(".")
        return f"{sign}€{text}M"
    if magnitude >= 1_000:
        return f"{sign}€{round(magnitude / 1_000)}k"
    return f"{sign}€{magnitude}"


def _pct(delta: float) -> str:
    return f"{delta:+.0%}"


def _precedent_line(pool: Sequence[ScoredComp], label: str) -> str | None:
    if not pool:
        return None
    named = [
        f"{comp.player_name} ({comp.from_club_name} → {comp.to_club_name}, "
        f"{comp.season}, {_pct(comp.delta_pct)})"
        for comp in pool[:NAMED_PRECEDENTS]
    ]
    return f"{label}: {'; '.join(named)}."


def build_narrative(
    player: PlayerRecord,
    dest_label: str,
    value_range: ValueRange | None,
    confidence: Confidence,
    pool: Sequence[ScoredComp],
    quality: PoolQuality,
    today: date,
    club_indistinct: bool = False,
) -> str:
    sentences: list[str] = []

    if value_range is None:
        count = "no" if quality.pool_size == 0 else f"only {quality.pool_size}"
        moves = "move" if quality.pool_size == 1 else "moves"
        sentences.append(
            f"Insufficient precedent: {count} comparable {moves} to "
            f"{dest_label} on record even after widening the search, so no responsible "
            "value range can be given."
        )
        closest = _precedent_line(pool, "The closest evidence we have")
        if closest:
            sentences.append(closest)
    else:
        q50 = value_range.q50_multiplier
        direction = direction_of(q50)
        if direction == "rise":
            verdict = "The precedent points up."
        elif direction == "decline":
            verdict = "The precedent points down."
        else:
            verdict = "The precedent is broadly flat."
        sentences.append(verdict)
        low_pct = _pct(value_range.q25_multiplier - 1.0)
        high_pct = _pct(value_range.q75_multiplier - 1.0)
        sentences.append(
            f"Across {quality.pool_size} comparable moves, a player in {player.name}'s "
            f"situation moving to {dest_label} typically lands at {_pct(q50 - 1.0)} within "
            f"12 months, with the middle half of outcomes between {low_pct} "
            f"and {high_pct} — a range of "
            f"{format_eur(value_range.q25_eur)} to {format_eur(value_range.q75_eur)} "
            f"({confidence} confidence)."
        )
        closest = _precedent_line(pool, "Closest precedents")
        if closest:
            sentences.append(closest)
        decliners = sum(1 for comp in pool if comp.delta_pct < 0)
        if pool and decliners / len(pool) >= DECLINER_CAVEAT_MIN_SHARE:
            sentences.append(f"{decliners} of the {len(pool)} comparable moves lost value.")
        if quality.pool_size <= SMALL_POOL_MAX:
            sentences.append(
                f"Thin evidence: only {quality.pool_size} comparable moves — treat the "
                "range as indicative, not bankable."
            )

    if club_indistinct:
        sentences.append(
            f"Precedent this rare doesn't distinguish destinations this fine: choosing "
            f"{dest_label} barely moves the league-level answer."
        )
    if quality.expanded_search and quality.relaxation_steps:
        sentences.append(
            f"To find this precedent the search was expanded ({quality.relaxation_steps[-1]})."
        )
    if quality.club_selected and not quality.dest_elo_available:
        sentences.append(
            "Club-strength ratings are unavailable for this destination club; squad-value "
            "tiers stand in for them."
        )
    if (
        player.market_value_asof is not None
        and (today - player.market_value_asof).days > STALE_VALUE_DAYS
    ):
        sentences.append(
            f"Note: {player.name}'s valuation is dated {player.market_value_asof.isoformat()} "
            "— over a year old — so the baseline itself may have moved."
        )
    return " ".join(sentences)
