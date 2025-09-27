def calculate_total(subtotal: float, tax_rate: float | None = None) -> float:
    # BUG: relies on global TAX_RATE that doesn't exist if tax_rate is None
    if tax_rate is None:
        tax_rate = 0.08  # Default tax rate
    return round(subtotal * (1 + tax_rate), 2)