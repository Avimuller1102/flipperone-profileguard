"""The shell test proposed for flipperos-btrfs-tools, run against each script in its own tree."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from profileguard import targets
from tests.conftest import PR4_FIXTURE

SH_TEST = Path(__file__).parents[2] / "upstream-proposal" / "tests" / "accountdb-merge.sh"
pytestmark = pytest.mark.skipif(shutil.which("sh") is None, reason="needs a POSIX sh")


def _run(script: Path, tmp_path: Path) -> subprocess.CompletedProcess[str]:
    (tmp_path / "libs").mkdir()
    (tmp_path / "tests").mkdir()
    shutil.copy(script, tmp_path / "libs" / "flipper-accountdb.awk")
    shutil.copy(SH_TEST, tmp_path / "tests" / SH_TEST.name)
    return subprocess.run(
        ["sh", str(tmp_path / "tests" / SH_TEST.name)], capture_output=True, text=True, timeout=60
    )


@pytest.mark.parametrize("which", ["snapshot", "pr4"])
def test_upstream_revisions_pass(which: str, tmp_path: Path) -> None:
    script = targets.snapshot().script if which == "snapshot" else PR4_FIXTURE
    proc = _run(script, tmp_path)
    assert proc.returncode == 0, proc.stdout
    assert proc.stdout.rstrip().endswith("all account merge checks ok")


def test_synthetic_defect_fails(tmp_path: Path) -> None:
    proc = _run(targets.synthetic_defect().script, tmp_path)
    assert proc.returncode == 1
    assert "FAIL owner password kept over a rebuilt factory one" in proc.stdout
    assert "FAIL locked account stays locked" in proc.stdout
