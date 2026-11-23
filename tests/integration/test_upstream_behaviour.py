"""Run every scenario through real upstream scripts and pin what each one does.

These are not wishes: they record the behaviour of the bundled snapshot (dev@8c9ffc7) and of two
earlier revisions kept as fixtures, so a change upstream shows up here as a failing expectation
that has to be looked at and updated.
"""

from __future__ import annotations

import pytest

from profileguard.merger import AwkImpl
from profileguard.runner import Status, run_all
from profileguard.scenarios import SCENARIOS
from profileguard.targets import Target

EXPECTED_FAILURES = {
    "snapshot": set(),  # dev@8c9ffc7: AM-10 fixed by #4, AM-11 and AM-13 by 8c9ffc7
    "old_dev": {"AM-10", "AM-11", "AM-13"},  # dev@bb92d87, before both
    "pr4": {"AM-11", "AM-12", "AM-13"},  # #4 alone
}


def _failing(target: Target, awks: list[AwkImpl]) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for r in run_all(list(SCENARIOS), target, awks):
        assert r.status is not Status.ERROR, r.error
        if r.status is Status.FAIL:
            out.setdefault(r.awk.name, set()).add(r.scenario.id)
    return out


@pytest.mark.parametrize("which", sorted(EXPECTED_FAILURES))
def test_pinned_behaviour(
    which: str, request: pytest.FixtureRequest, all_awks: list[AwkImpl]
) -> None:
    failing = _failing(request.getfixturevalue(which), all_awks)
    for a in all_awks:
        assert failing.get(a.name, set()) == EXPECTED_FAILURES[which], a.name


@pytest.mark.parametrize("which", sorted(EXPECTED_FAILURES))
def test_every_awk_produces_identical_output(
    which: str, request: pytest.FixtureRequest, all_awks: list[AwkImpl]
) -> None:
    if len(all_awks) < 2:
        pytest.skip("only one awk implementation installed")
    by_scenario: dict[str, set[tuple[str, ...]]] = {}
    for r in run_all(list(SCENARIOS), request.getfixturevalue(which), all_awks):
        by_scenario.setdefault(r.scenario.id, set()).add(r.merged)
    assert {k: len(v) for k, v in by_scenario.items() if len(v) > 1} == {}
