"""Deterministic financial calculation engine.

These modules are the single source of truth for every number in the product.
The AI layer explains their output; it never produces it.
"""

from app.calculations.base import CalcResult, money, pct, safe_div

__all__ = ["CalcResult", "money", "pct", "safe_div"]
