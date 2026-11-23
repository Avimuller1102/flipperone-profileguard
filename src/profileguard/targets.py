"""Which awk script a run executes, where it came from, and how far it is trusted.

A target is one of:

* ``snapshot``           the copy of upstream's script bundled with this package
* ``synthetic-defect``   a deliberately broken copy, to show that the checks catch a regression
* ``REF``                a git revision of a local flipperos-btrfs-tools clone (``--repo``)
* a path to an ``.awk`` file

Trust levels (see docs/ARCHITECTURE.md, "Trust boundaries"):

* ``bundled``          shipped in this package; its git blob id is checked before every run
* ``upstream-merged``  a commit on the default branch of the official upstream repository
* ``unreviewed``       anything else: an unmerged pull request, a fork, a local file. It runs only
                       with ``--allow-unreviewed``, and only under ``gawk --sandbox`` unless
                       ``--allow-unsandboxed-awk`` is also given.

None of this is a sandbox. awk runs as the invoking user; see merger.py for what limits apply.
"""

from __future__ import annotations

import hashlib
import re
import subprocess
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from importlib import resources
from pathlib import Path

from profileguard.merger import AwkImpl
from profileguard.scenarios import ACCOUNTDB

#: Provenance of the bundled snapshot. Checked before each run and by `profileguard doctor`.
SNAPSHOT_REPO = "https://github.com/flipperdevices/flipperos-btrfs-tools"
SNAPSHOT_BRANCH = "dev"
SNAPSHOT_COMMIT = "8c9ffc779501da67009b77ccc0bca338549a2929"
SNAPSHOT_BLOB = "fae7452c04333de1fabcca98b7e9e20504666913"
SYNTHETIC_BLOB = "8fc5717cd06f4eddd32f5afba0c7015e60c29675"

_OFFICIAL_REMOTE = re.compile(
    r"^(?:https://github\.com/|ssh://git@github\.com/|git@github\.com:)"
    r"flipperdevices/flipperos-btrfs-tools(?:\.git)?/?$",
    re.IGNORECASE,
)

# Repository-local git settings that could run a program on an otherwise read-only command.
_GIT_HARDENING = ("-c", "core.fsmonitor=false", "-c", "core.hooksPath=/dev/null")


class Mode(StrEnum):
    UPSTREAM_GIT = "upstream-git"
    UPSTREAM_SNAPSHOT = "upstream-snapshot"
    SYNTHETIC = "synthetic-fixture"
    EXTERNAL_FILE = "external-file"


class Trust(StrEnum):
    BUNDLED = "bundled"
    UPSTREAM_MERGED = "upstream-merged"
    UNREVIEWED = "unreviewed"


class TargetError(RuntimeError):
    pass


@dataclass(frozen=True)
class Target:
    label: str
    mode: Mode
    trust: Trust
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
            "trust": self.trust.value,
            "upstream_code_executed": self.is_upstream_code,
            "script_path": ACCOUNTDB if self.is_upstream_code else self.script.name,
            "git_blob": self.blob,
            "commit": self.commit,
            "repository": self.repo,
            "on_default_branch": self.reviewed_branch,
        }


def git_blob_id(data: bytes) -> str:
    """The id git gives a blob with these bytes, so a file can be matched to an upstream commit."""
    return hashlib.sha1(b"blob %d\0" % len(data) + data, usedforsecurity=False).hexdigest()


def is_official_remote(url: str) -> bool:
    return bool(_OFFICIAL_REMOTE.match(url.strip()))


def _bundled(parts: tuple[str, ...], expected_blob: str) -> tuple[Path, str]:
    """A file shipped with the package, refused if it is not byte-for-byte what was released."""
    path = Path(str(resources.files("profileguard").joinpath(*parts)))
    if not path.is_file():
        raise TargetError(f"bundled file missing: {'/'.join(parts)}")
    blob = git_blob_id(path.read_bytes())
    if blob != expected_blob:
        raise TargetError(
            f"bundled file {'/'.join(parts)} has blob {blob}, expected {expected_blob}; "
            "the installation was modified, reinstall profileguard"
        )
    return path, blob


def snapshot() -> Target:
    path, blob = _bundled(("upstream_snapshot", "flipper-accountdb.awk"), SNAPSHOT_BLOB)
    return Target(
        label=f"snapshot:{SNAPSHOT_BRANCH}@{SNAPSHOT_COMMIT[:7]}",
        mode=Mode.UPSTREAM_SNAPSHOT,
        trust=Trust.BUNDLED,
        script=path,
        blob=blob,
        commit=SNAPSHOT_COMMIT,
        repo=SNAPSHOT_REPO,
        reviewed_branch=True,
    )


