# Bring-up notes

What it took to get Retail Plus Lite from an installer to a recompiled
program, in the order it happened. The newest is at the bottom.

## 1. Not Visual Basic

It was picked as pcrecomp's Visual Basic runtime test. It is not a VB app.
`PLUSLITE.EXE` imports `CAVORT20.DLL`, `CAVO2GUI.DLL`, `CAVO2SYS.DLL`,
`CAVO2RDD.DLL`, `CAVO2OLE.DLL`, `CAVOOLE.DLL` and `VOCOM32.DLL`: it is a
CA-Visual Objects 2.x program. There is no `MSVBVM50/60` import and no `VB5!`
header, so the P-code-or-native question does not come up. VO compiles to
native x86, and the runtime is a set of ordinary DLLs. Its data is dBase/FoxPro
`.DBF` tables (with `.CDX` indexes and `.FPT` memos) through VO's replaceable
database drivers (`DBFCDX.RDD`, `rp2RDD32.DLL`). Its reports are ReportPro
`.RPT` files, which the `CATO3*.DLL` support DLLs run.

So the approach is the usual native32 one: lift `PLUSLITE.EXE` (Retail Plus's
own code, VO-compiled) and let the VO runtime and report DLLs run natively,
called through the bridge and calling back into lifted code.

## 2. The installer

`Rp_lite.exe` is a Clickteam Install Maker setup: a UPX-packed stub with the
payload appended behind a `wwgT)H` signature, as blocks (`u16 id, u16 flags,
u32 size`). Block `0x143A` is the file list (zlib) and `0x7F7F` the file data,
each file as `u32 size, u8 method (1 zlib, 2 bzip2), data`. pcrecomp had no
extractor for it; `tools/assets/extract_clickteam.py` is new on the
`pcrecomp-retailplus` branch. 89 files come out.

## 3. The catalog

`disasm32` on the 3.7 MB `.text` ran past 20 GB and an hour. The cause was
VO's class-init stubs: thousands of 44-byte functions, each ending in `jmp`
to the previous one. Recursive descent follows an unconditional jump as more
of the body, so every stub decoded the whole chain before it (quadratic). The
new `--tail-jumps` flag makes a jump to another first-round candidate a tail
call. A second slow spot, `drop_mid_instruction_entries`, walked every body
two or three times a round; it now walks each once. With both, the catalog
takes 9 minutes and under 2 GB: 40,826 functions, 95.8% of the code range.

## 4. The original, driven

The harness drives the original first, so the script is known to work before
the recomp is asked to run it (`tools/pos_diff.py`):

- it runs on a hidden desktop of its own (`tools/rp.py`, `CreateDesktop`),
  so nothing appears on the user's screens and it works over RDP;
- the first run creates its data (`SETUP.DBF`, `NUMBERS.DBF`, `STAFF`,
  `USERS`, the `TestData\` demo inventory) and writes `v2.dll` (the trial's
  start date, as text);
- the last-opened inventory is kept in `%WINDIR%\pluslite.INI`, which
  Windows virtualises into `%LOCALAPPDATA%\VirtualStore\Windows`. A run in a
  new folder then complains that the old inventory is missing, so the harness
  deletes that INI before each run;
- VO's edit controls take `WM_SETTEXT`, and the values reach the database;
  combo boxes need `CB_SETCURSEL` plus the `CBN_SELCHANGE` notification.

The trial needs no code: "TRIAL USER" mode starts straight into the main
window.

## 5. The lift

`run_lift.py` lifts 41,580 functions in 32 minutes, 14 million lines of C,
and the build takes about 40 minutes. Bring-up can't afford that per seed, so
`run_lift.py --add` lifts only what isn't lifted yet into new chunks and
declares them in `recomp_funcs_add.h`. `recomp_funcs.h`, which every chunk
includes, is left alone, so a round is about a minute to lift plus a minute
to build. `tools/seed_loop.ps1` repeats run, seed, `--add` and build until a
run finds nothing new.

First unresolved dispatch: `je 0x0077A9FB` at 0x004723C8, a class-init stub
jumping into the shared failure tail of a function megabytes away. The
lifter makes such a branch a tail dispatch, but nothing collected the
forward ones. pcrecomp's `true_extent(far=...)` now does, and the driver
lifts them (eight in this program).

## 6. The runtime, called the way VO calls it

Through native32's ordinary bridge (host stack, C arguments) the VO runtime
can't work:

| Symptom | Cause | Fix |
|---|---|---|
| A MessageBox titled with the bytes of a function prologue | `_NCARG` reads the caller's frame through ebp; `__chkstk` moves esp | the app-folder DLLs are entered on the guest stack with the guest's registers (`native32_add_guest_abi`) |
| "default inventory build\TestData\TSTINV.DBF cannot be found" | the runtime asks `GetModuleFileNameA(NULL)` itself and gets the host | its imports of that and `GetModuleHandleA` are pointed at the guest (host.c `patch_iat`) |
| NUMERIC OVERFLOW, FLOAT=>, argument -1.#I | loading the MMX registers marked every x87 tag valid, so the runtime's first `fld` overflowed | x87 left alone; st(0) results go onto the lifted FPU stack |
| DATA TYPE ERROR, NIL =>LOGIC at APP:START | `cb_tramp` returned the purge in edx, so the type half of every USUAL (eax:edx) a lifted method returned to the runtime was lost | the purge goes through a stack slot (every native32 host) |
| The process vanished after a first-chance 0x6BA | RPC's `__try` frames were on the guest stack, outside the TEB's bounds, so the chain counted as invalid | the TEB's bounds cover the guest stack during the call |
| "Cannot open ...TSTINV.DBF - not a DBF file" | `call _CPSE; jne` reads the string compare's answer from the flags, and the flags weren't returned | EFLAGS go back to the lifted caller |
| Callbacks into code nothing calls (0x0067CB18, 0x0078B22C) | VO methods registered by pushed address, some with VO's `push ebp; mov eax, esp` prologue the scanner doesn't look for | seeded: the runs' misses, plus a scan for `55 8B C4 BA` (14 functions) |
| Open errors on `.DBF` with no name | callbacks from the runtime pass values in eax/edx and the frame in ebp | the VEH stashes the native caller's registers and the callback starts with them |

The database drivers (`DBFCDX.RDD` and friends) are loaded later by
`CAVO2RDD`. Loading them all up front crashed in ntdll, so instead the
runtime's `LoadLibraryA` is hooked to register each one as it arrives.

## 7. Done

`tools/pos_diff.py`: the original and the recomp each add RPX1, sell two,
and export the inventory. All 11 outputs are identical: every DBF (setup,
numbering, staff, users, departments, categories, the inventory with the new
item, the sales log, the day's totals, the transaction log) and the export,
which shows `RECOMP TEST WIDGET,RPX1,...,3.00,2.00,24.68`.
