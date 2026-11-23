# Security

This repository contains no real credentials, and the tool never reads or writes the system's
account databases.

## Running code you did not write

profileguard executes awk scripts. By default it only runs the scripts bundled with it (checked
against their released git blob ids) and commits merged into the official flipperos-btrfs-tools
repository. Anything else, such as an unmerged pull request, a fork or a local file, is refused
unless you pass `--allow-unreviewed`. Even then it runs only under `gawk --sandbox`, unless you
also pass `--allow-unsandboxed-awk`.

This is a gate, not a sandbox. Read a script before you allow it. For untrusted input, run
profileguard in a disposable VM or container. Details are in docs/ARCHITECTURE.md, "Trust
boundaries".

## Reporting

If you think you found a vulnerability **in Flipper OS** while using this tool, report it to
Flipper Devices through their own channels, not in this repository's public issues.

For a problem in this tool itself (for example, a way to make it run unreviewed code without
the flags, or to write outside its temporary directory), open a private security advisory on
this repository.
