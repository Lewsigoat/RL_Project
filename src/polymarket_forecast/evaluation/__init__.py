"""Proper scoring, dependence-aware inference, and power simulation."""

from polymarket_forecast.evaluation.bootstrap import paired_superiority_test
from polymarket_forecast.evaluation.metrics import summarize_probabilistic_forecast
from polymarket_forecast.evaluation.power import simulate_power

__all__ = [
    "paired_superiority_test",
    "simulate_power",
    "summarize_probabilistic_forecast",
]
