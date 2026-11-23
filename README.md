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
this" on every update. The script's contract is a short header comment, and on upstream `dev` it
has no tests.

## What it does

- Runs the **real upstream script** on 13 synthetic scenarios (fake placeholder hashes only). Each
  expectation is either:
  - **contract**: written down upstream, so a failure means the script does not do what upstream says;
  - **proposed**: a security property suggested here that upstream has not decided, so a failure
    is a question for maintainers, not a bug report.
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

## What it found, and who found it

| Kind | Scenario | Status |
|---|---|---|
| Upstream defect **already found and fixed by someone else** | AM-10: an empty base file shifts the roles of the other files | Fixed in the open [PR #4](https://github.com/flipperdevices/flipperos-btrfs-tools/pull/4) by rafaetri. Reproduced here; not found by this project. |
| Behaviour questions for maintainers | AM-11: an account the owner deleted gets its factory shadow record back on update · AM-12: with PR #4, if the base lacks the file, the factory record wins over the owner's · AM-13: an owner-set group password is dropped | Unconfirmed policy. Not presented as bugs. See [docs/RESEARCH.md §7](docs/RESEARCH.md#7-results-of-running-it-summary-full-output-in-examples). |
| Synthetic defect | `synthetic-defect` | Written for this project to show detection; not upstream code. |

No new upstream defect is confirmed.

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

`--target snapshot` (the default) is an unmodified copy of upstream's script from `dev@bb92d87`,
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
target: snapshot:dev@bb92d87  mode: upstream-snapshot  upstream code executed: yes
commit: bb92d87252807ee306c90e9c853b8a9af84a493f  blob: 0533182f2d87de6d350dd45f22573122ace6e087

PASS   AM-01  [mawk] [contract] Owner password survives a rebuilt base
PASS   AM-02  [mawk] [contract] Owner password survives an unchanged base
PASS   AM-03  [mawk] [contract] Never-customized account follows the new base
PASS   AM-04  [mawk] [contract] Locked account stays locked
PASS   AM-05  [mawk] [contract] Owner-created account is carried
PASS   AM-06  [mawk] [contract] System account added by the new build appears
PASS   AM-07  [mawk] [contract] Membership the owner removed stays removed
PASS   AM-08  [mawk] [contract] Memberships added on both sides are united
PASS   AM-09  [mawk] [contract] gshadow administrators and members are both set-merged
FAIL*  AM-10  [mawk] [contract] Empty base file keeps the other files in their roles
         'user' is exactly: user:x:1000:1000::/home/user:/bin/bash -> observed: 'user' is: (absent)
         a 'root' entry exists and no key appears twice -> observed: no root entry
         class: contract-violation
         reproduce: profileguard test --target snapshot --awk mawk --scenario AM-10
FAIL*  AM-11  [mawk] [proposed] Account the owner deleted is not revived by a rebuilt base
         'user' is absent (owner deleted it) -> observed: 'user' is present: user:$y$FAKE-SALT-BUILD-2$factory-placeholder:20350:0:99999:7:::
         class: finding
         reproduce: profileguard test --target snapshot --awk mawk --scenario AM-11
PASS   AM-12  [mawk] [proposed] Owner password survives when the base lacks the database
FAIL*  AM-13  [mawk] [proposed] Group password the owner set survives an unchanged base
         'wheel' is exactly: wheel:$y$FAKE-SALT-GROUP$group-placeholder::user -> observed: 'wheel' is: wheel:!::user
         class: finding
         reproduce: profileguard test --target snapshot --awk mawk --scenario AM-13

13 checks: 10 passed, 3 failed (contract violations: 1, proposed-invariant findings: 2), 0 errors
```

CI pins exactly these failures with `profileguard test --expect-fail AM-10,AM-11,AM-13`. Any other
failure, or one of these starting to pass, fails the build.

### The synthetic regression being caught

```text
$ profileguard compare --baseline snapshot --candidate synthetic-defect --awk mawk
baseline:  snapshot:dev@bb92d87 (upstream-snapshot, bundled)
candidate: synthetic-defect (synthetic-fixture, bundled)

change            id     awk           basis     baseline -> candidate
regressed         AM-01  mawk          contract  PASS -> FAIL
                  candidate: 'user' is exactly: user:$y$FAKE-SALT-OWNER$owner-placeholder:20310:0:99999:7::: (owner's credential) -> observed: 'user' is: user:$y$FAKE-SALT-BUILD-2$factory-placeholder:20350:0:99999:7:::
regressed         AM-04  mawk          contract  PASS -> FAIL
                  candidate: 'user' is exactly: user:!$y$FAKE-SALT-BUILD-1$factory-placeholder:20310:0:99999:7::: (still locked) -> observed: 'user' is: user:$y$FAKE-SALT-BUILD-2$factory-placeholder:20350:0:99999:7:::

regressed: 2, unchanged: 11
```

The command exits with code 1. After the defect, both the owner's password and the owner's lock
come back as the factory record. The Hypothesis property tests also find this defect without
being told where it is.

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
