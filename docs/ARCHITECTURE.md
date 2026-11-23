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
| `targets.py` | What gets executed (bundled snapshot, synthetic defect, a git revision, or a file), its provenance (commit, git blob id) and its trust level; refuses what is not allowed to run |
| `runner.py` | Scenario × awk → PASS / FAIL / ERROR, classification, reproduce command |
| `compare.py` | Pair results of two targets and name every change |
| `reporting.py` | Text, JSON (`profileguard-report/1`, schema in `report-schema.json`), HTML, and report validation |

## Execution modes

Each report states its mode and whether upstream code ran:

| Mode | Code executed | Upstream code? |
|---|---|---|
| `upstream-snapshot` | `src/profileguard/upstream_snapshot/flipper-accountdb.awk`, blob-checked against `dev@8c9ffc7` | yes |
| `upstream-git` | the script at a commit of a local checkout, extracted with `git show` (nothing is checked out or built) | yes |
| `synthetic-fixture` | the deliberately broken copy | no |
| `external-file` | any `.awk` file given on the command line | unknown, only its blob id is recorded |

There is no "model-only" mode. Every scenario result comes from executing a real script. The
Python code checks what the script printed. It does not reimplement the merge.

## Trust boundaries

What runs is code. profileguard decides **whether** it runs and **with which awk**. It does not
isolate it.

| Trust | Source | Allowed awks | Gate |
|---|---|---|---|
| `bundled` | `upstream_snapshot/flipper-accountdb.awk`, `fixtures/synthetic-defect-accountdb.awk` | all | blob id checked against the released value before every run; a modified install is refused (exit 2) |
| `upstream-merged` | `git show` of a commit that is an ancestor of the default branch, in a clone whose `origin` is the official repository | all | origin URL and ancestry checked |
| `unreviewed` | any other commit, any fork, any local file | `gawk --sandbox` only | refused without `--allow-unreviewed`; other awks need `--allow-unsandboxed-awk` too |

What each layer actually provides:

- **gawk `--sandbox`** turns off `system()`, input and output redirection, pipes and dynamic
  extensions, and stops a script from adding files to `ARGV` (each checked with gawk 5.2.1). It
  does **not** stop a script from reading the files named on the command line or `ENVIRON`,
  using CPU or memory, or exploiting a bug in gawk.
- **mawk, BusyBox awk, one-true-awk** have no sandbox. A script they run can execute any
  command as the invoking user (`tests/unit/test_merger_containment.py` demonstrates this on
  purpose).
- **Every run** gets a fresh temporary working directory (removed afterwards), an environment
  of only `PATH=/usr/bin:/bin`, `LC_ALL=C` and `TMPDIR`, no stdin, a 20 s wall-clock timeout and,
  on POSIX, `setrlimit` limits: 10 s CPU, 8 MiB per written file (stdout is a file, so this also
  bounds output), 1 GiB address space where the OS allows it (not on macOS), no core dumps.
  These contain mistakes such as an endless loop or an output flood. They are not a security
  boundary. The process runs as you and can read what you can read.
- **git** is only asked to read: `rev-parse`, `merge-base`, `remote get-url`, `show`. Nothing is
  checked out, built or hooked. It runs with `core.fsmonitor=false` and `core.hooksPath=/dev/null`.
  The "merged" decision relies on the clone's own remote-tracking refs, which whoever controls the
  clone can rewrite. Use a clone you made yourself.

If you need real isolation for unreviewed code, run profileguard inside a throwaway VM or
container. That is deliberately not built in.

## Data safety

- Inputs are synthetic and written only into the temporary directory. `/etc` and real account
  databases are never read or written.
- A unit test enforces that every hash-like field in the scenarios is a `$y$FAKE-…placeholder`
  string.
- Reports contain script file names, not local absolute paths.
