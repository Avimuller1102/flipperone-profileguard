"""Run the same scenarios on two targets and classify every difference."""

from __future__ import annotations

from dataclasses import dataclass

from profileguard.runner import Result, Status
from profileguard.scenarios import Basis


@dataclass(frozen=True)
class Delta:
    scenario_id: str
    awk: str
    basis: Basis
    baseline: Result
    candidate: Result

    @property
    def change(self) -> str:
        b, c = self.baseline.status, self.candidate.status
        contract = self.basis is Basis.CONTRACT
        if b is c:
            if b is Status.PASS and self.baseline.merged != self.candidate.merged:
                return "output-changed"
            return "unchanged"
        if c is Status.PASS:
            return "fixed" if contract else "now-holds"
        if b is Status.PASS:
            return "regressed" if contract else "behaviour-change"
        return "changed"

    @property
    def is_regression(self) -> bool:
        return self.change == "regressed" or (
            self.basis is Basis.CONTRACT
            and self.candidate.status is Status.ERROR
            and self.baseline.status is not Status.ERROR
        )


def compare(baseline: list[Result], candidate: list[Result]) -> list[Delta]:
    cand = {(r.scenario.id, r.awk.name): r for r in candidate}
    out = []
    for b in baseline:
        c = cand.get((b.scenario.id, b.awk.name))
        if c is not None:
            out.append(Delta(b.scenario.id, b.awk.name, b.scenario.basis, b, c))
    return out


def render(deltas: list[Delta], baseline_label: str, candidate_label: str) -> str:
    lines = [f"baseline:  {baseline_label}", f"candidate: {candidate_label}", ""]
    lines.append(f"{'change':<17} {'id':<6} {'awk':<13} {'basis':<9} baseline -> candidate")
    for d in deltas:
        if d.change == "unchanged":
            continue
        lines.append(
            f"{d.change:<17} {d.scenario_id:<6} {d.awk:<13} {d.basis.value:<9} "
            f"{d.baseline.status.value} -> {d.candidate.status.value}"
        )
        for f in d.candidate.failures:
            lines.append(f"{'':<17} candidate: {f}")
    counts: dict[str, int] = {}
    for d in deltas:
        counts[d.change] = counts.get(d.change, 0) + 1
    lines.append("")
    lines.append(", ".join(f"{k}: {v}" for k, v in sorted(counts.items())))
    return "\n".join(lines)
