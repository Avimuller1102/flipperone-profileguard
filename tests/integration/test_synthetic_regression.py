"""The required demonstration: a plausible one-line defect is caught, classified, reproducible."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from profileguard.cli import main
from tests.conftest import primary_awk

AWK = primary_awk().name


def test_correct_script_passes_owner_password_scenario() -> None:
    assert main(["test", "--target", "snapshot", "--awk", AWK, "--scenario", "AM-01"]) == 0


def test_synthetic_defect_is_detected(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    report_path = tmp_path / "defect.json"
    html_path = tmp_path / "defect.html"
    rc = main(
        [
            "test",
            "--target",
            "synthetic-defect",
            "--awk",
            AWK,
            "--json",
            str(report_path),
            "--html",
            str(html_path),
        ]
    )
    assert rc == 1
    report = json.loads(report_path.read_text())
    assert report["target"]["mode"] == "synthetic-fixture"
    assert report["target"]["upstream_code_executed"] is False
    am01 = next(r for r in report["results"] if r["scenario_id"] == "AM-01")
    assert am01["status"] == "FAIL"
    assert am01["classification"] == "contract-violation"
    assert "FAKE-SALT-BUILD-2" in am01["observed"][0]  # the factory hash came back
    assert am01["reproduce"] == (
        f"profileguard test --target synthetic-defect --awk {AWK} --scenario AM-01"
    )
    assert "AM-01" in html_path.read_text()
    assert "FAIL" in capsys.readouterr().out


def test_compare_isolates_exactly_what_the_defect_broke(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc = main(
        ["compare", "--baseline", "snapshot", "--candidate", "synthetic-defect", "--awk", AWK]
    )
    assert rc == 1
    out = capsys.readouterr().out
    regressed = sorted(
        line.split()[1] for line in out.splitlines() if line.split()[:1] == ["regressed"]
    )
    assert regressed == ["AM-01", "AM-04"]


def test_property_search_finds_the_defect_without_being_told_where() -> None:
    """Hypothesis, given only the header contract, has to find an input the defect breaks."""
    from hypothesis import find, settings
    from hypothesis import strategies as st

    from profileguard.targets import synthetic_defect
    from tests.property.test_merge_properties import check_header_contract, merged, side

    defect = synthetic_defect()

    def violates(bot: tuple[dict[str, str], dict[str, str], dict[str, str]]) -> bool:
        try:
            check_header_contract(*bot, merged(defect, *bot))
        except AssertionError:
            return True
        return False

    b, o, t = find(st.tuples(side, side, side), violates, settings=settings(database=None))
    # Shrunk to one account that both the new build and the profile changed.
    changed_both = [k for k in t if k in b and k in o and t[k] != b[k] and o[k] != b[k]]
    assert changed_both
