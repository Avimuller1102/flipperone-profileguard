"""Run every scenario through the real upstream script and pin what it does today.

These are not wishes: they record the behaviour of the bundled dev snapshot and of PR #4, so a
change upstream shows up here as a failing expectation that has to be looked at and updated.
"""

from __future__ import annotations

import pytest

from profileguard.merger import AwkImpl
from profileguard.runner import Status, run_all
from profileguard.scenarios import SCENARIOS
from profileguard.targets import Target

DEV_FAILS = {"AM-10", "AM-11", "AM-13"}
PR4_FAILS = {"AM-11", "AM-12", "AM-13"}


def _failing(target: Target, awks: list[AwkImpl]) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for r in run_all(list(SCENARIOS), target, awks):
        assert r.status is not Status.ERROR, r.error
        if r.status is Status.FAIL:
            out.setdefault(r.awk.name, set()).add(r.scenario.id)
    return out


def test_dev_snapshot(snapshot: Target, all_awks: list[AwkImpl]) -> None:
    failing = _failing(snapshot, all_awks)
    for a in all_awks:
        assert failing.get(a.name, set()) == DEV_FAILS, a.name


def test_pr4(pr4: Target, all_awks: list[AwkImpl]) -> None:
    failing = _failing(pr4, all_awks)
    for a in all_awks:
        assert failing.get(a.name, set()) == PR4_FAILS, a.name


@pytest.mark.parametrize("which", ["snapshot", "pr4"])
def test_every_awk_produces_identical_output(
    which: str, snapshot: Target, pr4: Target, all_awks: list[AwkImpl]
) -> None:
    if len(all_awks) < 2:
        pytest.skip("only one awk implementation installed")
    target = snapshot if which == "snapshot" else pr4
    by_scenario: dict[str, set[tuple[str, ...]]] = {}
    for r in run_all(list(SCENARIOS), target, all_awks):
        by_scenario.setdefault(r.scenario.id, set()).add(r.merged)
    assert {k: len(v) for k, v in by_scenario.items() if len(v) > 1} == {}
