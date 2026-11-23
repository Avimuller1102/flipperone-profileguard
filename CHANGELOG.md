# Changelog

## 0.1.1 (2026-11-23)

- The proposed shell test was merged upstream as `tests/accountdb-merge.sh` (`8cc73fe`).

- Bundled snapshot moved to upstream `dev@8c9ffc7`, which fixes AM-11 and AM-13 (Yury-MonZon)
  and includes #4 (rafaetri, AM-10). All 13 scenarios pass on it.
- AM-11, AM-12 and AM-13 are now `contract`: upstream documented the behaviour.
- `dev@bb92d87` kept as a test fixture; the synthetic defect is regenerated from the new snapshot.
- CI requires zero failures (`test --strict`) instead of a list of expected ones.
- Fix: a local `.awk` target given as a relative path failed to open, because awk runs from a
  temporary directory.

## 0.1.0 (2026-11-23)

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
