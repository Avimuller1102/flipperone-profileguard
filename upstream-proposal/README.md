# Proposed upstream change

`tests/accountdb-merge.sh` is written to be copied as-is into
[flipperos-btrfs-tools](https://github.com/flipperdevices/flipperos-btrfs-tools) at
`tests/accountdb-merge.sh`. It needs only `sh` and `awk`, and it checks the documented contract of
`libs/flipper-accountdb.awk` (scenarios AM-01 to AM-09 of this project). See
[docs/UPSTREAM_CONTRIBUTION.md](../docs/UPSTREAM_CONTRIBUTION.md).

```bash
make upstream-sh UPSTREAM=../flipperos-btrfs-tools
AWK=gawk sh ../flipperos-btrfs-tools/tests/accountdb-merge.sh
```

Released under the MIT license like the rest of this repository, so it can be contributed under
flipperos-btrfs-tools' MIT license.
