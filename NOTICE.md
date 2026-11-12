# Notice

The MIT licence in [LICENSE](LICENSE) covers what is ours in this repository:
the host, the setup scripts, the tools, the harness and the documentation. It
does not cover the program.

*Retail Plus Lite* is © 2003 Retail Software, and the CA-Visual Objects
runtime it ships is © Computer Associates; neither is ours to license. Their
executables, DLLs, databases, reports and help files are not in this
repository and are excluded by `.gitignore`.

- You need your own copy of Retail Plus Lite to use any of this. Setup unpacks
  your `Rp_lite.exe` into `game/`; the pipeline reads it from there.
- Lifted code is a derivative work of the binary it came from. Anything the
  pipeline writes into `work/` or `src/recomp/gen*/` carries whatever licence
  the original carries, not this one. The MIT grant stops at our own work.
- `seeds/run_seeds.json` is 19 function addresses in `PLUSLITE.EXE` that runs
  found and the catalog missed: a list of numbers, no code or data from it.

The host started from the AmazingMIDI recomp's host (itself from the
MechWarrior 3 recomp's) and the lift driver from the Bully recomp's; all are
ours and MIT. It runs on [pcrecomp](https://github.com/sp00nznet/pcrecomp)'s
native32 runtime (MIT). No third-party code is in this repository.
