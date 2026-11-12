#!/bin/sh
# Retail Plus Lite has no Linux or macOS build yet: the host is native32, which
# runs the Visual Objects runtime DLLs natively and needs Windows. Use Setup.cmd
# on Windows. A Wine or cross-compile path is on the ROADMAP, untested.
echo "Retail Plus Lite recomp: Windows only for now. Run Setup.cmd on Windows (see README.md)." >&2
exit 1
