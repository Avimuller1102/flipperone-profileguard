"""Run scenarios against a target with one or more awk implementations."""

from __future__ import annotations

import shlex
from dataclasses import dataclass
from enum import StrEnum

from profileguard.merger import AwkImpl, MergeError, run_merge
from profileguard.scenarios import Basis, Scenario
from profileguard.targets import Target


class Status(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    ERROR = "ERROR"


@dataclass(frozen=True)
class Result:
    scenario: Scenario
    awk: AwkImpl
    target: Target
    status: Status
    failures: tuple[str, ...]
    merged: tuple[str, ...]
    error: str | None = None

    @property
    def classification(self) -> str:
        if self.status is Status.PASS:
            return "ok"
        if self.status is Status.ERROR:
            return "execution-error"
        return "contract-violation" if self.scenario.basis is Basis.CONTRACT else "finding"

    @property
    def counts_against_exit(self) -> bool:
        """Contract failures and errors fail a run; proposed-invariant findings do with --strict."""
        return self.status is Status.ERROR or (
            self.status is Status.FAIL and self.scenario.basis is Basis.CONTRACT
        )

    def reproduce(self) -> str:
        mode = self.target.mode.value
        if mode == "upstream-git":
            target = f"--repo PATH_TO_flipperos-btrfs-tools --target {self.target.commit}"
            if not self.target.reviewed_branch:
                target += " --allow-unmerged"
        elif mode == "upstream-snapshot":
            target = "--target snapshot"
        elif mode == "synthetic-fixture":
            target = "--target synthetic-defect"
        else:
            target = f"--target {shlex.quote(str(self.target.script))}"
        return f"profileguard test {target} --awk {self.awk.name} --scenario {self.scenario.id}"


def run_one(scenario: Scenario, target: Target, awk: AwkImpl) -> Result:
    try:
        merged = run_merge(
            awk, target.script, scenario.kind, scenario.base, scenario.new_base, scenario.profile
        )
    except MergeError as exc:
        return Result(scenario, awk, target, Status.ERROR, (), (), str(exc))
    failures = tuple(
        f"{check.describe()} -> observed: {observed}"
        for check in scenario.checks
        if (observed := check.evaluate(merged)) is not None
    )
    status = Status.FAIL if failures else Status.PASS
    return Result(scenario, awk, target, status, failures, merged.lines)


def run_all(scenarios: list[Scenario], target: Target, awks: list[AwkImpl]) -> list[Result]:
    return [run_one(s, target, a) for s in scenarios for a in awks]
