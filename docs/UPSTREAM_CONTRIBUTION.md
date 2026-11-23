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

## 3. Smallest reviewable upstream PR (option C: a targeted test in the repo that owns the code)

**Repository:** flipperdevices/flipperos-btrfs-tools, base `dev`.
**Change:** add one file, `tests/accountdb-merge.sh` (copy in `upstream-proposal/tests/`). It has no
dependencies beyond `sh` and `awk`, follows the `ck` style of `tests/entry-names.sh`, and checks
only the **contract** behaviour (11 checks, AM-01…AM-09). It changes no code. It works with or
without PR #4, and it does not overlap with PR #4's `tests/accountdb.sh` (empty base).

Verified here, every combination passing on `dev@bb92d87` and on PR #4 `@c8a97b0`:
`dash`, `bash`, `busybox sh` × `mawk`, `gawk`, `original-awk`, BusyBox awk (24/24 runs, 11 checks
each). `shellcheck -s sh` is clean. Against the synthetic defect it fails with exit 1 on two checks.

Suggested PR title: `tests: what the account merge keeps when a profile moves onto a newer build`

The proposed invariants (AM-11, AM-12, AM-13) are **not** in that PR. They go to the issue as questions.

## 4. Draft comment for issue #140

Post it only after the repository is public and the PR above is open. Replace the links.

> The account merge that `update-profile` runs through `migrate-profile`
> (`libs/flipper-accountdb.awk`) is where #140's credentials meet every update, and `dev` has no test
> for it, so I wrote one: <PR link>. It is one shell file in the style of `tests/entry-names.sh`
> with 11 checks of the behaviour the script's header promises: an owner password survives a
> rebuilt factory record, a lock survives, removed sudo membership stays removed, and so on. It
> passes on `dev` (bb92d87) and on #4 with dash/bash/busybox sh and mawk/gawk/busybox/one-true-awk.
>
> Running more cases turned up three behaviours I'd like a decision on rather than "fix":
>
> 1. If the owner deletes the factory `user`, the next update brings back its **shadow** record
>    with the new build's factory hash. `chpasswd` re-salts it in every build, so the record always
>    looks changed by the base (`flipper-accountdb.awk:23`). passwd/group stay deleted and
>    `check_db_pair` warns, so it is an orphan record, not a login. Should a deletion in the
>    profile win here?
> 2. With #4, when the old `_stock` lacks a database file, an owner-changed record loses to the
>    new build's (`:27`). Before #4 the shifted roles happened to keep the owner's. Intended?
> 3. For `group`/`gshadow`, every non-list field comes from the new base when both have the
>    record (`mergerec`), so a group password the owner set is dropped even if the build never
>    touched it. Intended?
>
> All three reproduce with synthetic inputs only, no hardware: <repo link>
> (`profileguard test --scenario AM-11 --scenario AM-12 --scenario AM-13`, AM-12 needs #4).
> Nothing here was run on a board.

## 5. Integration roadmap (no new framework upstream)

1. The shell test above, if maintainers want it.
2. If they decide on AM-11/AM-12, a check for the chosen behaviour in the same file, together with
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

