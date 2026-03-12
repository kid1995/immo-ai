"""Abstract base scorer with shared normalization helpers."""

from abc import ABC, abstractmethod
from typing import Any

from core.models import Listing, LocationIntel


class BaseScorer(ABC):
    """Base class for business-type-specific scoring."""

    @abstractmethod
    def score(
        self,
        listing: Listing,
        intel: LocationIntel | None = None,
    ) -> dict[str, Any]:
        """Return score dict matching ListingScore fields."""
        ...

    @staticmethod
    def normalize(value: float, min_val: float, max_val: float) -> float:
        """Normalize a value to 0.0–1.0 range, clamped."""
        if max_val <= min_val:
            return 0.5
        return max(0.0, min(1.0, (value - min_val) / (max_val - min_val)))

    @staticmethod
    def invert_normalize(value: float, min_val: float, max_val: float) -> float:
        """Higher input = lower score (e.g., rent per m²)."""
        if max_val <= min_val:
            return 0.5
        return max(0.0, min(1.0, 1.0 - (value - min_val) / (max_val - min_val)))

    @staticmethod
    def bool_score(value: bool | None) -> float:
        """Convert optional bool to 1.0 (True) or 0.0 (False/None)."""
        return 1.0 if value else 0.0

    @staticmethod
    def scale_to_ten(value: float) -> float:
        """Convert 0.0–1.0 to 0.0–10.0 score."""
        return round(max(0.0, min(10.0, value * 10.0)), 2)
