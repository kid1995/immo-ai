"""Revenue estimation service for nail studios and restaurants."""

from dataclasses import dataclass

from core.models import Listing, LocationIntel
from services.scoring.weights import NAIL_WEIGHTS, RESTAURANT_WEIGHTS


@dataclass(frozen=True)
class RevenueEstimate:
    revenue_min: float
    revenue_max: float
    confidence: float
    method: str
    details: dict


class RevenueEstimator:
    """Estimates annual revenue for a listing based on business type benchmarks."""

    def estimate_nail(
        self,
        listing: Listing,
        intel: LocationIntel | None = None,
    ) -> RevenueEstimate:
        """Nail Studio: flaeche_m2 × €800–1,400/m²/year × adjustments."""
        w = NAIL_WEIGHTS

        if not listing.flaeche_m2:
            return RevenueEstimate(
                revenue_min=0,
                revenue_max=0,
                confidence=0.0,
                method="no_data",
                details={"reason": "Keine Fläche angegeben"},
            )

        area = float(listing.flaeche_m2)
        kaufkraft = self._kaufkraft_factor(intel)
        competitor_factor = self._competitor_factor(intel, threshold=5)

        rev_min = area * w.revenue_low * kaufkraft * competitor_factor
        rev_max = area * w.revenue_high * kaufkraft * competitor_factor

        confidence = self._calculate_confidence(
            has_area=True,
            has_kaufkraft=intel is not None and intel.kaufkraft_index is not None,
            has_competitors=intel is not None and intel.competitor_count is not None,
        )

        return RevenueEstimate(
            revenue_min=round(rev_min, 2),
            revenue_max=round(rev_max, 2),
            confidence=confidence,
            method="area_benchmark",
            details={
                "area_m2": area,
                "rate_low": w.revenue_low,
                "rate_high": w.revenue_high,
                "kaufkraft_factor": round(kaufkraft, 3),
                "competitor_factor": round(competitor_factor, 3),
            },
        )

    def estimate_restaurant(
        self,
        listing: Listing,
        intel: LocationIntel | None = None,
    ) -> RevenueEstimate:
        """Restaurant: sitzplaetze × €2,000–4,500/seat/year × adjustments."""
        w = RESTAURANT_WEIGHTS

        if not listing.flaeche_m2:
            return RevenueEstimate(
                revenue_min=0,
                revenue_max=0,
                confidence=0.0,
                method="no_data",
                details={"reason": "Keine Fläche angegeben"},
            )

        area = float(listing.flaeche_m2)
        seats = area * w.seats_per_m2
        kaufkraft = self._kaufkraft_factor(intel)
        competitor_factor = self._competitor_factor(intel, threshold=8)

        rev_min = seats * w.revenue_low * kaufkraft * competitor_factor
        rev_max = seats * w.revenue_high * kaufkraft * competitor_factor

        confidence = self._calculate_confidence(
            has_area=True,
            has_kaufkraft=intel is not None and intel.kaufkraft_index is not None,
            has_competitors=intel is not None and intel.competitor_count is not None,
        )

        return RevenueEstimate(
            revenue_min=round(rev_min, 2),
            revenue_max=round(rev_max, 2),
            confidence=confidence,
            method="seat_benchmark",
            details={
                "area_m2": area,
                "estimated_seats": round(seats, 1),
                "rate_low": w.revenue_low,
                "rate_high": w.revenue_high,
                "kaufkraft_factor": round(kaufkraft, 3),
                "competitor_factor": round(competitor_factor, 3),
            },
        )

    @staticmethod
    def _kaufkraft_factor(intel: LocationIntel | None) -> float:
        if intel and intel.kaufkraft_index:
            return float(intel.kaufkraft_index) / 100.0
        return 1.0

    @staticmethod
    def _competitor_factor(intel: LocationIntel | None, threshold: int) -> float:
        """Reduce revenue estimate when competitor density is high."""
        if not intel or intel.competitor_count is None:
            return 1.0
        count = intel.competitor_count
        if count <= threshold:
            return 1.0
        # Reduce by 5% per extra competitor, minimum 0.5
        return max(0.5, 1.0 - (count - threshold) * 0.05)

    @staticmethod
    def _calculate_confidence(
        has_area: bool,
        has_kaufkraft: bool,
        has_competitors: bool,
    ) -> float:
        """Higher confidence when more data is available."""
        score = 0.3  # base confidence
        if has_area:
            score += 0.2
        if has_kaufkraft:
            score += 0.25
        if has_competitors:
            score += 0.25
        return min(1.0, score)
