"""Property tests of the partner-aware pool cut (FEAT-010 FR-8, AC-FEAT-010-09)."""

from datetime import timedelta
from decimal import Decimal

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from routepilot.optimization.engine.models import EngineParams
from routepilot.optimization.engine.prefilter import offer_pool
from tests.unit.optimization.factories import T, driver, offer, point, snapshot

PLACES = [point(f"P{n}", 49 + 0.4 * (n % 5), 15 + 0.9 * (n // 5)) for n in range(15)]
OFFERS = st.lists(
    st.tuples(
        st.integers(0, 14),
        st.integers(0, 14),
        st.integers(1_000, 90_000),
        st.sampled_from([200, 600, 2_000]),  # 2 000 kg never fits: a prefilter rejection
    ).filter(lambda item: item[0] != item[1]),
    min_size=1,
    max_size=24,
)


@pytest.mark.ac("AC-FEAT-010-09")
@settings(deadline=None)
@given(OFFERS, st.integers(1, 12))
def test_pool_is_repeatable_unchanged_when_small_and_keeps_the_best_half_when_cut(
    raw: list[tuple[int, int, int, int]], limit: int
) -> None:
    d = driver(PLACES[0])
    window = (T, T + timedelta(days=2))
    offers = [
        offer(
            f"O{n:02}",
            PLACES[a],
            PLACES[b],
            revenue=revenue,
            weight=kg,
            pickup=window,
            delivery=window,
        )
        for n, (a, b, revenue, kg) in enumerate(raw)
    ]
    source = snapshot([d], offers).model_copy(
        update={"params": EngineParams(max_pool_per_driver=limit)}
    )
    pool, rejected, truncated = offer_pool(source, d)
    assert (pool, rejected, truncated) == offer_pool(source, d)
    ids = [o.id for o in pool]
    assert ids == sorted(ids) and not set(ids) & set(rejected)
    passing = [o for o in offers if o.id not in rejected]
    assert truncated is (len(passing) > limit)
    if not truncated:
        assert ids == sorted(o.id for o in passing)  # the FEAT-003 FR-17 pool
        return

    def ratio(o: object) -> tuple[Decimal, str]:
        item = next(candidate for candidate in passing if candidate is o)
        deadhead, _ = source.matrix.leg(d.position, item.stops[0].point)
        loaded, _ = source.matrix.leg(item.stops[0].point, item.stops[1].point)
        return -Decimal(item.revenue_minor or 0) / (deadhead + loaded), item.id

    best = sorted(passing, key=ratio)[: (limit + 1) // 2]
    assert len(ids) == limit
    assert {o.id for o in best} <= set(ids)
