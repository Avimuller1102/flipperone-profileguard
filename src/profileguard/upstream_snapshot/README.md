# Bundled upstream snapshot

`flipper-accountdb.awk` is an unmodified copy of `libs/flipper-accountdb.awk` from
<https://github.com/flipperdevices/flipperos-btrfs-tools>, branch `dev`, commit
`8c9ffc779501da67009b77ccc0bca338549a2929` (git blob `fae7452c04333de1fabcca98b7e9e20504666913`).
It is distributed under the MIT license reproduced in `LICENSE.flipperos-btrfs-tools`,
Copyright (c) 2026 Flipper Devices.

It is bundled so that `profileguard test` runs offline. Its blob id is checked before every run.
To test a newer revision, point profileguard at a clone of the official repository:
`profileguard test --repo PATH --target origin/dev`.
