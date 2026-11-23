from __future__ import annotations

from pathlib import Path

import pytest

from profileguard import targets
from profileguard.merger import AwkImpl, available_awks, find_awk

FIXTURES = Path(__file__).parent / "fixtures"
PR4_FIXTURE = FIXTURES / "flipper-accountdb.pr4-c8a97b0.awk"
PR4_BLOB = "666053f332e5a9dc9e8d32023f539bce71f32652"


def primary_awk() -> AwkImpl:
    """mawk first: it is what Debian, and so the device image, runs as awk."""
    impl = find_awk("mawk") or (available_awks() or [None])[0]
    if impl is None:
        pytest.skip("no awk implementation on PATH")
    return impl


@pytest.fixture(scope="session")
def awk() -> AwkImpl:
    return primary_awk()


@pytest.fixture(scope="session")
def all_awks() -> list[AwkImpl]:
    impls = available_awks()
    if not impls:
        pytest.skip("no awk implementation on PATH")
    return impls


@pytest.fixture(scope="session")
def snapshot() -> targets.Target:
    return targets.snapshot()


@pytest.fixture(scope="session")
def pr4() -> targets.Target:
    # Read before it was added (tests/fixtures/README.md); unreviewed in the trust model.
    return targets.from_file(PR4_FIXTURE, allow_unreviewed=True)
