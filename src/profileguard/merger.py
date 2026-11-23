"""Run an account-merge awk script the way migrate-profile does, in a throwaway directory."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from profileguard.accountdb import AccountDb, DbKind

#: awk implementations worth comparing. Debian (and so the device image) installs mawk as awk;
#: gawk, BusyBox awk and the one-true-awk are what developers and recovery shells tend to have.
KNOWN_AWKS: tuple[str, ...] = ("mawk", "gawk", "busybox", "original-awk", "nawk", "awk")

TIMEOUT_SECONDS = 20


class MergeError(RuntimeError):
    """The awk process failed, timed out, or could not be started."""


@dataclass(frozen=True)
class AwkImpl:
    name: str
    argv: tuple[str, ...]
    version: str

    @property
    def sandboxed(self) -> bool:
        return "--sandbox" in self.argv


def _version_of(argv: list[str]) -> str:
    for flag in ("--version", "-W version", "-V", ""):
        try:
            proc = subprocess.run(
                [*argv, *flag.split()],  # bare: BusyBox prints its version in its banner
                capture_output=True,
                text=True,
                timeout=5,
                stdin=subprocess.DEVNULL,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        out = (proc.stdout or proc.stderr).strip().splitlines()
        if proc.returncode == 0 and out:
            return out[0][:120]
    return "unknown"


def find_awk(name: str) -> AwkImpl | None:
    """Locate one awk by name. gawk runs with --sandbox: no system(), no redirections."""
    path = shutil.which(name)
    if path is None:
        return None
    if name == "busybox":
        probe = subprocess.run(
            [path, "awk", "BEGIN{}"], capture_output=True, timeout=5, stdin=subprocess.DEVNULL
        )
        if probe.returncode != 0:
            return None
        return AwkImpl(name, (path, "awk"), _version_of([path]))
    argv: tuple[str, ...] = (path,)
    if name == "gawk":
        argv = (path, "--sandbox")
    return AwkImpl(name, argv, _version_of([path]))


def available_awks(names: tuple[str, ...] = KNOWN_AWKS) -> list[AwkImpl]:
    """Every distinct implementation found. A name that resolves to a binary already listed
    (``awk`` and ``nawk`` are usually symlinks to mawk or gawk) is dropped."""
    found: list[AwkImpl] = []
    seen_paths: set[str] = set()
    for name in names:
        impl = find_awk(name)
        if impl is None:
            continue
        real = str(Path(impl.argv[0]).resolve())
        key = real if name != "busybox" else f"{real} awk"
        if key in seen_paths:
            continue
        seen_paths.add(key)
        found.append(impl)
    return found


def run_merge(
    awk: AwkImpl,
    script: Path,
    kind: DbKind,
    base: AccountDb,
    new_base: AccountDb,
    profile: AccountDb,
) -> AccountDb:
    """Merge like ``awk -v LF=.. -f script base ours theirs`` in migrate-profile.

    ``base`` is the _stock the profile was made from, ``new_base`` the new build's copy being
    migrated onto (migrate-profile's dst, the awk script's "ours"), and ``profile`` the user's
    profile (src, "theirs"). Files are written under a private temporary directory only.
    """
    with tempfile.TemporaryDirectory(prefix="profileguard-") as tmp:
        tmpdir = Path(tmp)
        paths = []
        for name, db in (("base", base), ("ours", new_base), ("theirs", profile)):
            p = tmpdir / f"{name}.{kind.value}"
            p.write_text(db.render(), encoding="utf-8")
            paths.append(str(p))
        argv = [*awk.argv, "-v", f"LF={kind.lf_arg}", "-f", str(script), *paths]
        try:
            proc = subprocess.run(
                argv,
                capture_output=True,
                text=True,
                timeout=TIMEOUT_SECONDS,
                cwd=tmpdir,
                stdin=subprocess.DEVNULL,
                env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"},
            )
        except subprocess.TimeoutExpired as exc:
            raise MergeError(f"{awk.name} timed out after {TIMEOUT_SECONDS}s") from exc
        except OSError as exc:
            raise MergeError(f"could not start {awk.name}: {exc}") from exc
    if proc.returncode != 0:
        raise MergeError(f"{awk.name} exited {proc.returncode}: {proc.stderr.strip()[:500]}")
    return AccountDb.parse(proc.stdout)
