# Architecture

```
scenarios.py ─┐                         ┌─ reporting.py → text, JSON, HTML
checks.py ────┼─ runner.py ─ merger.py ─┤
targets.py ───┘      │      (awk subprocess)
                     └─ compare.py → fixed / regressed / behaviour-change
cli.py: doctor · scenarios · test · compare · report
```

| Module | Responsibility |
|---|---|
| `accountdb.py` | An account database as ordered raw lines; the list fields `migrate-profile` passes per database |
| `merger.py` | Find awk implementations; run one merge the way `migrate-profile:421` does, in a private temp dir with a minimal environment and a timeout |
| `scenarios.py` | The 13 scenarios: inputs, expectations, and the **basis** of each expectation (`contract` or `proposed`) with its upstream source |
| `checks.py` | Expectations: exact line, absent, member set, well-formed (root present, no duplicate keys) |
| `targets.py` | What gets executed: bundled snapshot, synthetic defect, a git revision, or a file, with provenance (commit, git blob id, whether it is on upstream's default branch) |
| `runner.py` | Scenario × awk → PASS / FAIL / ERROR, classification, reproduce command |
| `compare.py` | Pair results of two targets and name every change |
| `reporting.py` | Text, JSON (`profileguard-report/1`) and HTML |

## Execution modes

Each report states its mode and whether upstream code ran:

| Mode | Code executed | Upstream code? |
|---|---|---|
| `upstream-snapshot` | `src/profileguard/upstream_snapshot/flipper-accountdb.awk`, blob-checked against `dev@bb92d87` | yes |
| `upstream-git` | the script at a commit of a local checkout, extracted with `git show` (nothing is checked out or built) | yes |
| `synthetic-fixture` | the deliberately broken copy | no |
| `external-file` | any `.awk` file given on the command line | unknown, only its blob id is recorded |

There is no "model-only" mode. Every scenario result comes from executing a real script. The
Python code checks what the script printed. It does not reimplement the merge.

## Safety

- Inputs are written to a fresh temporary directory and removed afterwards. Nothing outside it is
  read or written. `/etc` is never touched.
- awk runs with `PATH=/usr/bin:/bin`, `LC_ALL=C`, no stdin and a 20 s timeout. gawk gets `--sandbox`,
  which disables `system()` and redirections.
- A git revision that is not an ancestor of the remote default branch is refused unless
  `--allow-unmerged` is given.
- No real credentials exist anywhere in the repository; a unit test enforces that every hash-like
  field is a `$y$FAKE-…placeholder` string.
