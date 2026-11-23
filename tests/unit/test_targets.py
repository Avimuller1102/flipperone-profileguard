from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from profileguard import targets
from profileguard.merger import AwkImpl
from profileguard.scenarios import ACCOUNTDB
from tests.conftest import OLD_DEV_BLOB, OLD_DEV_FIXTURE, PR4_BLOB, PR4_FIXTURE

needs_git = pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")


def test_snapshot_is_the_recorded_upstream_blob() -> None:
    snap = targets.snapshot()
    assert snap.blob == targets.SNAPSHOT_BLOB
    assert snap.trust is targets.Trust.BUNDLED
    assert snap.is_upstream_code and snap.commit == targets.SNAPSHOT_COMMIT


def test_modified_bundled_file_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(targets, "SNAPSHOT_BLOB", "0" * 40)
    with pytest.raises(targets.TargetError, match="installation was modified"):
        targets.snapshot()
    monkeypatch.setattr(targets, "SYNTHETIC_BLOB", "0" * 40)
    with pytest.raises(targets.TargetError, match="installation was modified"):
        targets.synthetic_defect()


def test_fixtures_are_the_recorded_upstream_blobs() -> None:
    assert targets.git_blob_id(PR4_FIXTURE.read_bytes()) == PR4_BLOB
    assert targets.git_blob_id(OLD_DEV_FIXTURE.read_bytes()) == OLD_DEV_BLOB


def test_synthetic_defect_is_not_reported_as_upstream_code() -> None:
    t = targets.synthetic_defect()
    assert t.mode is targets.Mode.SYNTHETIC
    assert t.provenance()["upstream_code_executed"] is False
    assert "SYNTHETIC DEFECT" in t.script.read_text()


@pytest.mark.parametrize(
    ("url", "official"),
    [
        ("https://github.com/flipperdevices/flipperos-btrfs-tools", True),
        ("https://github.com/flipperdevices/flipperos-btrfs-tools.git", True),
        ("git@github.com:flipperdevices/flipperos-btrfs-tools.git", True),
        ("ssh://git@github.com/flipperdevices/flipperos-btrfs-tools", True),
        ("https://github.com/someone/flipperos-btrfs-tools", False),
        ("https://github.com/flipperdevices/flipperos-btrfs-tools-evil", False),
        ("https://evil.example/flipperdevices/flipperos-btrfs-tools", False),
        ("/tmp/origin", False),
        ("", False),
    ],
)
def test_official_remote(url: str, official: bool) -> None:
    assert targets.is_official_remote(url) is official


def test_local_file_needs_opt_in(tmp_path: Path) -> None:
    f = tmp_path / "x.awk"
    f.write_text("{ print }\n")
    with pytest.raises(targets.TargetError, match="unreviewed"):
        targets.resolve(str(f), None, tmp_path, allow_unreviewed=False)
    t = targets.resolve(str(f), None, tmp_path, allow_unreviewed=True)
    assert t.trust is targets.Trust.UNREVIEWED
    assert t.provenance()["script_path"] == "x.awk"  # no local absolute path in reports


def test_relative_script_path_still_runs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from profileguard.accountdb import AccountDb, DbKind
    from profileguard.merger import run_merge
    from tests.conftest import primary_awk

    (tmp_path / "x.awk").write_text("{ print }\n")
    monkeypatch.chdir(tmp_path)
    t = targets.from_file(Path("x.awk"), allow_unreviewed=True)
    assert t.script.is_absolute()
    db = AccountDb.of("root:x")
    out = run_merge(primary_awk(), t.script, DbKind.PASSWD, db, db, db)
    assert out.lines == ("root:x",) * 3


def _awk(name: str, sandboxed: bool) -> AwkImpl:
    argv = ("/usr/bin/gawk", "--sandbox") if sandboxed else (f"/usr/bin/{name}",)
    return AwkImpl(name, argv, "test")


def test_unreviewed_code_runs_only_sandboxed(tmp_path: Path) -> None:
    f = tmp_path / "x.awk"
    f.write_text("{ print }\n")
    t = targets.from_file(f, allow_unreviewed=True)
    targets.check_execution_policy(t, [_awk("gawk", True)], allow_unsandboxed=False)
    with pytest.raises(targets.TargetError, match="mawk cannot stop it"):
        targets.check_execution_policy(
            t, [_awk("gawk", True), _awk("mawk", False)], allow_unsandboxed=False
        )
    targets.check_execution_policy(t, [_awk("mawk", False)], allow_unsandboxed=True)


def test_trusted_code_runs_on_every_awk() -> None:
    for t in (targets.snapshot(), targets.synthetic_defect()):
        targets.check_execution_policy(t, [_awk("mawk", False)], allow_unsandboxed=False)


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
        "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
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
def test_default_branch_of_an_unofficial_clone_is_unreviewed(
    upstream_like: Path, tmp_path: Path
) -> None:
    with pytest.raises(targets.TargetError, match="origin is not"):
        targets.from_git(upstream_like, "origin/dev", tmp_path, allow_unreviewed=False)


@needs_git
def test_merged_revision_of_the_official_repo_runs(
    upstream_like: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(targets, "is_official_remote", lambda url: True)
    t = targets.from_git(upstream_like, "origin/dev", tmp_path, allow_unreviewed=False)
    assert t.mode is targets.Mode.UPSTREAM_GIT and t.trust is targets.Trust.UPSTREAM_MERGED
    assert t.blob == targets.SNAPSHOT_BLOB


@needs_git
def test_unmerged_revision_needs_opt_in(
    upstream_like: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(targets, "is_official_remote", lambda url: True)
    with pytest.raises(targets.TargetError, match="not on the default branch"):
        targets.from_git(upstream_like, "feature", tmp_path, allow_unreviewed=False)
    t = targets.from_git(upstream_like, "feature", tmp_path, allow_unreviewed=True)
    assert t.trust is targets.Trust.UNREVIEWED and t.blob == PR4_BLOB


@needs_git
def test_unknown_revision_and_non_repo_are_errors(upstream_like: Path, tmp_path: Path) -> None:
    with pytest.raises(targets.TargetError, match="no commit"):
        targets.from_git(upstream_like, "nope", tmp_path, allow_unreviewed=True)
    plain = tmp_path / "plain"
    plain.mkdir()
    with pytest.raises(targets.TargetError, match="not a git repository"):
        targets.from_git(plain, "HEAD", tmp_path, allow_unreviewed=True)


def test_resolve_rejects_bare_revision_without_repo(tmp_path: Path) -> None:
    with pytest.raises(targets.TargetError, match="--repo"):
        targets.resolve("origin/dev", None, tmp_path, allow_unreviewed=False)
