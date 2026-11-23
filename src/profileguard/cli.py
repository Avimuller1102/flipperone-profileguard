"""profileguard command line.

Exit codes: 0 every contract scenario passed; 1 a contract scenario failed or errored (with
--strict, also a proposed-invariant finding); 2 usage or environment problem.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from profileguard import __version__, compare, reporting, targets
from profileguard.merger import KNOWN_AWKS, AwkImpl, available_awks, find_awk
from profileguard.runner import Result, run_all
from profileguard.scenarios import SCENARIOS, Scenario, by_id

EXIT_OK, EXIT_FAIL, EXIT_USAGE = 0, 1, 2


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
    p.add_argument("--repo", type=Path, help="local clone of flipperos-btrfs-tools")
    p.add_argument(
        "--allow-unmerged",
        action="store_true",
        help="run a git revision that is not on the remote default branch",
    )
    p.add_argument(
        "--awk",
        action="append",
        metavar="NAME",
        help=f"awk to use, repeatable ({', '.join(KNOWN_AWKS)})",
    )
    p.add_argument("--all-awks", action="store_true", help="every awk found on PATH")
    p.add_argument("--scenario", action="append", metavar="ID", help="run only this scenario")


def cmd_doctor(_: argparse.Namespace) -> int:
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
    print(f"  git   {'found' if shutil.which('git') else 'not found (needed only for --repo)'}")
    try:
        snap = targets.snapshot()
        good = snap.blob == targets.SNAPSHOT_BLOB
        print(
            f"  snapshot {snap.label} blob {snap.blob} "
            f"{'matches upstream' if good else 'DOES NOT MATCH ' + targets.SNAPSHOT_BLOB}"
        )
        ok = ok and good
        targets.synthetic_defect()
        print("  synthetic defect fixture present")
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
    target = targets.resolve(spec, args.repo, workdir, args.allow_unmerged)
    awks = _select_awks(args.awk, args.all_awks)
    results = run_all(_select_scenarios(args.scenario), target, awks)
    return target, awks, results


def cmd_test(args: argparse.Namespace) -> int:
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
            deltas, f"{base_t.label} ({base_t.mode.value})", f"{cand_t.label} ({cand_t.mode.value})"
        )
    )
    return EXIT_FAIL if any(d.is_regression for d in deltas) else EXIT_OK


def cmd_report(args: argparse.Namespace) -> int:
    try:
        report = json.loads(Path(args.json_report).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        reporting.eprint(f"error: cannot read {args.json_report}: {exc}")
        return EXIT_USAGE
    if report.get("schema") != reporting.SCHEMA:
        reporting.eprint(f"error: not a {reporting.SCHEMA} report")
        return EXIT_USAGE
    Path(args.html).write_text(reporting.html_report(report), encoding="utf-8")
    print(f"wrote {args.html}")
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="profileguard",
        description="Check the account-database merge that Flipper OS profile migration uses "
        "(flipperos-btrfs-tools libs/flipper-accountdb.awk) against security scenarios. "
        "No hardware needed.",
    )
    p.add_argument("--version", action="version", version=f"profileguard {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("doctor", help="check awk implementations and bundled files").set_defaults(
        func=cmd_doctor
    )

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
    t.add_argument("-v", "--verbose", action="store_true")
    t.set_defaults(func=cmd_test)

    c = sub.add_parser("compare", help="run the scenarios on two targets and show what changed")
    c.add_argument("--baseline", required=True)
    c.add_argument("--candidate", required=True)
    _add_target_args(c)
    c.set_defaults(func=cmd_compare)

    r = sub.add_parser("report", help="render a JSON report as HTML")
    r.add_argument("json_report")
    r.add_argument("--html", required=True, metavar="FILE")
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
