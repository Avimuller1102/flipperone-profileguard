"""The shell test proposed for flipperos-btrfs-tools, run in a tree laid out like upstream's.

Every shell and awk installed is tried, so the POSIX claim is checked, not assumed.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from profileguard import targets
from tests.conftest import PR4_FIXTURE

SH_TEST = Path(__file__).parents[2] / "upstream-proposal" / "tests" / "accountdb-merge.sh"
SHELLS = [s for s in ("sh", "dash", "bash", "busybox") if shutil.which(s)]
AWKS = [a for a in ("mawk", "gawk", "original-awk", "busybox", "awk") if shutil.which(a)]
pytestmark = pytest.mark.skipif(not SHELLS, reason="needs a POSIX sh")


def _tree(script: Path, tmp_path: Path) -> Path:
    (tmp_path / "libs").mkdir()
    (tmp_path / "tests").mkdir()
    shutil.copy(script, tmp_path / "libs" / "flipper-accountdb.awk")
    shutil.copy(SH_TEST, tmp_path / "tests" / SH_TEST.name)
    return tmp_path / "tests" / SH_TEST.name


def _awk_path(awk: str, tmp_path: Path) -> str:
    if awk != "busybox":
        return str(shutil.which(awk))
    link = tmp_path / "bb" / "awk"  # BusyBox picks the applet from argv[0]
    link.parent.mkdir()
    link.symlink_to(str(shutil.which("busybox")))
    return str(link)


def _run(test: Path, shell: str, awk: str) -> subprocess.CompletedProcess[str]:
    argv = ["busybox", "sh", str(test)] if shell == "busybox" else [shell, str(test)]
    env = {**os.environ, "AWK": awk}
    return subprocess.run(argv, capture_output=True, text=True, timeout=60, env=env)


@pytest.mark.parametrize("awk", AWKS)
@pytest.mark.parametrize("shell", SHELLS)
@pytest.mark.parametrize("which", ["snapshot", "pr4"])
def test_upstream_revisions_pass(which: str, shell: str, awk: str, tmp_path: Path) -> None:
    script = targets.snapshot().script if which == "snapshot" else PR4_FIXTURE
    proc = _run(_tree(script, tmp_path), shell, _awk_path(awk, tmp_path))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert proc.stdout.count("\nok ") + proc.stdout.startswith("ok ") == 12
    assert proc.stdout.rstrip().endswith("all account merge checks ok")


def test_synthetic_defect_fails(tmp_path: Path) -> None:
    proc = _run(_tree(targets.synthetic_defect().script, tmp_path), SHELLS[0], "awk")
    assert proc.returncode == 1
    assert "FAIL owner password kept over a rebuilt factory one" in proc.stdout
    assert "FAIL locked account stays locked" in proc.stdout


def test_missing_library_fails_cleanly(tmp_path: Path) -> None:
    (tmp_path / "tests").mkdir()
    test = tmp_path / "tests" / SH_TEST.name
    shutil.copy(SH_TEST, test)
    proc = _run(test, SHELLS[0], "awk")
    assert proc.returncode == 1 and "not found" in proc.stdout


def test_temporary_directory_is_removed(tmp_path: Path) -> None:
    tmp = tmp_path / "tmp"
    tmp.mkdir()
    test = _tree(targets.snapshot().script, tmp_path)
    env = {**os.environ, "TMPDIR": str(tmp)}
    subprocess.run([SHELLS[0], str(test)], capture_output=True, env=env, timeout=60, check=True)
    assert list(tmp.iterdir()) == []
