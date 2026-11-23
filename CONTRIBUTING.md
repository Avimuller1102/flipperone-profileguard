# Contributing

1. `make install`, then `make check` must pass.
2. A new scenario states its basis. Use `contract` only when you can cite the upstream line that
   promises the behaviour; otherwise use `proposed` and explain the security reasoning in `story`.
3. Hashes in fixtures must be `$y$FAKE-…placeholder` strings. Never paste a real `/etc/shadow`.
4. If upstream behaviour changes, update the pinned expectations in
   `tests/integration/test_upstream_behaviour.py` in the same commit and say why.
5. Never present a result as coming from hardware unless it did, and record the board and image.
6. Do not weaken a trust gate to make a test pass. Code that is not bundled or merged upstream
   runs only with `--allow-unreviewed`.

Commit messages: imperative, describe the change (`scenarios: cover gshadow admin removal`).
