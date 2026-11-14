# Roadmap

## Done
- `PLUSLITE.EXE` lifted (0 errors), the VO runtime run natively, and the
  harness's add-product, sale and export identical to the original, 11 of 11.
- Setup.cmd from a fresh clone, on pcrecomp `main`.

## Next
- More of the program under the harness: clients, receive stock, the
  reports menu, Backup / Rebuild. Each new path can reach VO methods not
  yet seeded (`tools/seed_loop.ps1`).
- A printed report through ReportPro (Inventory > Reports), compared as text:
  needs a printer to capture it (Microsoft Print to PDF, or a text-only
  generic printer writing to a file).
- The receipt: Retail Plus prints it to an `LPT1:` POS printer by default
  (`pluslite.INI`, `[POS] POSPrinterPort`). Point it at a file and compare it.
- The full lift is 32 minutes and the build about 40: split `run_lift.py`
  over processes, and try `/O1` for the generated C.
- The `--native-trace` `[dll]` hooks (CreateFileA/ReadFile) are bring-up
  diagnostics; keep or drop once the harness grows.

## Then
- Headless mode in the host (`native32_headless`), so the harness and
  screenshots can run on the netlab test VMs.
- Setup.cmd and the launcher on a clean VM.
- Linux or macOS through Wine (`setup.sh` exits for now).

## Out of scope
- Rewriting or changing what Retail Plus does. The point is the original's
  output, row for row.
- The VO runtime DLLs are not lifted: they are Computer Associates' runtime,
  shipped with the app, and run as they are.
