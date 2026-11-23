"""Run an account-merge awk script the way migrate-profile does, in a throwaway directory."""

from __future__ import annotations

import contextlib
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
CPU_SECONDS = 10
OUTPUT_LIMIT_BYTES = 8 * 1024 * 1024
MEMORY_LIMIT_BYTES = 1024 * 1024 * 1024

try:
    import resource

    _HAVE_RESOURCE = True
except ImportError:  # Windows
    _HAVE_RESOURCE = False


def _limit_resources() -> None:
    """Run in the child before exec: bound CPU, file size (stdout is a file), memory and cores.

    These limit damage from a runaway script; they do not stop a script from reading files or
    starting programs. Limits the platform refuses (RLIMIT_AS on macOS) are skipped.
    """
    for name, value in (
        ("RLIMIT_CPU", CPU_SECONDS),
        ("RLIMIT_FSIZE", OUTPUT_LIMIT_BYTES),
        ("RLIMIT_AS", MEMORY_LIMIT_BYTES),
        ("RLIMIT_CORE", 0),
    ):
        limit = getattr(resource, name, None)
        if limit is None:
            continue
        with contextlib.suppress(ValueError, OSError):
            resource.setrlimit(limit, (value, value))


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
    profile (src, "theirs"). Inputs and outputs live in a private temporary directory, the child
    gets a minimal environment, a timeout and resource limits. This is containment of mistakes,
    not a sandbox: awk runs as the invoking user and can read whatever that user can.
    """
    with tempfile.TemporaryDirectory(prefix="profileguard-") as tmp:
        tmpdir = Path(tmp)
        paths = []
        for name, db in (("base", base), ("ours", new_base), ("theirs", profile)):
            p = tmpdir / f"{name}.{kind.value}"
            p.write_text(db.render(), encoding="utf-8")
            paths.append(str(p))
        argv = [*awk.argv, "-v", f"LF={kind.lf_arg}", "-f", str(script), *paths]
        out_path, err_path = tmpdir / "stdout", tmpdir / "stderr"
        try:
            with out_path.open("wb") as out, err_path.open("wb") as err:
                proc = subprocess.run(
                    argv,
                    stdout=out,
                    stderr=err,
                    timeout=TIMEOUT_SECONDS,
                    cwd=tmpdir,
                    stdin=subprocess.DEVNULL,
                    env={"PATH": "/usr/bin:/bin", "LC_ALL": "C", "TMPDIR": str(tmpdir)},
                    preexec_fn=_limit_resources if _HAVE_RESOURCE else None,
                )
        except subprocess.TimeoutExpired as exc:
            raise MergeError(f"{awk.name} timed out after {TIMEOUT_SECONDS}s") from exc
        except OSError as exc:
            raise MergeError(f"could not start {awk.name}: {exc}") from exc
        stdout = out_path.read_bytes()[:OUTPUT_LIMIT_BYTES].decode("utf-8", "replace")
        stderr = err_path.read_bytes()[:500].decode("utf-8", "replace").strip()
    if proc.returncode < 0:
        raise MergeError(f"{awk.name} was killed by signal {-proc.returncode} (resource limit?)")
    if proc.returncode != 0:
        raise MergeError(f"{awk.name} exited {proc.returncode}: {stderr}")
    return AccountDb.parse(stdout)
