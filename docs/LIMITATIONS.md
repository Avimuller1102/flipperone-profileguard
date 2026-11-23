# Limitations

- **One component.** Only `libs/flipper-accountdb.awk` is executed. The rest of `migrate-profile`
  (btrfs send, `finalize_accountdbs`, `check_db_pair`, rsync, conflict sidecars) is not run, so
  a bug there is not caught.
- **Synthetic inputs.** The databases are small, hand-written or generated, with placeholder
  hashes. Records found on real images (NIS `+` lines, comments, odd field counts) are not covered.
- **No hardware, no PAM.** Nothing shows that sshd, `login`, PAM or SDDM treat the merged files
  as expected. See the hardware matrix in TESTING.md.
- **Policy is not decided here.** Scenarios marked `contract` cite what upstream documented;
  new questions start as `proposed` until upstream decides.
- **No sandbox.** Trust levels decide what may run. Process limits contain mistakes, not
  attacks. gawk `--sandbox` is the only real restriction, and it is partial. See
  ARCHITECTURE.md, "Trust boundaries".
- **Snapshot age.** The bundled script is `dev@8c9ffc7` (2026-11-23). Use `--repo` for anything
  newer. The scheduled CI job compares today's `dev` with the snapshot.
- **Platforms.** Linux and macOS are verified in CI; macOS has only its system awk, so the
  cross-awk comparison runs on Linux. Windows works only through WSL, which is untested.
- Passing every scenario does not make a revision secure; it only means these scenarios hold.
