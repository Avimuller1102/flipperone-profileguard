"""Reports carry every field the schema requires, and validate() rejects broken ones."""

from __future__ import annotations

import copy
import json
from typing import Any

import pytest

from profileguard import reporting
from profileguard.merger import AwkImpl
from profileguard.runner import run_all
from profileguard.scenarios import SCENARIOS
from profileguard.targets import Target


@pytest.fixture
def report(snapshot: Target, awk: AwkImpl) -> dict[str, Any]:
    built = reporting.build_report(snapshot, [awk], run_all(list(SCENARIOS), snapshot, [awk]))
    loaded: dict[str, Any] = json.loads(json.dumps(built))
    return loaded


def test_report_is_valid(report: dict[str, Any]) -> None:
    assert reporting.validate(report) == []
    assert report["target"]["trust"] == "bundled"
    assert report["summary"]["contract_violations"] == 1
    assert report["summary"]["findings"] == 2


@pytest.mark.parametrize(
    ("breakage", "message"),
    [
        (lambda r: r.pop("results"), "missing 'results'"),
        (lambda r: r["results"].clear(), "empty"),
        (lambda r: r["results"][0].update(status="MAYBE"), "not one of"),
        (lambda r: r["summary"].update(PASS=999), "summary.PASS"),
        (lambda r: r["target"].update(trust="whatever"), "not one of"),
        (lambda r: r["results"].append(copy.deepcopy(r["results"][0])), "appears twice"),
        (lambda r: r.update(schema="other/1"), "must be"),
    ],
)
def test_broken_reports_are_rejected(report: dict[str, Any], breakage: Any, message: str) -> None:
    breakage(report)
    problems = reporting.validate(report)
    assert any(message in p for p in problems), problems


def test_html_is_self_contained(report: dict[str, Any]) -> None:
    page = reporting.html_report(report)
    assert "<script" not in page and "http://" not in page and "https://" not in page
