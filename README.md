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
back. Because the image build runs `chpasswd` every time, the factory record differs between any
two builds, so the merge has to tell "the build changed this" apart from "the owner changed this"
on every update. The script has a short written contract in its header comment. On upstream `dev`
it has no tests.

## What it does

- Runs the **real upstream script** on 13 synthetic scenarios (fake placeholder hashes only) and
  checks each against an expectation that is either:
  - **contract**: written down upstream, so a failure is a violation of what upstream says it does;
  - **proposed**: a security property this project suggests and upstream has not decided, so a
    failure is a *finding* to discuss, not a bug report.
- Runs every scenario with each awk it finds (mawk, gawk `--sandbox`, BusyBox awk, one-true-awk)
  and checks they agree.
- Compares two upstream revisions and reports which scenarios were fixed, regressed or changed.
- Writes JSON (schema in `docs/report-schema.json`) and a self-contained HTML report. Every result
  records the commit and git blob it ran, and says whether upstream code was executed.
- Includes a **synthetic defect**, a plausible one-line change to the script, to show that the
  checks catch it.
- Proposes the contract scenarios upstream as one POSIX shell test written in the repository's
  own style (`upstream-proposal/`).

## What it does not do

- It does not run `migrate-profile` or `update-profile` themselves (they need btrfs and root),
  and it does not emulate a device.
- It does not decide security policy for Flipper OS. Proposed invariants are questions.
- No result here comes from hardware. See [docs/LIMITATIONS.md](docs/LIMITATIONS.md).

## Install

Python 3.11+ and at least one awk. Linux and macOS are supported; on Windows use WSL.

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

`--target snapshot` (the default) is an unmodified copy of upstream's script from
`dev@bb92d87`, bundled so the tool works offline. `profileguard doctor` checks that its git blob
id still matches upstream.

To test a live checkout or an open pull request:

```bash
git clone https://github.com/flipperdevices/flipperos-btrfs-tools ../flipperos-btrfs-tools
git -C ../flipperos-btrfs-tools fetch origin pull/4/head:pr4
profileguard test --repo ../flipperos-btrfs-tools --target origin/dev
profileguard compare --repo ../flipperos-btrfs-tools --baseline origin/dev --candidate pr4 --allow-unmerged
```

A revision that is not on upstream's default branch is refused until you pass
`--allow-unmerged`. Read the script before you pass it. gawk always runs with `--sandbox`.

Exit codes: `0` every contract scenario passed · `1` a contract scenario failed or errored (with
`--strict`, also a finding) · `2` usage or environment error.

## Sample output

Real output on this machine (`profileguard test --awk mawk`; all four awks in
`examples/dev-snapshot-output.txt`):

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

AM-10 is the bug that the open upstream
[PR #4](https://github.com/flipperdevices/flipperos-btrfs-tools/pull/4) by rafaetri already
fixes. It was not found by this project. AM-11 and AM-13 are discussed in
[docs/RESEARCH.md §7](docs/RESEARCH.md#7-results-of-running-it-summary-full-output-in-examples).

### The synthetic regression being caught

`synthetic-defect` changes one line: when both the new build and the owner changed a record, the
new build wins. That is **not** upstream code and **not** a known upstream bug.

```text
$ profileguard compare --baseline snapshot --candidate synthetic-defect --awk mawk
baseline:  snapshot:dev@bb92d87 (upstream-snapshot)
candidate: synthetic-defect (synthetic-fixture)

change            id     awk           basis     baseline -> candidate
regressed         AM-01  mawk          contract  PASS -> FAIL
                  candidate: 'user' is exactly: user:$y$FAKE-SALT-OWNER$owner-placeholder:20310:0:99999:7::: (owner's credential) -> observed: 'user' is: user:$y$FAKE-SALT-BUILD-2$factory-placeholder:20350:0:99999:7:::
regressed         AM-04  mawk          contract  PASS -> FAIL
                  candidate: 'user' is exactly: user:!$y$FAKE-SALT-BUILD-1$factory-placeholder:20310:0:99999:7::: (still locked) -> observed: 'user' is: user:$y$FAKE-SALT-BUILD-2$factory-placeholder:20350:0:99999:7:::

regressed: 2, unchanged: 11
```

Exit code 1. The owner's password and the owner's lock both turn back into the factory record.
The Hypothesis property tests find the same defect on their own, without being pointed at it
(`tests/integration/test_synthetic_regression.py`).

## Tests

```bash
make check      # ruff, ruff format --check, mypy --strict, pytest
make demo       # the offline demo above
```

The suite has unit tests, integration tests that pin what the dev snapshot and PR #4 do today,
cross-awk agreement checks, and Hypothesis properties that restate the script's header contract.
See [docs/TESTING.md](docs/TESTING.md).

## Documentation

- [docs/RESEARCH.md](docs/RESEARCH.md): upstream audit, commit SHAs, why this scope
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md): modules and execution modes
- [docs/TESTING.md](docs/TESTING.md): what is tested, and the hardware matrix nobody has run yet
- [docs/LIMITATIONS.md](docs/LIMITATIONS.md)
- [docs/UPSTREAM_CONTRIBUTION.md](docs/UPSTREAM_CONTRIBUTION.md): the proposed upstream change

## License

MIT, see [LICENSE](LICENSE). The bundled upstream script and the files derived from it are MIT,
Copyright (c) 2026 Flipper Devices; see `src/profileguard/upstream_snapshot/`.
