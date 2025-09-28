"""Payment utilities."""

from __future__ import annotations


DEFAULT_TAX_RATE = 0.08


def calculate_total(subtotal: float, tax_rate: float | None = None) -> float:
    """Return the subtotal with tax applied, defaulting to 8% when unspecified."""

    rate = DEFAULT_TAX_RATE if tax_rate is None else tax_rate
    return round(subtotal * (1 + rate), 2)
