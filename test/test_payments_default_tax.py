"""
Goal: when tax_rate is None, use a default (e.g., 8%) and round to 2 decimals.
"""
from app.payments import calculate_total

def test_default_tax_applies_when_none():
    assert calculate_total(100.0) == 108.0

def test_explicit_tax_is_used_and_rounded():
    assert calculate_total(100.0, 0.075) == 107.5
