# Upstream research and scope decision

Research date: 2026-11-23. Every claim is tagged **[fact]** (read in code or on a page, with the
location given), **[interp]** (my reading of facts) or **[unverified]**.

## 1. Sources inspected

Repositories were cloned anonymously. Pull requests were fetched as `refs/pull/N/head`. GitHub issue
and PR *discussions* were read on the public web pages because the GitHub API was not available.

| Repository | Ref | Commit | Commit date |
|---|---|---|---|
| flipperdevices/flipperos-btrfs-tools | `dev` | `bb92d87252807ee306c90e9c853b8a9af84a493f` | 2026-11-10 |
| ⤷ PR #1 (miavuli, draft) | `pull/1/head` | `7ee35d460126efdbb44955180ac212e2f7f721bf` | 2026-09-10 |
| ⤷ PR #2 (rafaetri, draft) | `pull/2/head` | `8fb920a13c8f39d1ef6ca93d76fc3d86f051cf60` | 2026-11-13 |
| ⤷ PR #3 (overdeadsss, draft, changes requested) | `pull/3/head` | `d9636943c3a863f148b441a8624f0854fb780f6d` | 2026-11-03 |
| ⤷ PR #4 (rafaetri, open) | `pull/4/head` | `c8a97b063118b6065c55fdd9376c9197a4b8d46f` | 2026-11-13 |
| flipperdevices/flipperone-linux-build-scripts | `dev` | `1f8a286642c366598f9baf897be6312ad64392f9` | 2026-11-20 |
| ⤷ PR #184 (rafaetri, draft) | `pull/184/head` | `c11df7605241002da246e62ec1616e76264cc60c` | 2026-11-13 |
| ⤷ PR #202 (overdeadsss, draft) | `pull/202/head` | `cdbe18ad6200b09af2de10e549f9243de08ae2ee` | 2026-11-03 |
| flipperdevices/flipperone-testing | `dev` | `6d782afdf32158388d1f60e362c53a0fa4dfc4ff` | 2026-11-12 |
| kalicyh/flipperone-lab | `main` | `d26f193d4a8f69c727fb751b9e1b7939adf858b9` | 2026-11-20 |

