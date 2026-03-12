"""Nail studio scoring logic."""

from typing import Any

from core.models import Listing, LocationIntel
from services.scoring.base_scorer import BaseScorer
from services.scoring.weights import NAIL_WEIGHTS


class NailScorer(BaseScorer):
    def score(
        self,
        listing: Listing,
        intel: LocationIntel | None = None,
    ) -> dict[str, Any]:
        w = NAIL_WEIGHTS

        # ── Disqualification check ───────────────────
        if w.require_wasseranschluss and not listing.wasseranschluss:
            return self._disqualified("Kein Wasseranschluss vorhanden")

        # ── Physical score ───────────────────────────
        physical_raw = (
            w.wasseranschluss * self.bool_score(listing.wasseranschluss)
            + w.lueftung * self.bool_score(listing.lueftung)
            + w.parkplaetze * self.bool_score(listing.parkplaetze)
        )
        physical_max = w.wasseranschluss + w.lueftung + w.parkplaetze

        # Etage penalty: ground floor (0) is ideal
        etage = listing.etage or 0
        etage_factor = 1.0 if etage == 0 else max(0.3, 1.0 - etage * 0.25)
        physical_raw *= etage_factor

        score_physical = self.scale_to_ten(
            physical_raw / physical_max if physical_max else 0
        )

        # ── Financial score ──────────────────────────
        if listing.mietpreis and listing.flaeche_m2 and listing.flaeche_m2 > 0:
            preis_per_m2 = float(listing.mietpreis) / float(listing.flaeche_m2)
            financial_raw = self.invert_normalize(preis_per_m2, 5.0, 25.0)
        else:
            financial_raw = 0.5  # neutral if unknown

        score_financial = self.scale_to_ten(financial_raw)

        # ── Location score ───────────────────────────
        location_raw = 0.5  # default neutral
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
            location_raw = 0.6 * competitor_factor + 0.4 * kaufkraft_factor

        score_location = self.scale_to_ten(location_raw)

        # ── Market score ─────────────────────────────
        market_raw = 0.5
        if intel and intel.mietspiegel and listing.mietpreis and listing.flaeche_m2:
            actual = float(listing.mietpreis) / float(listing.flaeche_m2)
            avg = float(intel.mietspiegel)
            if avg > 0:
                market_raw = self.invert_normalize(actual / avg, 0.5, 2.0)

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
                listing, score_physical, score_financial, score_location, score_market
            ),
        }

    def _estimate_revenue(
        self,
        listing: Listing,
        intel: LocationIntel | None,
    ) -> tuple[float | None, float | None, float]:
        w = NAIL_WEIGHTS
        if not listing.flaeche_m2:
            return None, None, 0.0

        area = float(listing.flaeche_m2)
        kaufkraft_factor = (
            float(intel.kaufkraft_index) / 100.0
            if intel and intel.kaufkraft_index
            else 1.0
        )

        rev_min = round(area * w.revenue_low * kaufkraft_factor, 2)
        rev_max = round(area * w.revenue_high * kaufkraft_factor, 2)
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
        score_location: float,
        score_market: float,
    ) -> dict:
        strengths: list[str] = []
        weaknesses: list[str] = []

        if listing.wasseranschluss:
            strengths.append("Wasseranschluss vorhanden")
        if listing.lueftung:
            strengths.append("Lüftung vorhanden")
        if listing.etage is not None and listing.etage == 0:
            strengths.append("Erdgeschoss (ideal für Laufkundschaft)")
        if score_financial >= 7:
            strengths.append("Günstiger Mietpreis pro m²")

        if not listing.lueftung:
            weaknesses.append("Keine Lüftung (wichtig für Nagelstudio-Chemikalien)")
        if listing.etage and listing.etage > 0:
            weaknesses.append(f"Etage {listing.etage} (Erdgeschoss bevorzugt)")
        if score_location < 5:
            weaknesses.append("Viele Konkurrenten in der Nähe")
        if not listing.parkplaetze:
            weaknesses.append("Keine Parkplätze")

        return {"strengths": strengths, "weaknesses": weaknesses}
