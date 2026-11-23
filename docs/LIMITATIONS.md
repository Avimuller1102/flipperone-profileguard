# Limitations

- **One component.** Only `libs/flipper-accountdb.awk` is executed. `migrate-profile` around it
  (btrfs send, `finalize_accountdbs`, `check_db_pair`, rsync, conflict sidecars) is not run, so a
  bug there is not caught. In particular AM-11's real-world effect depends on `check_db_pair`'s
  warning, which this project only reads in the source.
- **Synthetic inputs.** The databases are small, hand-written or generated, with placeholder
  hashes. Real images may have records (NIS `+` lines, comments, odd field counts) not covered.
- **No hardware, no PAM.** Nothing shows that sshd, `login`, PAM or SDDM treat the merged files
  as expected. See the hardware matrix in TESTING.md.
- **Policy is not decided here.** AM-11 and AM-12 are proposed invariants. Upstream may decide
  the current behaviour is intended.
- **Snapshot age.** The bundled script is `dev@bb92d87` (2026-11-10). Use `--repo` for anything
  newer; the scheduled CI job compares today's `dev` with the snapshot.
- **Platforms.** Linux and macOS. Windows only through WSL, because the upstream script needs a
  POSIX awk.
- Passing every scenario does not make a revision secure. It means these scenarios hold.
