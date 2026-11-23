"""Which awk script a run executes, and where it came from.

A target is one of:

* ``snapshot``           the copy of upstream's script bundled with this package
* ``synthetic-defect``   a deliberately broken copy, to show that the checks catch a regression
* ``REF``                a git revision of a local flipperos-btrfs-tools checkout (``--repo``)
* a path to an ``.awk`` file
"""

from __future__ import annotations

import hashlib
import subprocess
import tempfile
from dataclasses import dataclass
from enum import StrEnum
from importlib import resources
from pathlib import Path

from profileguard.scenarios import ACCOUNTDB

#: Provenance of the bundled snapshot. Verified by `profileguard doctor` and the test suite.
SNAPSHOT_REPO = "https://github.com/flipperdevices/flipperos-btrfs-tools"
SNAPSHOT_BRANCH = "dev"
SNAPSHOT_COMMIT = "bb92d87252807ee306c90e9c853b8a9af84a493f"
SNAPSHOT_BLOB = "0533182f2d87de6d350dd45f22573122ace6e087"


class Mode(StrEnum):
    UPSTREAM_GIT = "upstream-git"
    UPSTREAM_SNAPSHOT = "upstream-snapshot"
    SYNTHETIC = "synthetic-fixture"
    EXTERNAL_FILE = "external-file"


class TargetError(RuntimeError):
    pass


@dataclass(frozen=True)
class Target:
    label: str
    mode: Mode
    script: Path
    blob: str
    commit: str | None = None
    repo: str | None = None
    reviewed_branch: bool | None = None

    @property
    def is_upstream_code(self) -> bool:
        return self.mode in (Mode.UPSTREAM_GIT, Mode.UPSTREAM_SNAPSHOT)

    def provenance(self) -> dict[str, object]:
        return {
            "label": self.label,
            "mode": self.mode.value,
            "upstream_code_executed": self.is_upstream_code,
            "script_path": ACCOUNTDB if self.is_upstream_code else str(self.script),
            "git_blob": self.blob,
            "commit": self.commit,
            "repository": self.repo,
            "on_default_branch": self.reviewed_branch,
        }


def git_blob_id(data: bytes) -> str:
    """The id git gives a blob with these bytes, so a file can be matched to an upstream commit."""
    return hashlib.sha1(b"blob %d\0" % len(data) + data, usedforsecurity=False).hexdigest()


def _package_file(*parts: str) -> Path:
    ref = resources.files("profileguard").joinpath(*parts)
    path = Path(str(ref))
    if not path.is_file():
        raise TargetError(f"bundled file missing: {'/'.join(parts)}")
    return path


def snapshot() -> Target:
    path = _package_file("upstream_snapshot", "flipper-accountdb.awk")
    return Target(
        label=f"snapshot:{SNAPSHOT_BRANCH}@{SNAPSHOT_COMMIT[:7]}",
        mode=Mode.UPSTREAM_SNAPSHOT,
        script=path,
        blob=git_blob_id(path.read_bytes()),
        commit=SNAPSHOT_COMMIT,
        repo=SNAPSHOT_REPO,
        reviewed_branch=True,
    )


def synthetic_defect() -> Target:
    path = _package_file("fixtures", "synthetic-defect-accountdb.awk")
    return Target(
        label="synthetic-defect",
        mode=Mode.SYNTHETIC,
        script=path,
        blob=git_blob_id(path.read_bytes()),
    )


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, timeout=60, stdin=subprocess.DEVNULL
    )


def _default_branch_tips(repo: Path) -> list[str]:
    """Remote-tracking default branches: origin/HEAD if set, else origin/dev and origin/main."""
    head = _git(repo, "symbolic-ref", "-q", "refs/remotes/origin/HEAD")
    if head.returncode == 0:
        return [head.stdout.decode().strip()]
    return [
        r
        for r in ("refs/remotes/origin/dev", "refs/remotes/origin/main")
        if _git(repo, "rev-parse", "-q", "--verify", r).returncode == 0
    ]


def from_git(repo: Path, ref: str, workdir: Path, allow_unmerged: bool) -> Target:
    """Extract the script at ``ref`` without checking anything out.

    A revision that is not on the remote default branch (an unmerged PR, say) is code nobody at
    upstream has accepted yet; it only runs with ``allow_unmerged``.
    """
    if _git(repo, "rev-parse", "--git-dir").returncode != 0:
        raise TargetError(f"{repo} is not a git repository")
    rev = _git(repo, "rev-parse", "--verify", "-q", f"{ref}^{{commit}}")
    if rev.returncode != 0:
        raise TargetError(f"no commit '{ref}' in {repo}")
    commit = rev.stdout.decode().strip()
    tips = _default_branch_tips(repo)
    on_default = any(
        _git(repo, "merge-base", "--is-ancestor", commit, tip).returncode == 0 for tip in tips
    )
    if not on_default and not allow_unmerged:
        where = ", ".join(tips) or "no remote default branch found"
        raise TargetError(
            f"'{ref}' ({commit[:12]}) is not on the default branch ({where}). Read the script "
            f"first (git -C {repo} show {commit[:12]}:{ACCOUNTDB}), then pass --allow-unmerged."
        )
    blob = _git(repo, "show", f"{commit}:{ACCOUNTDB}")
    if blob.returncode != 0:
        raise TargetError(f"{ACCOUNTDB} does not exist at {commit[:12]}")
    out = workdir / f"accountdb-{commit[:12]}.awk"
    out.write_bytes(blob.stdout)
    origin = _git(repo, "remote", "get-url", "origin")
    return Target(
        label=f"{ref}@{commit[:7]}",
        mode=Mode.UPSTREAM_GIT,
        script=out,
        blob=git_blob_id(blob.stdout),
        commit=commit,
        repo=origin.stdout.decode().strip() if origin.returncode == 0 else str(repo),
        reviewed_branch=on_default,
    )


def from_file(path: Path) -> Target:
    if not path.is_file():
        raise TargetError(f"no such file: {path}")
    data = path.read_bytes()
    return Target(label=path.name, mode=Mode.EXTERNAL_FILE, script=path, blob=git_blob_id(data))


def resolve(spec: str, repo: Path | None, workdir: Path, allow_unmerged: bool) -> Target:
    if spec == "snapshot":
        return snapshot()
    if spec == "synthetic-defect":
        return synthetic_defect()
    if repo is not None:
        return from_git(repo, spec, workdir, allow_unmerged)
    if spec.endswith(".awk") or Path(spec).is_file():
        return from_file(Path(spec))
    raise TargetError(
        f"'{spec}' is not 'snapshot', 'synthetic-defect' or a file; to use a git revision, "
        "also pass --repo PATH_TO_flipperos-btrfs-tools"
    )


def new_workdir() -> tempfile.TemporaryDirectory[str]:
    return tempfile.TemporaryDirectory(prefix="profileguard-target-")
