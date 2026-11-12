"""Name the runtime-DLL addresses in a --native-trace log: py -3 -I tools/annotate.py work/run.log [N]

"generated code @1004F0D0" -> "CAVORT20.DLL!INCKidStackPtr". Assumes each DLL
loaded at its preferred base (the trace prints the real address)."""
import os, re, sys
import pefile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
names = {}
game = os.path.join(ROOT, 'game')
for fn in os.listdir(game):
    if fn.upper().endswith(('.DLL', '.RDD')):
        try:
            p = pefile.PE(os.path.join(game, fn), fast_load=True)
            p.parse_data_directories([0])
            for e in p.DIRECTORY_ENTRY_EXPORT.symbols:
                names[p.OPTIONAL_HEADER.ImageBase + e.address] = '%s!%s' % (fn, (e.name or b'#%d' % e.ordinal).decode())
        except Exception:
            pass
L = open(sys.argv[1], errors='replace').read().splitlines()
n = int(sys.argv[2]) if len(sys.argv) > 2 else 80
for l in L[-n:]:
    print(re.sub(r'generated code @([0-9A-F]{8})', lambda m: names.get(int(m.group(1), 16), m.group(0)), l)[:220])
