"""Tunable weight constants for scoring – adjust without changing logic."""

from dataclasses import dataclass


@dataclass(frozen=True)
class NailWeights:
    wasseranschluss: float = 0.20
    lueftung: float = 0.18
    fussgaenger: float = 0.15
    mietpreis_per_m2: float = 0.15
    parkplaetze: float = 0.10
    etage_penalty: float = 0.10
    competitor_penalty: float = 0.12

    # Disqualification flags
    require_wasseranschluss: bool = True

    # Revenue benchmarks (€/m²/year)
    revenue_low: float = 800.0
    revenue_high: float = 1400.0

    # Thresholds
    max_competitor_count: int = 5  # penalty starts above this


@dataclass(frozen=True)
class RestaurantWeights:
    kueche: float = 0.22
    starkstrom: float = 0.12
    flaeche: float = 0.15
    competitor_density: float = 0.15
    kaufkraft: float = 0.15
    ablöse_vs_mietspiegel: float = 0.10
    etage_penalty: float = 0.11

    # Disqualification flags
    require_kueche: bool = True

    # Revenue benchmarks (€/seat/year)
    revenue_low: float = 2000.0
    revenue_high: float = 4500.0

    # Thresholds
    max_competitor_count: int = 8
    min_flaeche_m2: float = 50.0
    seats_per_m2: float = 0.6  # estimate seats from area


NAIL_WEIGHTS = NailWeights()
RESTAURANT_WEIGHTS = RestaurantWeights()
