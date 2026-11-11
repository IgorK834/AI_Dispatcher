"""AC-FEAT-001-03: UUID, UTC and integer money preserve their values."""

from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import Column, Integer, MetaData, Table, select
from sqlalchemy.exc import StatementError

from routepilot.shared.db.engine import make_engine
from routepilot.shared.db.types import UtcDateTime, UuidText
from routepilot.shared.money import Money
from routepilot.shared.units import km_to_m, m_to_km, metres_to_mm, mm_to_metres


@pytest.mark.ac("AC-FEAT-001-03")
def test_round_trip_and_naive_rejection() -> None:
    engine = make_engine("sqlite://")
    metadata = MetaData()
    table = Table(
        "values_test",
        metadata,
        Column("id", UuidText(), primary_key=True),
        Column("at", UtcDateTime()),
        Column("amount", Integer),
    )
    metadata.create_all(engine)
    identifier = uuid4()
    at = datetime(2026, 11, 11, 15, tzinfo=timezone(timedelta(hours=2)))
    money = Money(12345, "EUR")
    with engine.begin() as connection:
        connection.execute(table.insert().values(id=identifier, at=at, amount=money.amount_minor))
        row = connection.execute(select(table)).one()
        assert row.id == identifier
        assert row.at == at.astimezone(UTC)
        assert row.at.tzinfo == UTC
        assert row.amount == 12345 and isinstance(row.amount, int)
        with pytest.raises(StatementError) as error:
            connection.execute(
                table.insert().values(id=uuid4(), at=datetime(2026, 11, 11), amount=1)
            )
        assert isinstance(error.value.orig, ValueError)
    engine.dispose()


@pytest.mark.ac("AC-FEAT-001-03")
def test_money_and_unit_boundaries() -> None:
    with pytest.raises(ValueError, match="integer"):
        Money(1.5, "EUR")
    with pytest.raises(ValueError, match="currency"):
        Money(1, "euro")
    assert km_to_m(Decimal("1.23")) == 1230
    assert m_to_km(1235) == Decimal("1.24")
    assert metres_to_mm(Decimal("1.23")) == 1230
    assert mm_to_metres(1235) == Decimal("1.24")
