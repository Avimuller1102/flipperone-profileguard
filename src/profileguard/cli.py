"""profileguard command line.

Exit codes:
  0  as expected: every contract scenario passed, or with --expect-fail exactly the listed
     scenarios failed
  1  scenario failures: a contract scenario failed (with --strict, also a proposed-invariant
     finding), or the failures differ from --expect-fail, or compare found a regression
  2  usage, environment or policy problem: bad arguments, a missing awk, unreviewed code without
     the flags that allow it, a modified installation, an invalid report
  3  execution error: awk crashed, timed out or hit a resource limit
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from profileguard import __version__, compare, reporting, targets
from profileguard.merger import KNOWN_AWKS, AwkImpl, available_awks, find_awk
from profileguard.runner import Result, Status, run_all
from profileguard.scenarios import SCENARIOS, Scenario, by_id

EXIT_OK, EXIT_FAIL, EXIT_USAGE, EXIT_ERROR = 0, 1, 2, 3


def _select_awks(names: list[str] | None, all_awks: bool) -> list[AwkImpl]:
    if names:
        found = []
        for n in names:
            impl = find_awk(n)
            if impl is None:
                raise targets.TargetError(f"awk implementation '{n}' not found on PATH")
            found.append(impl)
        return found
    impls = available_awks()
    if not impls:
        raise targets.TargetError("no awk implementation found on PATH")
    return impls if all_awks else impls[:1]


def _select_scenarios(ids: list[str] | None) -> list[Scenario]:
    if not ids:
        return list(SCENARIOS)
    try:
        return [by_id(i) for i in ids]
    except KeyError as exc:
        raise targets.TargetError(f"unknown scenario {exc}; see 'profileguard scenarios'") from exc


def _add_target_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--repo", type=Path, help="a clone of flipperos-btrfs-tools you made yourself")
    p.add_argument(
        "--allow-unreviewed",
        action="store_true",
        help="run code that is not merged upstream (an unmerged PR, a fork, a local .awk file) "
        "after you have read it; it then runs only under gawk --sandbox",
    )
    p.add_argument(
        "--allow-unsandboxed-awk",
        action="store_true",
        help="with --allow-unreviewed, also run it under awks that have no sandbox",
    )
    p.add_argument(
        "--awk",
        action="append",
        metavar="NAME",
        help=f"awk to use, repeatable ({', '.join(KNOWN_AWKS)})",
    )
    p.add_argument("--all-awks", action="store_true", help="every awk found on PATH")
    p.add_argument("--scenario", action="append", metavar="ID", help="run only this scenario")


def cmd_doctor(args: argparse.Namespace) -> int:
    ok = True
    print(f"profileguard {__version__}, Python {sys.version.split()[0]}")
    awks = available_awks()
    for a in awks:
        print(f"  awk   {a.name:<13} {a.version}{'  (--sandbox)' if a.sandboxed else ''}")
    listed = {a.name for a in awks}
    for n in KNOWN_AWKS:
        if n in listed:
            continue
        if find_awk(n) is None:
            print(f"  awk   {n:<13} not found")
        else:
            print(f"  awk   {n:<13} same binary as one listed above")
    if not awks:
        print("  ERROR: no awk found; install mawk or gawk")
        ok = False
    for name in args.require or []:
        if find_awk(name) is None:
            print(f"  ERROR: required awk '{name}' not found")
            ok = False
    print(f"  git   {'found' if shutil.which('git') else 'not found (needed only for --repo)'}")
    try:
        snap = targets.snapshot()
        print(f"  snapshot {snap.label} blob {snap.blob} matches upstream")
        targets.synthetic_defect()
        print(f"  synthetic defect fixture blob {targets.SYNTHETIC_BLOB} as released")
    except targets.TargetError as exc:
        print(f"  ERROR: {exc}")
        ok = False
    print("doctor: ok" if ok else "doctor: problems found")
    return EXIT_OK if ok else EXIT_USAGE


def cmd_scenarios(args: argparse.Namespace) -> int:
    for s in SCENARIOS:
        print(f"{s.id}  {s.kind.value:<8} {s.basis.value:<9} {s.title}")
        if args.verbose:
            print(f"      {s.story}")
            print(f"      basis: {s.source}")
            for c in s.checks:
                print(f"      expect: {c.describe()}")
            print()
    return EXIT_OK


def _run(
    args: argparse.Namespace, spec: str, workdir: Path
) -> tuple[targets.Target, list[AwkImpl], list[Result]]:
    target = targets.resolve(spec, args.repo, workdir, args.allow_unreviewed)
    awks = _select_awks(args.awk, args.all_awks)
    targets.check_execution_policy(target, awks, args.allow_unsandboxed_awk)
    results = run_all(_select_scenarios(args.scenario), target, awks)
    return target, awks, results


def _expectation_problems(results: list[Result], expected: set[str]) -> list[str]:
    """Where the failing scenarios differ from the expected set, per awk."""
    problems = []
    for awk in sorted({r.awk.name for r in results}):
        ran = {r.scenario.id for r in results if r.awk.name == awk}
        failed = {r.scenario.id for r in results if r.awk.name == awk and r.status is Status.FAIL}
        want = expected & ran
        for sid in sorted(failed - want):
            problems.append(f"[{awk}] {sid} failed but was not expected to")
        for sid in sorted(want - failed):
            problems.append(f"[{awk}] {sid} was expected to fail but passed")
    return problems


def cmd_test(args: argparse.Namespace) -> int:
    ids = [i for arg in args.expect_fail or [] for i in arg.split(",") if i]
    expected = {s.id for s in _select_scenarios(ids)} if ids else set()
    with targets.new_workdir() as wd:
        target, awks, results = _run(args, args.target, Path(wd))
    print(reporting.text_report(target, results, args.verbose))
    report = reporting.build_report(target, awks, results)
    if args.json:
        reporting.write_json(report, args.json)
        print(f"wrote {args.json}")
    if args.html:
        Path(args.html).write_text(reporting.html_report(report), encoding="utf-8")
        print(f"wrote {args.html}")
    if any(r.status is Status.ERROR for r in results):
        return EXIT_ERROR
    if args.expect_fail is not None:
        problems = _expectation_problems(results, expected)
        for p in problems:
            print(f"unexpected: {p}")
        if not problems:
            print(f"failures match --expect-fail: {', '.join(sorted(expected))}")
        return EXIT_FAIL if problems else EXIT_OK
    failing = any(r.counts_against_exit for r in results)
    if args.strict:
        failing = failing or any(r.classification == "finding" for r in results)
    return EXIT_FAIL if failing else EXIT_OK


def cmd_compare(args: argparse.Namespace) -> int:
    with targets.new_workdir() as wd:
        base_t, _, base_r = _run(args, args.baseline, Path(wd))
        cand_t, _, cand_r = _run(args, args.candidate, Path(wd))
    deltas = compare.compare(base_r, cand_r)
    print(
        compare.render(
            deltas,
            f"{base_t.label} ({base_t.mode.value}, {base_t.trust.value})",
            f"{cand_t.label} ({cand_t.mode.value}, {cand_t.trust.value})",
        )
    )
    if any(r.status is Status.ERROR for r in (*base_r, *cand_r)):
        return EXIT_ERROR
    return EXIT_FAIL if any(d.is_regression for d in deltas) else EXIT_OK


def cmd_report(args: argparse.Namespace) -> int:
    try:
        report = json.loads(Path(args.json_report).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        reporting.eprint(f"error: cannot read {args.json_report}: {exc}")
        return EXIT_USAGE
    problems = reporting.validate(report)
    if problems:
        for p in problems:
            reporting.eprint(f"invalid report: {p}")
        return EXIT_USAGE
    print(f"{args.json_report}: valid {reporting.SCHEMA} report")
    if args.html:
        Path(args.html).write_text(reporting.html_report(report), encoding="utf-8")
        print(f"wrote {args.html}")
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="profileguard",
        description="Check the account-database merge that Flipper OS profile migration uses "
        "(flipperos-btrfs-tools libs/flipper-accountdb.awk) against security scenarios. "
        "No hardware needed.",
        epilog="exit codes: 0 as expected, 1 scenario failures, 2 usage/environment/policy, "
        "3 execution error",
    )
    p.add_argument("--version", action="version", version=f"profileguard {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    d = sub.add_parser("doctor", help="check awk implementations and bundled files")
    d.add_argument(
        "--require", action="append", metavar="AWK", help="fail unless this awk is installed"
    )
    d.set_defaults(func=cmd_doctor)

    sc = sub.add_parser("scenarios", help="list scenarios")
    sc.add_argument("-v", "--verbose", action="store_true")
    sc.set_defaults(func=cmd_scenarios)

    t = sub.add_parser("test", help="run scenarios against one target")
    t.add_argument(
        "--target",
        default="snapshot",
        help="'snapshot' (default), 'synthetic-defect', an .awk file, or a git "
        "revision together with --repo",
    )
    _add_target_args(t)
    t.add_argument("--json", metavar="FILE", help="write a JSON report")
    t.add_argument("--html", metavar="FILE", help="write a self-contained HTML report")
    t.add_argument(
        "--strict", action="store_true", help="also exit 1 on findings against proposed invariants"
    )
    t.add_argument(
        "--expect-fail",
        action="append",
        metavar="ID",
        help="exit 0 only if exactly these scenarios fail, on every awk "
        "(repeatable or comma-separated)",
    )
    t.add_argument("-v", "--verbose", action="store_true")
    t.set_defaults(func=cmd_test)

    c = sub.add_parser("compare", help="run the scenarios on two targets and show what changed")
    c.add_argument("--baseline", required=True)
    c.add_argument("--candidate", required=True)
    _add_target_args(c)
    c.set_defaults(func=cmd_compare)

    r = sub.add_parser("report", help="validate a JSON report, optionally render it as HTML")
    r.add_argument("json_report")
    r.add_argument("--html", metavar="FILE")
    r.set_defaults(func=cmd_report)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return int(args.func(args))
    except targets.TargetError as exc:
        reporting.eprint(f"error: {exc}")
        return EXIT_USAGE
    except BrokenPipeError:  # output piped into head(1) and friends
        return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
