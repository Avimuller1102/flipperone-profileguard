"""Text, JSON and HTML output. The JSON layout is described in docs/report-schema.json."""

from __future__ import annotations

import html
import json
import platform
import sys
from datetime import UTC, datetime
from importlib import resources
from typing import Any

from profileguard import __version__
from profileguard.merger import AwkImpl
from profileguard.runner import Result, Status
from profileguard.targets import Target

SCHEMA = "profileguard-report/1"

LIMITATIONS = (
    "Only libs/flipper-accountdb.awk is executed. migrate-profile's surrounding steps (btrfs send, "
    "finalize_accountdbs, check_db_pair, rsync) are not run.",
    "Inputs are synthetic account databases with placeholder hashes, not files from a device.",
    "No result here was obtained on Flipper One or RK3576 hardware.",
    "Passing every scenario does not make a revision secure; it means these scenarios hold.",
)


def environment(awks: list[AwkImpl]) -> dict[str, Any]:
    return {
        "python": platform.python_version(),
        "platform": platform.platform(terse=True),
        "awk": [{"name": a.name, "version": a.version, "sandboxed": a.sandboxed} for a in awks],
    }


def summarize(results: list[Result]) -> dict[str, int]:
    out = {"total": len(results)}
    for status in Status:
        out[status.value] = sum(r.status is status for r in results)
    out["contract_violations"] = sum(r.classification == "contract-violation" for r in results)
    out["findings"] = sum(r.classification == "finding" for r in results)
    return out


def result_dict(r: Result) -> dict[str, Any]:
    s = r.scenario
    return {
        "scenario_id": s.id,
        "title": s.title,
        "database": s.kind.value,
        "basis": s.basis.value,
        "basis_source": s.source,
        "story": s.story,
        "awk": r.awk.name,
        "status": r.status.value,
        "classification": r.classification,
        "expected": [c.describe() for c in s.checks],
        "observed": list(r.failures) if r.failures else ["all expectations met"],
        "error": r.error,
        "inputs": {
            "base": list(s.base.lines),
            "new_base": list(s.new_base.lines),
            "profile": list(s.profile.lines),
        },
        "merged_output": list(r.merged),
        "reproduce": r.reproduce(),
        "refs": list(s.refs),
    }


def build_report(target: Target, awks: list[AwkImpl], results: list[Result]) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "tool": {"name": "profileguard", "version": __version__},
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "target": target.provenance(),
        "environment": environment(awks),
        "summary": summarize(results),
        "results": [result_dict(r) for r in results],
        "limitations": list(LIMITATIONS),
    }


def _schema() -> dict[str, Any]:
    text = resources.files("profileguard").joinpath("report-schema.json").read_text("utf-8")
    loaded: dict[str, Any] = json.loads(text)
    return loaded


def _check(obj: Any, schema: dict[str, Any], where: str, out: list[str]) -> None:
    """The subset of JSON Schema the report schema uses: required, enum, const, type, items."""
    types = schema.get("type")
    allowed = types if isinstance(types, list) else [types] if types else []
    py = {"object": dict, "array": list, "string": str, "boolean": bool, "null": type(None)}
    if allowed and not any(isinstance(obj, py[t]) for t in allowed if t in py):
        out.append(f"{where}: expected {'/'.join(allowed)}")
        return
    if "const" in schema and obj != schema["const"]:
        out.append(f"{where}: must be {schema['const']!r}")
    if "enum" in schema and obj not in schema["enum"]:
        out.append(f"{where}: {obj!r} not one of {schema['enum']}")
    if isinstance(obj, dict):
        for key in schema.get("required", []):
            if key not in obj:
                out.append(f"{where}: missing '{key}'")
        for key, sub in schema.get("properties", {}).items():
            if key in obj:
                _check(obj[key], sub, f"{where}.{key}", out)
    if isinstance(obj, list) and "items" in schema:
        for i, item in enumerate(obj):
            _check(item, schema["items"], f"{where}[{i}]", out)


def validate(report: Any) -> list[str]:
    """Problems that make a report unusable: schema violations and internal inconsistencies."""
    problems: list[str] = []
    _check(report, _schema(), "report", problems)
    if problems:
        return problems
    results = report["results"]
    if not results:
        problems.append("report.results: empty")
    pairs = [(r["scenario_id"], r["awk"]) for r in results]
    if len(pairs) != len(set(pairs)):
        problems.append("report.results: a scenario/awk pair appears twice")
    recount = summarize_dicts(results)
    for key, value in recount.items():
        if report["summary"].get(key) != value:
            problems.append(f"report.summary.{key}: {report['summary'].get(key)} != {value}")
    awks = {a["name"] for a in report["environment"]["awk"]}
    if {r["awk"] for r in results} - awks:
        problems.append("report.results: an awk not listed in report.environment.awk")
    return problems


def summarize_dicts(results: list[dict[str, Any]]) -> dict[str, int]:
    out = {"total": len(results)}
    for status in Status:
        out[status.value] = sum(r["status"] == status.value for r in results)
    out["contract_violations"] = sum(r["classification"] == "contract-violation" for r in results)
    out["findings"] = sum(r["classification"] == "finding" for r in results)
    return out


def write_json(report: dict[str, Any], path: str) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
        fh.write("\n")


