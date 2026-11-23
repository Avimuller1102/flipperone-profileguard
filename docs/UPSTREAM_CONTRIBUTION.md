# Upstream contribution plan

## 1. What is addressed

[flipperone-linux-build-scripts#140](https://github.com/flipperdevices/flipperone-linux-build-scripts/issues/140),
in its update-time form: when `update-profile` moves a profile onto a new build, does the owner's
credential state survive? The code under test is `libs/flipper-accountdb.awk` in
[flipperos-btrfs-tools](https://github.com/flipperdevices/flipperos-btrfs-tools). It is merged and
used by `migrate-profile`/`update-profile`, and it has no test on `dev`.

## 2. Comparison with what exists

| | Upstream `dev` | PR #4 | PR #1 | PR #2 | This project |
|---|---|---|---|---|---|
| Tests `flipper-accountdb.awk` | no | 1 case (empty base) | no (own Python prototype) | no | 9 contract + 4 proposed scenarios, properties |
| Runs on every awk | n/a | n/a | n/a | n/a | mawk, gawk, BusyBox, one-true-awk |
| Compares revisions | n/a | n/a | n/a | n/a | yes |
| Needs hardware | n/a | no | no (btrfs VM for part) | no | no |

flipperone-testing holds on-device scripts (thermal, power) and is unrelated to this code. Nothing
here replaces it.

## 3. Smallest reviewable upstream PR (a targeted test in the repo that owns the code)

**Repository:** flipperdevices/flipperos-btrfs-tools, base `dev`.

**Change:** one new file, `tests/accountdb-merge.sh`, copied unchanged from
`upstream-proposal/tests/`. It needs only `sh` and `awk`, follows the `ck` style of
`tests/entry-names.sh`, changes no code, and has 12 checks. Each one tests behaviour that upstream
has written down:

| Check | Upstream source |
|---|---|
| owner password kept over a rebuilt or the same factory record; locked account stays locked; account the owner added is carried | `flipper-accountdb.awk:4` "user-added or changed ones ride along from src" |
| untouched root, never-set factory account, and new build's added account follow the new base | `:4` "untouched accounts follow the new base" |
| no account twice | `:3` "entries cannot duplicate"; `migrate-profile:427-428` |
| membership removals and additions, gshadow admins and members | `:5` "memberships are set-merged", `LF=3,4` for gshadow; three-way removal per `merge_members` |

It does not cover the empty-base case (PR #4's own `tests/accountdb.sh` does), and it does not
encode the unresolved AM-11, AM-12 or AM-13. It works on `dev` with or without PR #4.

**Verified here** (Ubuntu 24.04, not in upstream CI, which does not exist): every combination
passes on `dev@bb92d87` and on PR #4 `@c8a97b0`, namely dash 0.5.12, bash 5.2 and BusyBox 1.36.1
sh × mawk 1.3.4, gawk 5.2.1, one-true-awk 20231127 and BusyBox awk (24 distinct combinations).
`shellcheck -s sh` is clean. It fails (exit 1) on the synthetic defect, exits 1 with a message if
`libs/flipper-accountdb.awk` is missing, and leaves nothing in `$TMPDIR`.

**PR title:** `tests: what the account merge keeps when a profile moves onto a newer build`

**PR description:**

> Adds `tests/accountdb-merge.sh`, 12 checks of what `libs/flipper-accountdb.awk` promises in its
> header, with the three files laid out the way `migrate-profile` passes them (old `_stock`, new
> build, profile). The image runs `chpasswd` at build time, so the factory record differs between
> any two builds. Most checks are about telling that apart from a password the owner set: the
> owner's password and lock survive a rebuilt factory record, accounts added by either side are
> kept, and membership removals hold.
>
> No code changes. Independent of #4, which has its own test for the empty-base case.
>
> Ran it with dash, bash and busybox sh, each with mawk, gawk, one-true-awk and busybox awk, on
> `dev` (bb92d87) and on #4; all pass, and shellcheck is clean. Not run on a board, but nothing
> here needs one. `AWK=gawk ./tests/accountdb-merge.sh` runs it with another awk.
>
> Part of flipperdevices/flipperone-linux-build-scripts#140.

## 4. Draft comment for issue #140

Post it only after the PR above is open. Replace `<PR link>`.

> `update-profile` runs the account merge in `libs/flipper-accountdb.awk` (via `migrate-profile`)
> on every update. That is where #140's credentials meet each new build, and `dev` has no test
> for it, so I proposed one in flipperos-btrfs-tools: <PR link>. It adds 12 checks of what the
> script's header promises and passes on `dev` and on #4.
>
> While testing more cases I hit three behaviours that look like decisions rather than bugs:
>
> 1. If the owner deletes the factory `user`, the next update brings back its **shadow** record
>    with the new build's factory hash. `chpasswd` re-salts it in every build, so the record always
>    looks changed by the base (`flipper-accountdb.awk:23`). passwd/group stay deleted and
>    `check_db_pair` warns, so this is an orphan record, not a login. Should a deletion in the
>    profile win here?
> 2. With #4 applied, when the old `_stock` lacks a database file, a record the owner changed
>    loses to the new build's (`:27`). Before #4 the shifted roles happened to keep the owner's.
>    This only happens when the `_stock` lacks the file. Is that intended?
> 3. For `group`/`gshadow`, every non-list field comes from the new base when both sides have the
>    record (`mergerec`), so a group password the owner set is dropped even if the build never
>    touched that record. Is that intended?
>
> All three reproduce with synthetic data on an ordinary machine:
> https://github.com/avimuller1102/flipperone-profileguard (`profileguard test --scenario AM-11
> --scenario AM-13`; AM-12 needs #4). Nothing was run on a board.

## 5. Integration roadmap (no new framework upstream)

1. The shell test above, if maintainers want it.
2. If they decide on AM-11/AM-12/AM-13, a check for the chosen behaviour in the same file, together with
   whoever implements it.
3. If flipperos-btrfs-tools gains CI, the test runs there like `entry-names.sh`.
4. This repository stays a place for the broader exploration (properties, cross-awk, revision
   compare). Upstream does not need to adopt Python.

## 6. Questions maintainers need to answer first

1. Should a profile's deletion (or rename) of an account survive an update when the base re-salted
   it? (AM-11)
2. With no base record, should credentials side with the profile or the new build? (AM-12)
3. Is "a never-onboarded profile follows the new factory record" (AM-03) the intended answer to
   #140 decision 4, or temporary?
4. Should non-list fields of `group`/`gshadow` that the profile changed survive? Today the new
   base's fields win whenever both have the record (`mergerec` takes them from "ours"), even when
   the new base left them unchanged. A group password the owner set in `gshadow` is dropped.
5. Is a CI workflow for flipperos-btrfs-tools welcome, or should tests stay manual?

## 7. Hardware validation

See the matrix in [TESTING.md](TESTING.md#hardware-validation-matrix-specified-not-run). It needs a
supported RK3576 board and two image builds. None of it has been run.

## 8. Later, only if 0.1 proves useful

- Scenarios for `migrate-profile --keep-identity` on a loopback btrfs in a disposable VM (the
  identity files it carries next to the account databases).
- The same revision-compare for `sync-identity` (PR #2) once it is merged, reusing its own
  `FLIPPER_TOP` test hook rather than a new harness.
- Results from someone running the hardware matrix on an RK3576 board.

