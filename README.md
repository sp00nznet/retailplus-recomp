# Retail Plus Lite, recompiled

Static recompilation of **Retail Plus Lite** (Retail Software, 2003), a
point-of-sale and inventory program for small shops, from its shipping Win32
executable to native C. No emulator, no wrapper DLLs.

It is pcrecomp's first **CA-Visual Objects** program: an xBase language whose
compiler produces native x86 and whose runtime is a set of DLLs
(`CAVORT20`, `CAVO2GUI`, `CAVO2RDD`, ...), with the data in dBase/FoxPro
`.DBF` tables. It was picked as a Visual Basic test and turned out not to be
one ([docs/bringup.md](docs/bringup.md)).

Built on the [pcrecomp](https://github.com/sp00nznet/pcrecomp) toolchain and
following its shared house style (layout, CLI, conformance harness), like the
other [pcrecomp projects](https://github.com/sp00nznet/pcrecomp#the-projects-that-built-this).

## What it is

A static recompilation of `PLUSLITE.EXE` (PE stamp `0x3FEFC097`,
2003-12-29). Retail Plus's own code, compiled by Visual Objects into the EXE,
is lifted to C by pcrecomp, compiled with MSVC and run on pcrecomp's
`native32` host. The Visual Objects runtime and the report DLLs that ship with
it are loaded as they are and called through the host's bridge; they call
back into the lifted code (window procedures, class methods, code blocks).

## Status: v0.1.0, alpha. It adds a product, rings up a sale and exports, and its output matches the original

| Stage | State |
|---|---|
| Version recompiled | Retail Plus Lite (`Rp_lite.exe`, Tucows 341566), shareware, run in its trial mode |
| Installer | unpacked, never run: pcrecomp `tools/assets/extract_clickteam.py` (new) |
| Function catalog (`disasm32 --tail-jumps`) | 40,826 functions, 95.8% of the code range, 9 minutes |
| Lift (`run_lift.py`) | 41,580 functions (+754 outside the catalog), 0 errors, 32 minutes, plus 19 seeds found by runs and by a scan for VO prologues (`seeds/run_seeds.json`) |
| Host (`build/retailplusrecomp.exe`, 32-bit, `native32`) | 4,816 imports bound, 0 unresolved; the VO runtime and report DLLs run natively with the guest's registers |
| Conformance harness (`tools/pos_diff.py`) | runs the whole script on the original: add a product, ring up a sale, export the inventory. **The recomp runs the same script and matches: 11/11 IDENTICAL** (every DBF and the export) |

Built and tested against pcrecomp branch `pcrecomp-retailplus` (on
`pcrecomp-ingame`), which adds the Clickteam extractor and the catalog fixes
this program needed.

## Screenshots

The inventory, running as recompiled code, after the harness's sale:

![The inventory window, recompiled](docs/screenshots/inventory.png)

## How the runtime is run

The Visual Objects runtime is not called by the C ABI (every function's
prologue calls `INCKidStackPtr` with `eax = esp` and `__chkstk`, helpers read
the caller's frame through `ebp`, results come back in `eax:edx` and in the
flags). So the host enters every DLL from the app folder with pcrecomp's
`native32_add_guest_abi`: on the guest's stack with the guest's registers,
the x87 left alone, the flags returned, and callbacks from it given the
caller's registers. Its `GetModuleFileNameA(NULL)` and `GetModuleHandleA(NULL)`
are pointed at the guest (`PLUSLITE.EXE` in the app folder), and its
`LoadLibraryA` registers the database drivers it loads later. The whole story
is in [docs/bringup.md](docs/bringup.md).

## What is not in this repo

Nothing of Retail Plus or of the Visual Objects runtime: no executable, DLL,
database, report and **no generated source**. The recompiled C is produced on
your machine from your own copy by `run_lift.py`, into `src/recomp/gen/`,
which is gitignored.

## Getting Started

You need **your own copy of Retail Plus Lite**: the `Rp_lite.exe` installer is
on the Internet Archive in the Tucows collection (item
`tucows_341566_Retail_Plus_Lite_POS_Software`). You do not have to install
it: setup unpacks it.

### Quick start: Setup.cmd

1. Put this repository and the pcrecomp toolkit side by side (below).
2. Double-click **`Setup.cmd`** and give it `Rp_lite.exe` when it asks
   (`Setup.cmd -GameDir C:\path\Rp_lite.exe` skips the question).

It checks for Python 3.10+, `pefile` and `capstone`, the pcrecomp toolkit and
the Visual Studio 2022 C++ compiler, and asks before installing any of them.
Then it unpacks the installer into `game\`, finds every function, recompiles
it and builds `build\retailplusrecomp.exe`, and leaves a **`Retail Plus
Lite`** shortcut. A rerun skips the finished steps; the details of every step
are in `setup.log`.

### Step by step

Prerequisites: Windows 10/11, **Python 3.10+**, **git**, **Visual Studio
2022** (or its Build Tools) with *Desktop development with C++*, and pcrecomp
beside this repository, on the `pcrecomp-retailplus` branch until it is
merged:

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

## Usage

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

### The conformance check

```
py -3 tools\pos_diff.py              # both, compared
py -3 tools\pos_diff.py --only orig  # just the original
```

Each program gets a fresh copy of `game\` in a temporary folder and runs on a
hidden desktop of its own (nothing shows on your screens; it works over RDP).
The same script drives both through window messages:

1. **Add a product.** File > Inventory > Open, Edit > Add Item: a STANDARD
   item `RPX1`, "RECOMP TEST WIDGET", price 12.34, 5 in stock, cost 6.00.
2. **Ring up a sale.** File > Point Of Sale, Start, scan `RPX1`, quantity 2,
   Total, Save (cash, no receipt printer).
3. **Export.** Inventory > Tools > Export Inventory to `EXPORT.CSV`.

Then it compares every DBF's rows (the inventory, the sales log `SALES001`,
the day's totals `TOTAL001`, the transaction log, setup, numbering, staff)
and the export, and prints `IDENTICAL` or `DIFFERENT` for each. The time of
day of the sale is masked; both runs are on the same day. Without
`game\PLUSLITE.EXE` it prints `skipped` and exits 0.

On the original the export shows the script worked: the new item with 3 left
in stock, 2 sold, 24.68 taken.

## License

MIT, for the code in this repository ([LICENSE](LICENSE); attribution in
[NOTICE](NOTICE)). Retail Plus Lite is (c) Retail Software and the Visual
Objects runtime (c) Computer Associates; none of either is here.
