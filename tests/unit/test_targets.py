from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from profileguard import targets
from profileguard.scenarios import ACCOUNTDB
from tests.conftest import PR4_BLOB, PR4_FIXTURE

needs_git = pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")


def test_snapshot_is_the_recorded_upstream_blob() -> None:
    snap = targets.snapshot()
    assert snap.blob == targets.SNAPSHOT_BLOB
    assert snap.is_upstream_code and snap.commit == targets.SNAPSHOT_COMMIT


def test_pr4_fixture_is_the_recorded_upstream_blob() -> None:
    assert targets.git_blob_id(PR4_FIXTURE.read_bytes()) == PR4_BLOB


def test_synthetic_defect_is_not_reported_as_upstream_code() -> None:
    t = targets.synthetic_defect()
    assert t.mode is targets.Mode.SYNTHETIC
    assert t.provenance()["upstream_code_executed"] is False
    assert "SYNTHETIC DEFECT" in t.script.read_text()


@needs_git
def test_git_blob_id_matches_git(tmp_path: Path) -> None:
    f = tmp_path / "x"
    f.write_bytes(b"hello\n")
    out = subprocess.run(["git", "hash-object", str(f)], capture_output=True, text=True)
    assert targets.git_blob_id(b"hello\n") == out.stdout.strip()


def _git(repo: Path, *args: str) -> str:
    env = {
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.invalid",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.invalid",
        "PATH": "/usr/bin:/bin",
        "HOME": str(repo),
    }
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True, env=env
    ).stdout.strip()


@pytest.fixture
def upstream_like(tmp_path: Path) -> Path:
    """A clone whose origin/dev holds one commit, plus a local commit not on it."""
    origin = tmp_path / "origin"
    origin.mkdir()
    _git(origin, "init", "-q", "-b", "dev")
    (origin / "libs").mkdir()
    (origin / ACCOUNTDB).write_bytes(targets.snapshot().script.read_bytes())
    _git(origin, "add", ".")
    _git(origin, "commit", "-q", "-m", "base")
    clone = tmp_path / "clone"
    subprocess.run(["git", "clone", "-q", str(origin), str(clone)], check=True)
    _git(clone, "checkout", "-q", "-b", "feature")
    (clone / ACCOUNTDB).write_bytes(PR4_FIXTURE.read_bytes())
    _git(clone, "commit", "-q", "-am", "feature")
    return clone


@needs_git
def test_reviewed_revision_runs(upstream_like: Path, tmp_path: Path) -> None:
    t = targets.from_git(upstream_like, "origin/dev", tmp_path, allow_unmerged=False)
    assert t.mode is targets.Mode.UPSTREAM_GIT and t.reviewed_branch is True
    assert t.blob == targets.SNAPSHOT_BLOB


@needs_git
def test_unmerged_revision_needs_opt_in(upstream_like: Path, tmp_path: Path) -> None:
    with pytest.raises(targets.TargetError, match="not on the default branch"):
        targets.from_git(upstream_like, "feature", tmp_path, allow_unmerged=False)
    t = targets.from_git(upstream_like, "feature", tmp_path, allow_unmerged=True)
    assert t.reviewed_branch is False and t.blob == PR4_BLOB


@needs_git
def test_unknown_revision_and_non_repo_are_errors(upstream_like: Path, tmp_path: Path) -> None:
    with pytest.raises(targets.TargetError, match="no commit"):
        targets.from_git(upstream_like, "nope", tmp_path, allow_unmerged=True)
    plain = tmp_path / "plain"
    plain.mkdir()
    with pytest.raises(targets.TargetError, match="not a git repository"):
        targets.from_git(plain, "HEAD", tmp_path, allow_unmerged=True)


def test_resolve_rejects_bare_revision_without_repo(tmp_path: Path) -> None:
    with pytest.raises(targets.TargetError, match="--repo"):
        targets.resolve("origin/dev", None, tmp_path, allow_unmerged=False)
