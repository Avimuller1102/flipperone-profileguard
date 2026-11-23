# Testing

## Layers

| Layer | Where | Runs upstream code | Hardware |
|---|---|---|---|
| Unit | `tests/unit/` | no: parsing, checks, trust gates, report validation, exit codes, process limits | none |
| Integration | `tests/integration/` | yes: dev snapshot, PR #4 copy, synthetic defect, and the proposed shell test under every shell × awk installed | none |
| Property | `tests/property/` | yes: Hypothesis generates account databases, the real script merges them | none |
| Hardware | the matrix below | yes | RK3576 board, **not run** |

`tests/integration/test_upstream_behaviour.py` pins what upstream does today, for every awk
installed: dev fails AM-10, AM-11 and AM-13, and the PR #4 copy fails AM-11, AM-12 and AM-13. It
also checks that all awks agree byte for byte. If upstream changes, these tests fail on purpose,
and someone must look at the change before updating them.

The properties restate `flipper-accountdb.awk:3-5`:

- a change made in the profile rides along;
- an account nobody touched follows the new base;
- a deletion in the profile holds when the base did not change the record;
- an account the new base added appears;
- no key appears twice.

Two more properties: running the same update twice changes nothing, and group members are
three-way set-merged. Generated files always contain a root entry, so the dev snapshot's
empty-file bug is left to AM-10.

## Running

```bash
python -m pytest -v
python -m pytest tests/property -v --hypothesis-show-statistics
```

## What has been verified where

Verified means executed on 2026-11-23 in this project's development environment (Ubuntu 24.04
x86_64 container), not in CI.

| Environment | Status |
|---|---|
| Linux, Python 3.11.18 / 3.12.3 / 3.13.18: full pytest, mypy, `--expect-fail` run | verified |
| awk: mawk 1.3.4, gawk 5.2.1, BusyBox 1.36.1 awk, one-true-awk 20231127 | verified, identical output |
| Shell test: dash 0.5.12, bash 5.2, BusyBox 1.36.1 sh × the four awks, dev and PR #4 | verified: 24 distinct combinations (3 shells × 4 awks × 2 revisions) |
| macOS (BSD userland, Apple's awk) | **not verified**. CI has a `macos-14` job; it has not run yet |
| GitHub Actions workflow | **not verified**. actionlint 1.7.12 is clean, but the workflow has never run on GitHub |
| Windows | not supported (needs a POSIX awk); WSL untested |

## Hardware validation matrix (specified, NOT RUN)

For someone with a supported RK3576 board running a Flipper OS image with two builds available.
None of this has been executed by this project.

| # | Steps | Expected observation | Status |
|---|---|---|---|
| H-1 | Set a password for `user` in profile A; `update-profile A` to a newer build | Log in to A with the new password works; `user`/`user` is refused | NOT RUN |
| H-2 | `passwd -l user` in A; update A | Password login for `user` refused after update | NOT RUN |
| H-3 | Create `alice`, add to `sudo`, remove `user` from `sudo`; update | `alice` logs in and has sudo; `user` is not in `sudo` | NOT RUN |
| H-4 | `userdel user` in A (after creating another admin); update A | Record whether `/etc/shadow` holds `user` again and what `migrate-profile` warned (AM-11) | NOT RUN |
| H-5 | Never touch profile B; update B | B accepts `user`/`user` (documented current behaviour, #140 decision 4) | NOT RUN |
| H-6 | Run `migrate-profile` by hand without `-a` (dry run by default, `migrate-profile:30`) | Dry run lists the shadow change and writes nothing | NOT RUN |
