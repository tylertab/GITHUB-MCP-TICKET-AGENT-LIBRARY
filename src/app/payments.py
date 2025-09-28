# Bug #5: uses undefined TAX_RATE when not provided via env/config.

def calculate_total(subtotal: float, tax_rate: float | None = None) -> float:
    if tax_rate is None:
        tax_rate = 0.08  # Default tax rate if none provided
        return round(subtotal * (1 + tax_rate), 2)

# Each snippet uses this format, repeated 0..N times:
# --- path: <repo-relative-path>
# --- start_line: <int>
# --- end_line: <int>
# --- code:
# <code lines…>