def synthetic_defect() -> Target:
    path, blob = _bundled(("fixtures", "synthetic-defect-accountdb.awk"), SYNTHETIC_BLOB)
    return Target(
        label="synthetic-defect", mode=Mode.SYNTHETIC, trust=Trust.BUNDLED, script=path, blob=blob
    )


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", *_GIT_HARDENING, "-C", str(repo), *args],
        capture_output=True,
        timeout=60,
        stdin=subprocess.DEVNULL,
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


def from_git(repo: Path, ref: str, workdir: Path, allow_unreviewed: bool) -> Target:
    """Extract the script at ``ref`` with ``git show``; nothing is checked out or built.

    Only a commit on the default branch of a clone whose origin is the official repository counts
    as merged upstream code. That decision rests on the clone's own remote-tracking refs, which
    whoever controls the clone can change: use a clone you made yourself.
    """
    if _git(repo, "rev-parse", "--git-dir").returncode != 0:
        raise TargetError(f"{repo} is not a git repository")
    rev = _git(repo, "rev-parse", "--verify", "-q", f"{ref}^{{commit}}")
    if rev.returncode != 0:
        raise TargetError(f"no commit '{ref}' in {repo}")
    commit = rev.stdout.decode().strip()
    origin = _git(repo, "remote", "get-url", "origin")
    origin_url = origin.stdout.decode().strip() if origin.returncode == 0 else ""
    official = is_official_remote(origin_url)
    tips = _default_branch_tips(repo) if official else []
    on_default = any(
        _git(repo, "merge-base", "--is-ancestor", commit, tip).returncode == 0 for tip in tips
    )
    if not on_default and not allow_unreviewed:
        why = (
            f"is not on the default branch ({', '.join(tips) or 'none found'})"
            if official
            else f"comes from a clone whose origin is not {SNAPSHOT_REPO} ({origin_url or 'none'})"
        )
        raise TargetError(
            f"'{ref}' ({commit[:12]}) {why}, so it is unreviewed code. Read it first "
            f"(git -C {repo} show {commit[:12]}:{ACCOUNTDB}), then pass --allow-unreviewed."
        )
    blob = _git(repo, "show", f"{commit}:{ACCOUNTDB}")
    if blob.returncode != 0:
        raise TargetError(f"{ACCOUNTDB} does not exist at {commit[:12]}")
    out = workdir / f"accountdb-{commit[:12]}.awk"
    out.write_bytes(blob.stdout)
    return Target(
        label=f"{ref}@{commit[:7]}",
        mode=Mode.UPSTREAM_GIT,
        trust=Trust.UPSTREAM_MERGED if on_default else Trust.UNREVIEWED,
        script=out,
        blob=git_blob_id(blob.stdout),
        commit=commit,
        repo=origin_url or str(repo),
        reviewed_branch=on_default,
    )


def from_file(path: Path, allow_unreviewed: bool) -> Target:
    # Absolute: awk runs from a private temporary directory, where a relative path means nothing.
    path = path.resolve()
    if not path.is_file():
        raise TargetError(f"no such file: {path}")
    if not allow_unreviewed:
        raise TargetError(
            f"{path} is a local file, so it is unreviewed code. Read it first, then pass "
            "--allow-unreviewed."
        )
    data = path.read_bytes()
    return Target(
        label=path.name,
        mode=Mode.EXTERNAL_FILE,
        trust=Trust.UNREVIEWED,
        script=path,
        blob=git_blob_id(data),
    )


def resolve(spec: str, repo: Path | None, workdir: Path, allow_unreviewed: bool) -> Target:
    if spec == "snapshot":
        return snapshot()
    if spec == "synthetic-defect":
        return synthetic_defect()
    if repo is not None:
        return from_git(repo, spec, workdir, allow_unreviewed)
    if spec.endswith(".awk") or Path(spec).is_file():
        return from_file(Path(spec), allow_unreviewed)
    raise TargetError(
        f"'{spec}' is not 'snapshot', 'synthetic-defect' or a file; to use a git revision, "
        "also pass --repo PATH_TO_flipperos-btrfs-tools"
    )


def check_execution_policy(
    target: Target, awks: Sequence[AwkImpl], allow_unsandboxed: bool
) -> None:
    """Unreviewed code runs only where awk itself refuses system(), pipes and redirections."""
    if target.trust is not Trust.UNREVIEWED or allow_unsandboxed:
        return
    unsandboxed = [a.name for a in awks if not a.sandboxed]
    if unsandboxed:
        raise TargetError(
            f"{target.label} is unreviewed code and {', '.join(unsandboxed)} cannot stop it from "
            "running commands (system(), pipes) or writing files. Use --awk gawk, which runs "
            "with --sandbox, or pass --allow-unsandboxed-awk after reading the script."
        )


def new_workdir() -> tempfile.TemporaryDirectory[str]:
    return tempfile.TemporaryDirectory(prefix="profileguard-target-")
