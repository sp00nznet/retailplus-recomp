# Building

The by-hand route; `Setup.cmd` runs exactly these steps.

## Step by step

Prerequisites: Windows 10/11, **Python 3.10+**, **git**, **Visual Studio
2022** (or its Build Tools) with *Desktop development with C++*, and pcrecomp
beside this repository, on `main`:

```
some-folder\
  pcrecomp\                     <- git clone https://github.com/sp00nznet/pcrecomp
  retailplus\                   <- this repository
```

1. `py -3 -m pip install --user pefile capstone`
2. Unpack the installer into `game\` and copy the EXE into `work\`:
   ```
   py -3 -I ..\pcrecomp\tools\assets\extract_clickteam.py Rp_lite.exe game
   mkdir work & copy game\PLUSLITE.EXE work\
   ```
   Expected: `89 files`.
3. The function catalog (about 9 minutes, under 2 GB):
   ```
   py -3 ..\pcrecomp\tools\disasm\disasm32.py work\PLUSLITE.EXE -o work\functions.json --tail-jumps
   ```
   Expected, at the end: `[*] Functions: 40826  (thunks=5236, leaves=6882)`.
   Without `--tail-jumps` it runs for hours (docs/bringup.md, section 3).
4. Recompile to C: `py -3 run_lift.py`. (about 30 minutes)
   Expected, at the end: about `lifted 41606`, `errors 0`
   (give or take: the seeds lift in the same pass).
5. Build: `build.cmd` (about 40 minutes the first time: 700 MB of C).
6. Check it without opening a window: `build\retailplusrecomp.exe`.
7. Run it: `build\retailplusrecomp.exe --run`.

## Running

```
build\retailplusrecomp.exe --run                  # run it
build\retailplusrecomp.exe --run --watchdog 60    # stop after 60 s, saying where it was
build\retailplusrecomp.exe --run --native-trace   # one line per call out of the lifted code
py -3 tools\pos_diff.py                           # the conformance check, below
```

| Flag | |
|---|---|
| `--run` | enter the program (without it: map, bind and stop, no window) |
| `--game DIR` | the program folder (default `game`) |
| `--args "..."` | the guest's command line |
| `--watchdog S` | stop after S seconds and say where it was |
| `--native-trace`, `--callbacks` | one line per call out of the lifted code, or back into it |


## Setup.cmd

`tools/setup.ps1` does steps 1 to 5 and makes the shortcut. `-GameDir` takes the installer or a folder; `-Yes` answers every question; `-Force` redoes finished steps; `PCRECOMP` points at another toolkit checkout, which must be on `main`. Linux and macOS: not yet (`setup.sh` exits with that message).