Pages read: docs.flipper.net/one/how-to-join, /open-tasks, /testing/about, /dev-log (index, #6,
#10), /cpu-software/about, /cpu-software/build-system, /cpu-software/profiles,
/cpu-software/supported-boards; issue flipperone-linux-build-scripts#140; PRs listed above.

No upstream commit or PR was newer than 2026-11-20 at the time of research **[fact]**.

## 2. Architecture of profiles (answers to research questions 1-3)

- **[fact]** A profile is a btrfs subvolume holding a whole root (`/`) plus its own kernel in
  `/boot`. Profiles are created from read-only `*_stock` snapshots (docs: cpu-software/profiles).
- **[fact]** Shared between profiles: `/home`, `/var/log`, `/var/cache`, `/boot` (docs:
  cpu-software/profiles). Per profile: `/etc`, `/root`, `/var/lib` (issue #140 body).
- **[fact]** The image ships no machine-id and no SSH host keys. Each root generates them on its
  own first boot (flipperone-linux-build-scripts `debian-rk3576-ospack.yaml:299`;
  `overlays/configs/systemd/system/sshd-keygen.service.d/10-any-boot.conf`).
- **[fact]** The factory account is created at build time with
  `useradd -s /bin/bash -F -m user && echo "user:user" | chpasswd`
  (`debian-rk3576-ospack.yaml:161-162`).
- **[interp]** `chpasswd` picks a fresh salt every run, so the `user` shadow record (hash, and the
  last-change day) differs between any two builds even though the password does not.
- **[fact]** `update-profile` moves a profile onto a newer build's `_stock` by running
  `migrate-profile -a -y --keep-identity` (`scripts/update-profile:652-655`).
- **[fact]** `migrate-profile` merges `passwd`, `shadow`, `group` and `gshadow` (and their `-`
  backups) per account with `libs/flipper-accountdb.awk`. It calls it as
  `awk -v LF=… -f flipper-accountdb.awk BASE DST SRC` (`scripts/migrate-profile:421`), where BASE is
  the profile's old `_stock`, DST the new build's copy, SRC the user's profile. If BASE lacks the
  file it passes an empty file (`:401`). The old `_stock` itself must exist (`:220-221`).
- **[fact]** It rejects a merge with no `root` entry or duplicate keys (`:425-428`), drops accounts
  malformed in any database (`finalize_accountdbs`, `:446`) and warns when passwd and shadow name
  different accounts (`check_db_pair`, `:475`, called at `:747`).
- **[fact]** The script's contract is its header (`libs/flipper-accountdb.awk:3-5`): "untouched
  accounts follow the new base, user-added or changed ones ride along from src, memberships are
  set-merged".

## 3. Issue #140 and related work (questions 4-9)

- **[fact]** #140 ("Plan how credentials and device identity reach every profile after
  onboarding", opened 2026-07-29 by Yury-MonZon, labels `enhancement`, `help wanted`) asks four
  open questions: which items follow the device, push vs. pull, what happens to later profiles,
  and whether a never-onboarded profile may keep `user`/`user`. No maintainer has decided any of
  them. The only maintainer comment (alchark, 2026-07-29) adds Wi-Fi country to the list.
- **[fact]** Nothing proposed for #140 is merged. All four flipperos-btrfs-tools PRs are open;
  #1, #2 and #3 are drafts. Both build-scripts PRs (#184, #202) are drafts.

| Work | What it does | Tests it ships | Status |
|---|---|---|---|
| btrfs-tools #1 | standalone Python experiment: reconcile the owner's shadow row from shared state | 28 unit tests, 9 btrfs scenarios | draft, no review |
| btrfs-tools #2 + build #184 | `sync-identity`: one SSH host-key set in `/boot/flipper-identity`, copied into every profile | `tests/sync-identity.sh` (60 checks) | draft; reviewed by a community member |
| btrfs-tools #3 + build #202 | `sync-settings`: one Wi-Fi country | `tests/sync-settings.sh` | draft; maintainer requested changes (use flipmeta / NetworkManager) |
| btrfs-tools #4 | `flipper-accountdb.awk`: an empty file no longer shifts the roles of the files after it | `tests/accountdb.sh` (1 case) | open |
| kalicyh/flipperone-lab | containers for inspecting the public rootfs and the fake-flipctl UI | n/a | community project |
| flipperone-testing | on-device scripts (temperature, power, …) and HTML reports | on-device only | its README calls it "dirty vibe-coded" and "to be completely rewrited" |

- **[fact]** On `dev`, `flipper-accountdb.awk` has **no test at all**. The only upstream test is
  `tests/entry-names.sh`. PR #4 adds one case.
- **[fact]** flipperos-btrfs-tools has no CI workflow (`.github/` does not exist).
- **[interp]** The merge decides whether a profile keeps the owner's password or gets the factory
  one back after every `update-profile`. That is the "weakest profile decides the security of
  the device" problem of #140 in its update-time form. It runs on every update, and nothing tests it.

## 4. What can be tested where (questions 10-11)

| Without hardware (this project) | Needs a board or btrfs |
|---|---|
| `flipper-accountdb.awk` on synthetic databases: every documented rule, edge cases, every common awk | `migrate-profile` end to end (needs `btrfs send`, subvolumes, root) |
| Differences between upstream revisions of that script | `update-profile` with a real artifact server |
| Shell-level behaviour of `sync-identity` (PR #2 already does this) | Whether sshd/PAM/SDDM accept what the merge produced |
| | Boot-time ordering of the sync units |

## 5. Contribution rules (question 12)

- **[fact]** docs/how-to-join: pick tasks labelled `help wanted`, comment with contributions only
  ("no flooding"), each sub-project has its own rules. No CLA, commit convention or
  AI-assistance disclosure rule is stated there. flipperos-btrfs-tools has no CONTRIBUTING file.
  **[unverified]** whether any rule exists elsewhere (Discord, other repos).
- **[fact]** The Testing sub-project has no open `help wanted` task. The Linux sub-project has
  eight, #140 among them.

## 6. Candidate contributions (questions 13-15)

| | A. Merge-contract tests for `flipper-accountdb.awk` | B. A second harness for `sync-identity` | C. Drift auditor over a mounted image |
|---|---|---|---|
| Upstream relevance | #140; runs on every update-profile | #140 SSH half | #140 "observed drift" table |
| Duplicates existing work? | No: zero tests on dev; PR #4 adds one case | Yes: PR #2 ships 60 checks and a community review | Partly: #140's author already listed the drift by hand |
| Executes real upstream code | Yes, the exact script | Yes, but unmerged code | No, it only reads files |
| Reviewable size | ~60-line shell test upstream | — | larger, new tool |
| Hardware needed | none | none | an image or a board for real input |

**Decision: A.** It tests a security-relevant upstream component that is merged and in use and has
no tests. It runs the real code, needs nothing but awk, and its upstream form is one small shell
file in the repository's existing test style. B would duplicate PR #2's work. C would need images I
cannot produce, and it would observe drift without testing behaviour.

## 7. Results of running it (summary; full output in `examples/`)

- All nine contract scenarios pass on `dev@bb92d87` with mawk 1.3.4, gawk 5.2.1, BusyBox
  1.36.1 awk and one-true-awk 20231127, and all four give byte-identical output.
- The empty-file case (AM-10) fails on `dev`, as PR #4 describes, and passes with PR #4.
- **Finding, proposed invariant (AM-11).** If the owner deletes the factory `user` account, the next
  update brings back its *shadow* record with the new build's factory hash. This happens because
  every build re-salts that record (`flipper-accountdb.awk:23`). The passwd/group lines do not
  change between builds, so they stay deleted, and `check_db_pair` prints a warning. **[interp]**
  The result is an orphan record holding a known password, not a working login. It becomes a
  working login only if a later build changes the `user` passwd line or something re-creates the
  passwd entry. Whether deletion should win here is a policy decision for the maintainers.
- **Behaviour change, proposed invariant (AM-12).** With PR #4, when the old `_stock` lacks a
  database file, an owner-changed record loses to the new build's factory record (`:27`,
  `if (!ib) return Ol[k]`; PR #4's own test states "ours wins"). Before PR #4 the shifted roles
  happened to keep the owner's record. The case is only reachable when the `_stock` lacks the
  file, so it is an edge case.
- **Finding, proposed invariant (AM-13).** For `group`/`gshadow`, when both sides have a record,
  every non-list field comes from the new base (`mergerec`, `flipper-accountdb.awk:32-38`), even
  when the new base did not change it. A group password the owner set in `gshadow` is dropped.
  The header's "changed ones ride along" does not say whether that is meant for group fields.
