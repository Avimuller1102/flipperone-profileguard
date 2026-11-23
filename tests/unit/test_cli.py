from __future__ import annotations

import json
from pathlib import Path

import pytest

from profileguard.cli import main


def test_scenarios_lists_every_scenario(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["scenarios"]) == 0
    out = capsys.readouterr().out
    assert out.count("\n") == 13 and "AM-11" in out


def test_unknown_scenario_is_a_usage_error(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["test", "--scenario", "AM-99"]) == 2
    assert "unknown scenario" in capsys.readouterr().err


def test_missing_awk_is_a_usage_error(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["test", "--awk", "no-such-awk"]) == 2


def test_report_rejects_foreign_json(tmp_path: Path) -> None:
    bad = tmp_path / "x.json"
    bad.write_text(json.dumps({"schema": "something-else"}))
    assert main(["report", str(bad), "--html", str(tmp_path / "x.html")]) == 2
    assert main(["report", str(tmp_path / "missing.json"), "--html", "x.html"]) == 2
