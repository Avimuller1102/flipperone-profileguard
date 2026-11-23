"""What the process limits around awk do and do not do. Not a sandbox; see ARCHITECTURE.md."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from profileguard import merger
from profileguard.accountdb import AccountDb, DbKind
from profileguard.merger import AwkImpl, MergeError, find_awk, run_merge

posix_only = pytest.mark.skipif(sys.platform == "win32", reason="resource limits need POSIX")
DB = AccountDb.of("root:x:0:0::/root:/bin/sh")


def _script(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "s.awk"
    p.write_text(body)
    return p


def _merge(awk: AwkImpl, script: Path) -> AccountDb:
    return run_merge(awk, script, DbKind.PASSWD, DB, DB, DB)


@posix_only
def test_cpu_limit_stops_an_endless_loop(
    tmp_path: Path, awk: AwkImpl, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(merger, "CPU_SECONDS", 1)
    with pytest.raises(MergeError):
        _merge(awk, _script(tmp_path, "BEGIN { while (1) x++ }\n"))


@posix_only
def test_output_limit_stops_a_flood(
    tmp_path: Path, awk: AwkImpl, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(merger, "OUTPUT_LIMIT_BYTES", 64 * 1024)
    with pytest.raises(MergeError):
        _merge(awk, _script(tmp_path, 'BEGIN { while (1) print "xxxxxxxxxxxxxxxxxxxxxxxx" }\n'))


def test_gawk_sandbox_refuses_system(tmp_path: Path) -> None:
    gawk = find_awk("gawk")
    if gawk is None:
        pytest.skip("gawk not installed")
    marker = tmp_path / "ran"
    script = _script(tmp_path, f'BEGIN {{ system("touch {marker}") }}\n')
    with pytest.raises(MergeError, match="exited"):
        _merge(gawk, script)
    assert not marker.exists()


def test_gawk_sandbox_refuses_writing_files(tmp_path: Path) -> None:
    gawk = find_awk("gawk")
    if gawk is None:
        pytest.skip("gawk not installed")
    target = tmp_path / "written"
    with pytest.raises(MergeError):
        _merge(gawk, _script(tmp_path, f'BEGIN {{ print "x" > "{target}" }}\n'))
    assert not target.exists()


def test_unsandboxed_awk_is_not_contained(tmp_path: Path, awk: AwkImpl) -> None:
    """Documents the limit: without --sandbox, awk can run commands. That is why unreviewed code
    is refused on these awks unless --allow-unsandboxed-awk is given."""
    if awk.sandboxed:
        pytest.skip("primary awk is sandboxed")
    marker = tmp_path / "ran"
    _merge(awk, _script(tmp_path, f'BEGIN {{ system("touch {marker}") }}\n'))
    assert marker.exists()
