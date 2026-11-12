# Contributing

Issues and pull requests are welcome.

## The one rule

**Nothing from the program goes in the repository.** No Retail Plus or Visual
Objects files (EXE, DLLs, DBF tables, reports, help), no lifted C
(`src/recomp/gen/`), no catalog (`work/`), no disassembly listings, nothing
generated from `PLUSLITE.EXE`. The tool ships; its output is made on each
person's machine from their own copy. `.gitignore` covers the usual paths;
check `git status` before you commit anyway. Screenshots of it running are fine.

## Where your code comes from

Contributions must be your own or MIT-compatible. Don't port code from GPL or
LGPL projects (Wine, ReactOS, DOSBox and the like); comparing against them as a
black box is fine.

## Before a pull request

1. Build from a clean lift: `py -3 run_lift.py` (expected: `errors 0`), then
   `build.cmd`.
2. Run the conformance harness ([docs/testing.md](docs/testing.md)):
   ```
   py -3 tools\pos_diff.py
   ```
   Every line must say `IDENTICAL` (11 of 11 today). A new path through the
   program comes with a step in the script that shows it.

## Where a fix belongs

- A bug in the lifter, the catalog, the installer extractor or the native32
  bridge belongs in [pcrecomp](https://github.com/sp00nznet/pcrecomp), not
  here.
- A fix specific to Retail Plus or the VO runtime goes in `run_lift.py`,
  `seeds/` or `src/runtime/host.c`, with a comment saying what it fixes and why.
- A wall you got past goes in `docs/bringup.md`: what it looked like, what it
  was, what moved it.
