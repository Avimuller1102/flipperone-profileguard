# Testing

## Layers

| Layer | Where | Runs upstream code | Hardware |
|---|---|---|---|
| Unit | `tests/unit/` | no (parsing, checks, git provenance, CLI exit codes) | none |
| Integration | `tests/integration/` | yes: dev snapshot, PR #4, synthetic defect, proposed shell test | none |
| Property | `tests/property/` | yes: Hypothesis generates account databases, the real script merges them | none |
| Hardware | the matrix below | yes | RK3576 board, **not run** |

`tests/integration/test_upstream_behaviour.py` pins what upstream does today (dev fails AM-10, AM-11
and AM-13; PR #4 fails AM-11, AM-12 and AM-13) for every awk installed, and checks all awks agree byte for
byte. If upstream changes, these tests fail on purpose and must be updated after a look at the
change.

The properties restate `flipper-accountdb.awk:3-5`: a profile's change rides along, an untouched
account follows the new base, a profile's deletion holds when the base did not change the
record, a new-base addition appears, no key is duplicated. Two more: re-running the same update
changes nothing, and group members are three-way set-merged. Generated files always contain a
root entry, so the dev snapshot's empty-file bug is left to AM-10.

## Running

```bash
python -m pytest -v
python -m pytest tests/property -v --hypothesis-show-statistics
```

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
| H-6 | Repeat H-1 while running `migrate-profile` by hand without `-a` | Dry run lists the shadow change and writes nothing | NOT RUN |
