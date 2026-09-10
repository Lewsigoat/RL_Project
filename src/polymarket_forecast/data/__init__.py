"""Data acquisition, normalization, provenance, and storage."""

from polymarket_forecast.data.collector import collect_markets
from polymarket_forecast.data.storage import ResearchStorage

__all__ = ["ResearchStorage", "collect_markets"]
