"""Explicit half-up rounding at unit boundaries."""

from decimal import ROUND_HALF_UP, Decimal


def round_half_up(value: Decimal, places: int = 2) -> Decimal:
    return value.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)
