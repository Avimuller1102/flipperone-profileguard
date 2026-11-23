from __future__ import annotations

import json
from pathlib import Path

import pytest

from profileguard.cli import main
from tests.conftest import primary_awk


def test_scenarios_lists_every_scenario(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["scenarios"]) == 0
    out = capsys.readouterr().out
    assert out.count("\n") == 13 and "AM-11" in out


def test_unknown_scenario_is_a_usage_error(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["test", "--scenario", "AM-99"]) == 2
    assert "unknown scenario" in capsys.readouterr().err


def test_missing_awk_is_a_usage_error() -> None:
    assert main(["test", "--awk", "no-such-awk"]) == 2


def test_doctor_require_reports_missing_dependency() -> None:
    assert main(["doctor", "--require", primary_awk().name]) == 0
    assert main(["doctor", "--require", "no-such-awk"]) == 2


def test_expect_fail_must_match_exactly(capsys: pytest.CaptureFixture[str]) -> None:
    awk = primary_awk().name
    base = ["test", "--awk", awk]
    known = ["--expect-fail", "AM-10", "--expect-fail", "AM-11", "--expect-fail", "AM-13"]
    assert main([*base, *known]) == 0
    assert main([*base, "--expect-fail", "AM-10", "--expect-fail", "AM-11"]) == 1
    assert "AM-13 failed but was not expected to" in capsys.readouterr().out
    assert main([*base, "--expect-fail", "AM-10,AM-11,AM-13"]) == 0
    assert main([*base, *known, "--expect-fail", "AM-01"]) == 1
    assert "AM-01 was expected to fail but passed" in capsys.readouterr().out


def test_local_script_is_refused_without_opt_in(tmp_path: Path) -> None:
    script = tmp_path / "x.awk"
    script.write_text("{ print }\n")
    assert main(["test", "--target", str(script)]) == 2


def test_unreviewed_script_is_refused_on_unsandboxed_awk(tmp_path: Path) -> None:
    awk = primary_awk()
    if awk.sandboxed:
        pytest.skip("primary awk is sandboxed")
    script = tmp_path / "x.awk"
    script.write_text("{ print }\n")
    args = ["test", "--target", str(script), "--allow-unreviewed", "--awk", awk.name]
    assert main(args) == 2
    assert main([*args, "--allow-unsandboxed-awk"]) == 1  # prints its input: checks fail


def test_execution_error_has_its_own_exit_code(tmp_path: Path) -> None:
    script = tmp_path / "broken.awk"
    script.write_text("this is not awk {{{\n")
    awk = primary_awk().name
    args = ["test", "--target", str(script), "--allow-unreviewed", "--allow-unsandboxed-awk"]
    assert main([*args, "--awk", awk, "--scenario", "AM-01"]) == 3


def test_report_validates_and_renders(tmp_path: Path) -> None:
    out = tmp_path / "r.json"
    assert main(["test", "--awk", primary_awk().name, "--json", str(out)]) == 1
    assert main(["report", str(out)]) == 0
    assert main(["report", str(out), "--html", str(tmp_path / "r.html")]) == 0
    assert (tmp_path / "r.html").stat().st_size > 1000


def test_report_rejects_foreign_or_missing_json(tmp_path: Path) -> None:
    bad = tmp_path / "x.json"
    bad.write_text(json.dumps({"schema": "something-else"}))
    assert main(["report", str(bad), "--html", str(tmp_path / "x.html")]) == 2
    assert main(["report", str(tmp_path / "missing.json")]) == 2
