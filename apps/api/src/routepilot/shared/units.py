"""Decimal domain units and integer database units."""

from decimal import Decimal

from routepilot.shared.rounding import round_half_up


def km_to_m(value: Decimal) -> int:
    return int(round_half_up(value * 1000, 0))


def m_to_km(value: int) -> Decimal:
    return round_half_up(Decimal(value) / 1000)


def metres_to_mm(value: Decimal) -> int:
    return int(round_half_up(value * 1000, 0))


def mm_to_metres(value: int) -> Decimal:
    return round_half_up(Decimal(value) / 1000)
