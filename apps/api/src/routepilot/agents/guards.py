"""Deterministic grounding and atomic token reservation; no provider or domain IO."""

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from threading import Lock
from typing import Any

IDENTIFIER = re.compile(r"\b(?:D\d+|MOCK-\d{6}|MAN-[0-9a-f]{8}|PLAN-[0-9a-f]{8})\b")
NUMBER = re.compile(
    r"(?P<prefix>[€])?\s*(?P<number>-?\d+(?:[\s\u00a0]\d{3})*(?:[.,]\d+)?)"
    r"\s*(?P<unit>kg\s*CO[₂2]|km|kg|min|EP|[€%lh])?"
)
COMPOUND_TIME = re.compile(r"\b(\d+)\s*h\s*(\d+)\s*min\b")


def _decimal(text: str) -> Decimal:
    return Decimal(re.sub(r"[\s\u00a0]", "", text).replace(",", "."))


def _facts(values: Iterable[Any]) -> tuple[set[str], set[Decimal]]:
    identifiers: set[str] = set()
    numbers: set[Decimal] = set()

    def visit(value: Any) -> None:
        if isinstance(value, Mapping):
            for key, item in value.items():
                if key != "untrusted_text":
                    visit(item)
        elif isinstance(value, (list, tuple, set)):
            for item in value:
                visit(item)
        elif isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
            numbers.add(Decimal(str(value)))
        elif isinstance(value, str):
            identifiers.update(IDENTIFIER.findall(value))
            try:
                numbers.add(_decimal(value))
            except InvalidOperation:
                # Timestamps are facts too; their displayed date/time components may be cited.
                if re.match(r"\d{4}-\d{2}-\d{2}T", value):
                    numbers.update(Decimal(v) for v in re.findall(r"\d+", value))

    for value in values:
        visit(value)
    return identifiers, numbers


def grounding_violations(text: str, facts: Iterable[Any]) -> list[str]:
    identifiers, numbers = _facts(facts)
    violations = [value for value in IDENTIFIER.findall(text) if value not in identifiers]
    text = IDENTIFIER.sub("", text)
    for match in COMPOUND_TIME.finditer(text):
        if Decimal(int(match[1]) * 60 + int(match[2])) not in numbers:
            violations.append(match[0])
    text = COMPOUND_TIME.sub("", text)
    for match in NUMBER.finditer(text):
        value = _decimal(match["number"])
        if not match["prefix"] and not match["unit"] and value == int(value) and 0 <= value <= 10:
            continue
        precision = Decimal(1).scaleb(
            -len(match["number"].split(".")[-1])
            if "." in match["number"]
            else -len(match["number"].split(",")[-1])
            if "," in match["number"]
            else 0
        )
        if not any(
            number.quantize(precision, rounding=ROUND_HALF_UP) == value for number in numbers
        ):
            violations.append(match[0].strip())
    return violations


class BudgetExceeded(Exception):
    """A hard limit reached; the caller must stop generation."""


@dataclass(frozen=True)
class Reservation:
    id: int
    input_tokens: int
    max_output_tokens: int


class TokenBudget:
    """Reserve input + the complete output cap, including hidden reasoning tokens.

    Unknown usage is charged at the full reservation. A provider exceeding its
    declared cap closes the budget; no subsequent request can be sent.
    """

    def __init__(self, limit: int, used: int = 0) -> None:
        self.limit = limit
        self.used = used
        self.tokens_in = used
        self.tokens_out = 0
        self.closed = False
        self._pending: dict[int, Reservation] = {}
        self._sequence = 0
        self._lock = Lock()

    def reserve(self, input_tokens: int, max_output_tokens: int) -> Reservation:
        with self._lock:
            reserved = sum(r.input_tokens + r.max_output_tokens for r in self._pending.values())
            if (
                self.closed
                or min(input_tokens, max_output_tokens) < 0
                or self.used + reserved + input_tokens + max_output_tokens > self.limit
            ):
                raise BudgetExceeded("TOKEN_BUDGET")
            self._sequence += 1
            ticket = Reservation(self._sequence, input_tokens, max_output_tokens)
            self._pending[ticket.id] = ticket
            return ticket

    def settle(self, ticket: Reservation, input_tokens: int, output_tokens: int) -> None:
        with self._lock:
            del self._pending[ticket.id]
            self.used += input_tokens + output_tokens
            self.tokens_in += input_tokens
            self.tokens_out += output_tokens
            if (
                min(input_tokens, output_tokens) < 0
                or input_tokens > ticket.input_tokens
                or output_tokens > ticket.max_output_tokens
                or self.used > self.limit
            ):
                self.closed = True
                raise BudgetExceeded("UNACCOUNTABLE_USAGE")

    def unknown(self, ticket: Reservation) -> None:
        with self._lock:
            del self._pending[ticket.id]
            self.used += ticket.input_tokens + ticket.max_output_tokens
            self.tokens_in += ticket.input_tokens
            self.tokens_out += ticket.max_output_tokens
