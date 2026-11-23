# Bundled upstream snapshot

`flipper-accountdb.awk` is an unmodified copy of `libs/flipper-accountdb.awk` from
<https://github.com/flipperdevices/flipperos-btrfs-tools>, branch `dev`, commit
`bb92d87252807ee306c90e9c853b8a9af84a493f` (git blob `0533182f2d87de6d350dd45f22573122ace6e087`).
It is distributed under the MIT license reproduced in `LICENSE.flipperos-btrfs-tools`,
Copyright (c) 2026 Flipper Devices.

It is bundled so that `profileguard test` runs offline. `profileguard doctor` and the test suite
check that the file still has that blob id. To test a newer revision, point profileguard at a
checkout: `profileguard test --repo PATH --target origin/dev`.
