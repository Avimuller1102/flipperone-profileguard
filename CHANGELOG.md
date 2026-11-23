# Changelog

## 0.1.0 (unreleased)

- 13 scenarios for `flipper-accountdb.awk` (9 contract, 4 proposed), run against the real
  upstream script with every awk found.
- `profileguard doctor`, `scenarios`, `test`, `compare`, `report`.
- JSON (`profileguard-report/1`) and HTML reports with commit and blob provenance.
- Synthetic defect fixture and the tests that show it is caught.
- Proposed upstream shell test `upstream-proposal/tests/accountdb-merge.sh`.
- Trust levels (`bundled`, `upstream-merged`, `unreviewed`): bundled files are blob-checked before
  each run; a revision counts as merged only in a clone of the official repository; unreviewed code
  (unmerged PRs, forks, local files) needs `--allow-unreviewed` and runs only under
  `gawk --sandbox` unless `--allow-unsandboxed-awk` is also given.
- Process limits on every awk run: CPU, output size, memory, no core dumps.
- Exit code 3 for execution errors; `test --expect-fail`; `doctor --require`; `report` validates.