def text_report(target: Target, results: list[Result], verbose: bool) -> str:
    lines = [
        f"target: {target.label}  mode: {target.mode.value}  "
        f"upstream code executed: {'yes' if target.is_upstream_code else 'no'}",
    ]
    if target.commit:
        lines.append(f"commit: {target.commit}  blob: {target.blob}")
    else:
        lines.append(f"blob: {target.blob}")
    lines.append("")
    for r in results:
        tag = r.status.value if r.status is Status.PASS else f"{r.status.value}*"
        lines.append(
            f"{tag:<6} {r.scenario.id}  [{r.awk.name}] [{r.scenario.basis.value}] "
            f"{r.scenario.title}"
        )
        if r.status is not Status.PASS or verbose:
            for f in r.failures:
                lines.append(f"         {f}")
            if r.error:
                lines.append(f"         error: {r.error}")
            if r.status is not Status.PASS:
                lines.append(f"         class: {r.classification}")
                lines.append(f"         reproduce: {r.reproduce()}")
    s = summarize(results)
    lines.append("")
    lines.append(
        f"{s['total']} checks: {s['PASS']} passed, {s['FAIL']} failed "
        f"(contract violations: {s['contract_violations']}, "
        f"proposed-invariant findings: {s['findings']}), "
        f"{s['ERROR']} errors"
    )
    return "\n".join(lines)


_CSS = """
:root{--bg:#fff;--fg:#1d1d1f;--mut:#5f6368;--line:#dadce0;--pass:#137333;--fail:#b3261e;
--find:#8a5a00;--card:#f8f9fa}
@media (prefers-color-scheme:dark){:root{--bg:#141414;--fg:#e8eaed;--mut:#9aa0a6;--line:#3c4043;
--pass:#81c995;--fail:#f28b82;--find:#fdd663;--card:#1f1f1f}}
body{background:var(--bg);color:var(--fg);font:14px/1.5 system-ui,sans-serif;margin:0;
padding:24px 16px;max-width:1100px;margin-inline:auto}
h1{font-size:20px;margin:0 0 4px}h2{font-size:16px;margin:24px 0 8px}
.mut{color:var(--mut)}table{border-collapse:collapse;width:100%}
th,td{border-bottom:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:top}
.PASS{color:var(--pass);font-weight:600}.FAIL,.ERROR{color:var(--fail);font-weight:600}
.finding{color:var(--find)}code,pre{font:12px/1.4 ui-monospace,monospace}
pre{background:var(--card);padding:8px;overflow-x:auto;margin:4px 0}
details{margin:2px 0}.wrap{overflow-x:auto}
.nw{white-space:nowrap}td code{word-break:break-all}
"""


def html_report(report: dict[str, Any]) -> str:
    e = html.escape
    t = report["target"]
    s = report["summary"]
    rows = []
    for r in report["results"]:
        status = r["status"]
        klass = "finding" if r["classification"] == "finding" else status
        detail = (
            "<details><summary>details</summary>"
            f"<p>{e(r['story'])}</p><p class='mut'>basis: {e(r['basis_source'])}</p>"
            "<b>expected</b><pre>" + e("\n".join(r["expected"])) + "</pre>"
            "<b>observed</b><pre>"
            + e("\n".join(r["observed"]))
            + "</pre>"
            + (f"<b>error</b><pre>{e(r['error'])}</pre>" if r["error"] else "")
            + "<b>inputs</b><pre>"
            + e(
                "\n".join(
                    f"{k}:\n  " + "\n  ".join(v or ["(empty file)"]) for k, v in r["inputs"].items()
                )
            )
            + "</pre><b>merged output</b><pre>"
            + e("\n".join(r["merged_output"]) or "(empty)")
            + f"</pre><b>reproduce</b><pre>{e(r['reproduce'])}</pre></details>"
        )
        rows.append(
            f"<tr><td class='{e(klass)} nw'>{e(status)}</td>"
            f"<td class='nw'>{e(r['scenario_id'])}</td>"
            f"<td>{e(r['awk'])}</td><td>{e(r['basis'])}</td><td>{e(r['classification'])}</td>"
            f"<td>{e(r['title'])}{detail}</td></tr>"
        )
    lim = "".join(f"<li>{e(x)}</li>" for x in report["limitations"])
    awks = ", ".join(f"{a['name']} ({a['version']})" for a in report["environment"]["awk"])
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ProfileGuard Report</title><style>{_CSS}</style></head><body>
<h1>ProfileGuard report</h1>
<p class="mut">{e(report["generated_at"])} &middot; profileguard {e(report["tool"]["version"])}</p>
<h2>Target</h2>
<table><tr><th>label</th><td>{e(str(t["label"]))}</td></tr>
<tr><th>mode</th><td>{e(str(t["mode"]))}</td></tr>
<tr><th>upstream code executed</th><td>{"yes" if t["upstream_code_executed"] else "no"}</td></tr>
<tr><th>commit</th><td><code>{e(str(t["commit"]))}</code></td></tr>
<tr><th>git blob</th><td><code>{e(str(t["git_blob"]))}</code></td></tr>
<tr><th>awk</th><td>{e(awks)}</td></tr></table>
<h2>Summary</h2>
<p>{s["total"]} checks: <span class="PASS">{s["PASS"]} passed</span>, {s["FAIL"]} failed
({s["contract_violations"]} contract violations, <span class="finding">{s["findings"]} findings on
proposed invariants</span>), {s["ERROR"]} errors.</p>
<h2>Results</h2><div class="wrap"><table>
<tr><th>status</th><th>id</th><th>awk</th><th>basis</th><th>class</th><th>scenario</th></tr>
{"".join(rows)}</table></div>
<h2>Limitations</h2><ul>{lim}</ul>
<p class="mut">Python {e(report["environment"]["python"])} on
{e(report["environment"]["platform"])}</p>
</body></html>
"""


def eprint(*args: object) -> None:
    print(*args, file=sys.stderr)
