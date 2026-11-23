# flipperone-profileguard

Security scenarios for the account-database merge that Flipper OS uses when a profile moves onto
a newer build. Runs on an ordinary computer; no Flipper One or RK3576 board needed.

> Independent community project. Not affiliated with or endorsed by Flipper Devices.

## The problem it addresses

On Flipper OS each profile is its own root filesystem with its own `/etc`
([issue #140](https://github.com/flipperdevices/flipperone-linux-build-scripts/issues/140)).
When `update-profile` puts a profile onto a newer build, `migrate-profile` merges the profile's
`passwd`, `shadow`, `group` and `gshadow` with the new build's copies. It does this one account at
a time with
[`libs/flipper-accountdb.awk`](https://github.com/flipperdevices/flipperos-btrfs-tools/blob/dev/libs/flipper-accountdb.awk).

That merge decides whether a profile keeps the password its owner set or gets the factory one
back. The image build runs `chpasswd` every time, so the factory record differs between any two
builds. The merge therefore has to tell "the build changed this" apart from "the owner changed
this" on every update. The script's contract is a short header comment. When this project
started, upstream had no tests for it.

## What it does

- Runs the **real upstream script** on 13 synthetic scenarios (fake placeholder hashes only). Each
  expectation is either:
  - **contract**: written down upstream, so a failure means the script does not do what upstream says;
  - **proposed**: a security property suggested here that upstream has not decided, so a failure
    is a question for maintainers, not a bug report. (All 13 scenarios are `contract` today: the
    three that started as questions were decided upstream, see below.)
- Runs every scenario with each awk it finds (mawk, gawk, BusyBox awk, one-true-awk) and checks
  they agree.
- Compares two upstream revisions and names each change: fixed, regressed or behaviour-change.
- Writes JSON (schema in `src/profileguard/report-schema.json`) and a self-contained HTML report.
  `profileguard report` validates a report. Every report records the commit, git blob and trust
  level of what ran.
- Includes a **synthetic defect** (a plausible one-line change, not upstream code) to show that
  the checks catch a regression.
- Proposes the contract scenarios upstream as one POSIX shell test written in the repository's own
  style (`upstream-proposal/`).

## What it does not do

- It does not run `migrate-profile` or `update-profile` themselves (they need btrfs and root),
  and it does not emulate a device.
- It does not decide security policy for Flipper OS.
- No result here comes from hardware. See [docs/LIMITATIONS.md](docs/LIMITATIONS.md).

## What happened upstream

| Scenario | What it showed on `dev@bb92d87` | Outcome |
|---|---|---|
| AM-10: an empty base file shifted the roles of the other files | contract violation | **Found and fixed by rafaetri** in [PR #4](https://github.com/flipperdevices/flipperos-btrfs-tools/pull/4), merged as `438ada7`. Reproduced here, not found here. |
| AM-11: an account the owner deleted got its factory shadow record back on update | question asked on [#140](https://github.com/flipperdevices/flipperone-linux-build-scripts/issues/140) | Reproduced by the maintainer, **fixed by Yury-MonZon in [`8c9ffc7`](https://github.com/flipperdevices/flipperos-btrfs-tools/commit/8c9ffc779501da67009b77ccc0bca338549a2929)**: a deletion in the profile now wins. |
| AM-12: with #4 alone, the factory record won over the owner's when the base lacked the file | question asked on #140 | Not reachable on a device: every stock carries all eight account files (checked on Flipper One by the maintainer). `8c9ffc7` makes the profile's record win on that path anyway. |
| AM-13: a group password the owner set was dropped | question asked on #140 | **Fixed in `8c9ffc7`**: scalar group/gshadow fields follow the same 3-way rule as whole records. |

The fixes are upstream's work. This project's part was writing the scenarios that surfaced
AM-11 to AM-13 and proposing the contract checks as
[flipperos-btrfs-tools#5](https://github.com/flipperdevices/flipperos-btrfs-tools/pull/5). The
maintainer ran it on a Flipper One and merged it into `dev` as
[`8cc73fe`](https://github.com/flipperdevices/flipperos-btrfs-tools/commit/8cc73fe) (`tests/accountdb-merge.sh`). Upstream added its own regression tests for all three cases in
`tests/accountdb.sh`.

The bundled snapshot is now `dev@8c9ffc7`, and it passes all 13 scenarios. The pre-fix revision
is kept as a test fixture to show what changed:

```text
$ profileguard compare --repo ../flipperos-btrfs-tools --baseline bb92d87 --candidate origin/dev --awk mawk
baseline:  bb92d87@bb92d87 (upstream-git, upstream-merged)
candidate: origin/dev@8c9ffc7 (upstream-git, upstream-merged)

change            id     awk           basis     baseline -> candidate
fixed             AM-10  mawk          contract  FAIL -> PASS
fixed             AM-11  mawk          contract  FAIL -> PASS
fixed             AM-13  mawk          contract  FAIL -> PASS

fixed: 3, unchanged: 10
```

## Install

Python 3.11+ and at least one awk. Verified in GitHub Actions on Ubuntu 24.04 with Python 3.11,
3.12 and 3.13, and on macOS with Python 3.12 and the system awk (see
[docs/TESTING.md](docs/TESTING.md)). On Windows, use WSL (untested).

```bash
git clone https://github.com/avimuller1102/flipperone-profileguard
cd flipperone-profileguard
python3 -m venv .venv && . .venv/bin/activate
python -m pip install -e ".[dev]"
```

Optional, to compare awk implementations on Debian/Ubuntu:

```bash
sudo apt-get install mawk gawk busybox original-awk
```

## Quickstart (offline)

```bash
profileguard doctor
profileguard scenarios --verbose
profileguard test --all-awks --html report.html
profileguard compare --baseline snapshot --candidate synthetic-defect
```

`--target snapshot` (the default) is an unmodified copy of upstream's script from `dev@8c9ffc7`,
bundled so the tool works offline. Its git blob id is checked before every run.

## Trust levels

| Trust | What | How it runs |
|---|---|---|
| `bundled` | the snapshot and the synthetic fixture, blob-checked | any awk |
| `upstream-merged` | a commit on the default branch of a clone whose origin is `github.com/flipperdevices/flipperos-btrfs-tools` | any awk |
| `unreviewed` | an unmerged PR, a fork, a local `.awk` file | refused without `--allow-unreviewed`; then only `gawk --sandbox`, unless `--allow-unsandboxed-awk` is also given |

```bash
git clone https://github.com/flipperdevices/flipperos-btrfs-tools ../flipperos-btrfs-tools
git -C ../flipperos-btrfs-tools fetch origin pull/4/head:pr4
profileguard test --repo ../flipperos-btrfs-tools --target origin/dev --all-awks
git -C ../flipperos-btrfs-tools show pr4:libs/flipper-accountdb.awk   # read it first
profileguard compare --repo ../flipperos-btrfs-tools --baseline origin/dev --candidate pr4 --allow-unreviewed --awk gawk
```

None of this is a sandbox. awk runs as you, with a timeout and resource limits; gawk's
`--sandbox` blocks `system()`, pipes and redirections but not reading files you can read. See
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#trust-boundaries).

**Exit codes:** `0` as expected · `1` scenario failures (a contract scenario failed, failures
differ from `--expect-fail`, or `compare` found a regression) · `2` usage, environment or policy
problem · `3` awk execution error.

## Sample output

Real output from `profileguard test --awk mawk` on Linux. All four awks are in
`examples/dev-snapshot-output.txt`.

```text
target: snapshot:dev@8c9ffc7  mode: upstream-snapshot  upstream code executed: yes
commit: 8c9ffc779501da67009b77ccc0bca338549a2929  blob: fae7452c04333de1fabcca98b7e9e20504666913

PASS   AM-01  [mawk] [contract] Owner password survives a rebuilt base
PASS   AM-02  [mawk] [contract] Owner password survives an unchanged base
PASS   AM-03  [mawk] [contract] Never-customized account follows the new base
PASS   AM-04  [mawk] [contract] Locked account stays locked
PASS   AM-05  [mawk] [contract] Owner-created account is carried
PASS   AM-06  [mawk] [contract] System account added by the new build appears
PASS   AM-07  [mawk] [contract] Membership the owner removed stays removed
PASS   AM-08  [mawk] [contract] Memberships added on both sides are united
PASS   AM-09  [mawk] [contract] gshadow administrators and members are both set-merged
PASS   AM-10  [mawk] [contract] Empty base file keeps the other files in their roles
PASS   AM-11  [mawk] [contract] Account the owner deleted is not revived by a rebuilt base
PASS   AM-12  [mawk] [contract] Owner password survives when the base lacks the database
PASS   AM-13  [mawk] [contract] Group password the owner set survives an unchanged base

13 checks: 13 passed, 0 failed (contract violations: 0, proposed-invariant findings: 0), 0 errors
```

CI runs this with `--strict` on every awk: any failure fails the build. What older revisions fail
is pinned in `tests/integration/test_upstream_behaviour.py`.

### The synthetic regression being caught

`synthetic-defect` changes one line of the snapshot: when the profile changed a record, the new
build wins instead. It is not upstream code and not a known upstream bug.

```text
$ profileguard compare --baseline snapshot --candidate synthetic-defect --awk mawk
baseline:  snapshot:dev@8c9ffc7 (upstream-snapshot, bundled)
candidate: synthetic-defect (synthetic-fixture, bundled)

change            id     awk           basis     baseline -> candidate
regressed         AM-01  mawk          contract  PASS -> FAIL
                  candidate: 'user' is exactly: user:$y$FAKE-SALT-OWNER$owner-placeholder:20310:0:99999:7::: (owner's credential) -> observed: 'user' is: user:$y$FAKE-SALT-BUILD-2$factory-placeholder:20350:0:99999:7:::
regressed         AM-02  mawk          contract  PASS -> FAIL
                  candidate: 'user' is exactly: user:$y$FAKE-SALT-OWNER$owner-placeholder:20310:0:99999:7::: (owner's credential) -> observed: 'user' is: user:$y$FAKE-SALT-BUILD-1$factory-placeholder:20300:0:99999:7:::
regressed         AM-04  mawk          contract  PASS -> FAIL
                  candidate: 'user' is exactly: user:!$y$FAKE-SALT-BUILD-1$factory-placeholder:20310:0:99999:7::: (still locked) -> observed: 'user' is: user:$y$FAKE-SALT-BUILD-2$factory-placeholder:20350:0:99999:7:::
regressed         AM-12  mawk          contract  PASS -> FAIL
                  candidate: 'user' is exactly: user:$y$FAKE-SALT-OWNER$owner-placeholder:20310:0:99999:7::: (owner's credential) -> observed: 'user' is: user:$y$FAKE-SALT-BUILD-2$factory-placeholder:20350:0:99999:7:::

regressed: 4, unchanged: 9
```

The command exits with code 1. After the defect, the owner's password and lock come back as the
factory record. The Hypothesis property tests also find this defect without being told where it
is.

## Tests

```bash
make check      # ruff, ruff format --check, mypy --strict, pytest
make demo       # the offline demo above
```

See [docs/TESTING.md](docs/TESTING.md) for what each layer covers, what was verified where, and
the hardware matrix nobody has run yet.

## Documentation

- [docs/RESEARCH.md](docs/RESEARCH.md): upstream audit, commit SHAs, why this scope
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md): modules, trust boundaries
- [docs/TESTING.md](docs/TESTING.md)
- [docs/LIMITATIONS.md](docs/LIMITATIONS.md)
- [docs/UPSTREAM_CONTRIBUTION.md](docs/UPSTREAM_CONTRIBUTION.md): the proposed upstream change

## License

MIT, see [LICENSE](LICENSE). The bundled upstream script and the files derived from it are MIT,
Copyright (c) 2026 Flipper Devices; see `src/profileguard/upstream_snapshot/`.
