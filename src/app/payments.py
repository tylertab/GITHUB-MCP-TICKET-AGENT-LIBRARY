
def calculate_total(subtotal: float, tax_rate: float | None = None) -> float:
    if tax_rate is None:
        return subtotal * (1 + TAX_RATE) 
    return round(subtotal * (1 + tax_rate), 2)

