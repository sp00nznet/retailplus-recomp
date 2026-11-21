# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.0] - 2026-11-20

### Added
- `CONTRIBUTING.md`, `CONTRIBUTORS.md`, `docs/building.md`, `docs/testing.md`,
  a hand-run installer workflow, and a `setup.sh` that says Linux and macOS
  aren't supported yet.

### Changed
- Builds against pcrecomp main; the `pcrecomp-retailplus` branch is merged.
- `NOTICE` is now `NOTICE.md`, saying what MIT covers and what it doesn't.
- Setup clones pcrecomp's `pcrecomp-retailplus` branch, and stops with the
  checkout command if `..\pcrecomp` is on another branch; the launcher uses
  the same branch. The README is in the house order.

## [0.1.0] - 2026-11-12

### Added
- `PLUSLITE.EXE` (Retail Plus Lite, 2003-12-29, CA-Visual Objects 2.x) lifted
  to C on pcrecomp's native32 host; the VO runtime DLLs run natively.
- `tools/pos_diff.py`: the conformance harness. It adds a product, rings up a
  sale and exports the inventory in the original and in the recomp, on a
  hidden desktop, and compares the DBF rows and the export.
- `tools/rp.py` (hidden-desktop launch and window-message driving),
  `tools/dbf.py` (DBF reader).
- `Setup.cmd` (`tools/setup.ps1`), taking the `Rp_lite.exe` installer
  directly (unpacked with pcrecomp's `extract_clickteam.py`, never run).
- `launcher/launcher.json`, `docs/bringup.md`.
- `run_lift.py --add`: lifts only new seeds into new chunks, so a bring-up
  round takes minutes instead of the full lift's half hour; `tools/seed_loop.ps1`
  and `tools/seeds_from_log.py` drive it. `tools/run_hidden.py` and
  `tools/annotate.py` (names runtime addresses in a `--native-trace` log).
- The host enters the VO runtime with pcrecomp's `native32_add_guest_abi`
  and points its `GetModuleFileNameA`/`GetModuleHandleA`/`LoadLibraryA` at
  the guest. The scripted add-product, sale and export match the original:
  11/11 IDENTICAL.
