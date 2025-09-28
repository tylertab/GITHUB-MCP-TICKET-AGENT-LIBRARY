def calculate_total(subtotal: float, tax_rate: float | None = None) -> float:
    TAX_RATE = 0.08
    if tax_rate is None:
        return round(subtotal * (1 + TAX_RATE), 2)
    return round(subtotal * (1 + tax_rate), 2)
    return round(subtotal * (1 + tax_rate), 2)
