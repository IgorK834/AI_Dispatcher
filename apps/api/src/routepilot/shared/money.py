"""Money is an integer number of minor units and a currency code."""

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Money:
    amount_minor: int
    currency: str

    def __post_init__(self) -> None:
        if type(self.amount_minor) is not int:
            raise ValueError("money amount must be an integer in minor units")
        if not re.fullmatch(r"[A-Z]{3}", self.currency):
            raise ValueError("currency must be a three-letter uppercase ISO-4217 code")
