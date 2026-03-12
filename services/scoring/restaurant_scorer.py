"""Restaurant scoring logic."""

from typing import Any

from core.models import Listing, LocationIntel
from services.scoring.base_scorer import BaseScorer
from services.scoring.weights import RESTAURANT_WEIGHTS


class RestaurantScorer(BaseScorer):
    def score(
        self,
        listing: Listing,
        intel: LocationIntel | None = None,
    ) -> dict[str, Any]:
        w = RESTAURANT_WEIGHTS

        # ── Disqualification check ───────────────────
        if w.require_kueche and not listing.kueche:
            return self._disqualified("Keine Küche vorhanden")

        # ── Physical score ───────────────────────────
        physical_parts = [
            w.kueche * self.bool_score(listing.kueche),
            w.starkstrom * self.bool_score(listing.starkstrom),
        ]

        # Area bonus
        area = float(listing.flaeche_m2) if listing.flaeche_m2 else 0.0
        area_factor = self.normalize(area, w.min_flaeche_m2, 200.0)
        physical_parts.append(w.flaeche * area_factor)

        physical_max = w.kueche + w.starkstrom + w.flaeche

        # Etage penalty
        etage = listing.etage or 0
        etage_factor = 1.0 if etage == 0 else max(0.2, 1.0 - etage * 0.3)

        physical_raw = sum(physical_parts) * etage_factor
        score_physical = self.scale_to_ten(
            physical_raw / physical_max if physical_max else 0
        )

        # ── Financial score ──────────────────────────
        financial_raw = 0.5
        if listing.mietpreis and listing.flaeche_m2 and listing.flaeche_m2 > 0:
            preis_per_m2 = float(listing.mietpreis) / float(listing.flaeche_m2)
            financial_raw = self.invert_normalize(preis_per_m2, 8.0, 30.0)

        # Ablöse penalty
        if listing.ablöse and intel and intel.mietspiegel:
            ablöse_ratio = (
                float(listing.ablöse) / (float(intel.mietspiegel) * area)
                if area > 0
                else 0
            )
            if ablöse_ratio > 12:  # more than 12 months rent
                financial_raw *= 0.7

        score_financial = self.scale_to_ten(financial_raw)

        # ── Location score ───────────────────────────
        location_raw = 0.5
        if intel:
            competitor_count = intel.competitor_count or 0
            competitor_factor = self.invert_normalize(
                competitor_count, 0, w.max_competitor_count * 2
            )
            kaufkraft_factor = (
                self.normalize(float(intel.kaufkraft_index), 80, 130)
                if intel.kaufkraft_index
                else 0.5
            )
            location_raw = 0.5 * competitor_factor + 0.5 * kaufkraft_factor

        score_location = self.scale_to_ten(location_raw)

        # ── Market score ─────────────────────────────
        market_raw = 0.5
        if intel and intel.leerstandsquote:
            market_raw = self.invert_normalize(float(intel.leerstandsquote), 0, 15)

        score_market = self.scale_to_ten(market_raw)

        # ── Overall ──────────────────────────────────
        score_gesamt = round(
            0.30 * score_physical
            + 0.25 * score_financial
            + 0.25 * score_location
            + 0.20 * score_market,
            2,
        )

        # ── Revenue estimate ─────────────────────────
        revenue_min, revenue_max, revenue_confidence = self._estimate_revenue(
            listing, intel
        )

        return {
            "score_gesamt": score_gesamt,
            "score_physical": score_physical,
            "score_financial": score_financial,
            "score_location": score_location,
            "score_market": score_market,
            "revenue_min": revenue_min,
            "revenue_max": revenue_max,
            "revenue_confidence": revenue_confidence,
            "explanation": self._build_explanation(
                listing, score_physical, score_financial
            ),
        }

    def _estimate_revenue(
        self,
        listing: Listing,
        intel: LocationIntel | None,
    ) -> tuple[float | None, float | None, float]:
        w = RESTAURANT_WEIGHTS
        if not listing.flaeche_m2:
            return None, None, 0.0

        area = float(listing.flaeche_m2)
        seats = area * w.seats_per_m2
        kaufkraft_factor = (
            float(intel.kaufkraft_index) / 100.0
            if intel and intel.kaufkraft_index
            else 1.0
        )

        rev_min = round(seats * w.revenue_low * kaufkraft_factor, 2)
        rev_max = round(seats * w.revenue_high * kaufkraft_factor, 2)
        confidence = 0.6 if intel and intel.kaufkraft_index else 0.3

        return rev_min, rev_max, confidence

    def _disqualified(self, reason: str) -> dict[str, Any]:
        return {
            "score_gesamt": 0.0,
            "score_physical": 0.0,
            "score_financial": 0.0,
            "score_location": 0.0,
            "score_market": 0.0,
            "revenue_min": None,
            "revenue_max": None,
            "revenue_confidence": 0.0,
            "explanation": {
                "disqualified": True,
                "reason": reason,
                "strengths": [],
                "weaknesses": [reason],
            },
        }

    @staticmethod
    def _build_explanation(
        listing: Listing,
        score_physical: float,
        score_financial: float,
    ) -> dict:
        strengths: list[str] = []
        weaknesses: list[str] = []

        if listing.kueche:
            strengths.append("Küche vorhanden")
        if listing.starkstrom:
            strengths.append("Starkstrom vorhanden")
        if listing.etage is not None and listing.etage == 0:
            strengths.append("Erdgeschoss (ideal für Gastronomie)")
        if score_financial >= 7:
            strengths.append("Günstiger Mietpreis")
        if listing.flaeche_m2 and float(listing.flaeche_m2) >= 100:
            strengths.append(f"Großzügige Fläche ({listing.flaeche_m2} m²)")

        if not listing.starkstrom:
            weaknesses.append("Kein Starkstrom (wichtig für Gastroküche)")
        if listing.etage and listing.etage > 0:
            weaknesses.append(f"Etage {listing.etage} (Erdgeschoss bevorzugt)")
        if score_physical < 5:
            weaknesses.append("Ausstattung nicht ideal für Gastronomie")

        return {"strengths": strengths, "weaknesses": weaknesses}
