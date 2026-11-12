"""Add the guest addresses a run could not dispatch to seeds/run_seeds.json.

    py -3 tools/seeds_from_log.py work/recomp.log [more logs]

Reads the host's "unresolved VA 0x..." and "called guest 0x..., which is not
lifted" lines. Then `py -3 run_lift.py --add` and build.cmd."""
import json, os, re, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
path = os.path.join(ROOT, 'seeds', 'run_seeds.json')
have = set(json.load(open(path))) if os.path.exists(path) else set()
new = set()
for log in sys.argv[1:]:
    for m in re.finditer(r'(?:unresolved VA|called guest) 0x([0-9A-Fa-f]{8})', open(log, errors='replace').read()):
        a = int(m.group(1), 16)
        if 0x00401000 <= a < 0x007A0400 and a not in have:
            new.add(a)
json.dump(sorted(have | new), open(path, 'w'), indent=0)
print('%d new seeds: %s' % (len(new), ' '.join('0x%08X' % a for a in sorted(new))))
