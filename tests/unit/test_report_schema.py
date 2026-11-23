"""The reports this tool writes carry every field docs/report-schema.json requires."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from profileguard import reporting
from profileguard.merger import AwkImpl
from profileguard.runner import run_all
from profileguard.scenarios import SCENARIOS
from profileguard.targets import Target

SCHEMA = json.loads((Path(__file__).parents[2] / "docs" / "report-schema.json").read_text())


def _require(obj: dict[str, Any], schema: dict[str, Any], where: str) -> None:
    for key in schema.get("required", []):
        assert key in obj, f"{where}: missing {key}"
    for key, sub in schema.get("properties", {}).items():
        if key not in obj:
            continue
        if "enum" in sub:
            assert obj[key] in sub["enum"], f"{where}.{key}={obj[key]!r}"
        if "const" in sub:
            assert obj[key] == sub["const"]
        if sub.get("type") == "object":
            _require(obj[key], sub, f"{where}.{key}")
        if sub.get("type") == "array" and "items" in sub:
            for i, item in enumerate(obj[key]):
                if isinstance(item, dict):
                    _require(item, sub["items"], f"{where}.{key}[{i}]")


def test_report_matches_schema(snapshot: Target, awk: AwkImpl) -> None:
    report = reporting.build_report(snapshot, [awk], run_all(list(SCENARIOS), snapshot, [awk]))
    _require(json.loads(json.dumps(report)), SCHEMA, "report")
    assert report["summary"]["contract_violations"] == 1
    assert report["summary"]["findings"] == 2


def test_html_is_self_contained(snapshot: Target, awk: AwkImpl) -> None:
    report = reporting.build_report(snapshot, [awk], run_all(list(SCENARIOS), snapshot, [awk]))
    page = reporting.html_report(report)
    assert "<script" not in page and "http://" not in page and "https://" not in page
