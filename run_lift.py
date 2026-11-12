#!/usr/bin/env python3
"""Retail Plus Lite lift driver: work/functions.json -> src/recomp/gen/.

PLUSLITE.EXE (CA-Visual Objects 2.x, native x86, base 0x00400000) is the
lifted module; the VO runtime DLLs it imports run natively. Bully's driver: every catalogued function is lifted, and catch
blocks resume inside their lifted body (pcrecomp eh32).

    py -3 run_lift.py
"""
import argparse
import json
import os
import re
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
# PCRECOMP picks the toolkit checkout, the same knob CMakeLists.txt has: the
# lifter and the runtime header must come from the same tree.
_TOOLS = os.path.join(os.environ.get('PCRECOMP', os.path.join(_HERE, '..', 'pcrecomp')), 'tools')
sys.path.insert(0, os.path.join(_TOOLS, 'lift'))
sys.path.insert(0, os.path.join(_TOOLS, 'pe'))

from capstone import Cs, CS_ARCH_X86, CS_MODE_32          # noqa: E402
from generate import (EXTENT_REACH, find_splits, true_extent,  # noqa: E402
                      linear_disassemble_function, lift_function_linear, write_chunk)
from lift32 import Lifter                                  # noqa: E402
from eh32 import resume_points                             # noqa: E402
from pe_analyze import analyze_pe, build_iat_map           # noqa: E402
import pefile                                              # noqa: E402

WORK = os.path.join(_HERE, 'work')
EXE = os.path.join(WORK, 'PLUSLITE.EXE')
OUT = os.path.join(_HERE, 'src', 'recomp', 'gen')
STAMP = 0x3FEFC097                                        # 2003-12-29, Retail Plus Lite (Tucows 341566)


def load_seeds(path):
    """Addresses from a seed file: a list of {'address': va} or of plain VAs."""
    if not os.path.exists(path):
        return set()
    return {e['address'] if isinstance(e, dict) else e for e in json.load(open(path))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--split', type=int, default=400, help='functions per .c file')
    ap.add_argument('--add', action='store_true',
                    help='lift only the seeds not lifted yet, into new chunks, and keep the rest: '
                         'a full lift takes half an hour, this a minute')
    args = ap.parse_args()
    catalog = os.path.join(WORK, 'functions.json')
    if not os.path.exists(EXE):
        sys.exit('no %s -- README, Getting started' % EXE)
    if pefile.PE(EXE, fast_load=True).FILE_HEADER.TimeDateStamp != STAMP:
        sys.exit('%s is not the Retail Plus Lite PLUSLITE.EXE (PE stamp 0x%08X expected); the README says where to get it'
                 % (EXE, STAMP))
    if not os.path.exists(catalog):
        sys.exit('no catalog at %s -- run disasm32.py first (README, Step by step)' % catalog)
    t0 = time.time()

    info = analyze_pe(EXE)
    iat = build_iat_map(info)
    cs, ce = info.code_start, info.code_end
    print('[*] base=0x%08X code=0x%08X-0x%08X IAT=%d' % (info.image_base, cs, ce, len(iat)))
    byaddr = {f['address']: f for f in json.load(open(catalog))['functions'] if cs <= f['address'] < ce}
    # Seeds: vtable slots, plus the unresolved targets runs reported
    # (seed_from_log.py -> work/run_seeds.json). Those found in bring-up are
    # kept in seeds/run_seeds.json, which is committed: addresses only, and a
    # fresh checkout has to lift the same functions.
    want = {a for a in load_seeds(os.path.join(WORK, 'seeds.json'))
            | load_seeds(os.path.join(WORK, 'run_seeds.json'))
            | load_seeds(os.path.join(_HERE, 'seeds', 'run_seeds.json'))
            if cs <= a < ce} - set(byaddr)
    for a in want:
        byaddr[a] = {'address': a, 'entry_kind': 'start'}
    print('[*] catalog %d functions, +%d seeded entries' % (len(byaddr) - len(want), len(want)))

    md = Cs(CS_ARCH_X86, CS_MODE_32)
    md.detail = True
    text = [s for s in info.sections if s.name == '.text'][0]
    code = open(EXE, 'rb').read()[text.raw_offset:text.raw_offset + text.raw_size]
    # The whole image as mapped, for the EH tables in .rdata.
    mapped = pefile.PE(EXE).get_memory_mapped_image()
    base = info.image_base
    read = lambda va, n: mapped[va - base:va - base + n] if 0 <= va - base < len(mapped) else None  # noqa: E731
    # precise carry: adc/sbb take their carry from the flag state that set it
    # (64-bit adds and subtracts; ra2's run_lift.py has the history).

    os.makedirs(OUT, exist_ok=True)
    have = set()
    if args.add:
        # A seed is an entry the catalog did not have. Lifted on its own it is
        # a body starting there; the bodies already lifted do not change (one
        # that runs through it keeps its own copy), so they are kept as they are.
        have = {int(a, 16) for a in re.findall(r'void sub_([0-9A-F]{8})\(void\);',
                                               open(os.path.join(OUT, 'recomp_funcs.h')).read()
                                               + open(os.path.join(OUT, 'recomp_funcs_add.h')).read())}
    else:
        for fn in os.listdir(OUT):                   # a smaller lift must not leave stale chunks
            if fn.startswith('recomp_') and fn.endswith('.c'):
                os.remove(os.path.join(OUT, fn))
    lifter = Lifter(iat_map=iat, lifted=set(byaddr) | have, precise_carry=True, precise_sbb=True)
    starts = {a for a in byaddr if byaddr[a].get('entry_kind') != 'alias'}
    starts -= find_splits(md, code, cs, ce, starts)   # still dispatchable, just not a wall
    # Where a function resumes after its own catch blocks. Nothing branches
    # there (the catch funclet returns the address), so the catalog often
    # starts a function at it and the parent's body stops short.
    eh_at = {}
    for a in byaddr:
        r = resume_points(md, read, list(md.disasm(read(a, 64) or b'', a))[:12])
        if r:
            eh_at[a] = r
    starts -= set().union(*eh_at.values()) if eh_at else set()

    entries, chunk, idx, errors, dirty, ehs, unimpl = [], [], 0, 0, 0, 0, {}
    # A direct branch or call to an address nothing catalogued is a tail call
    # or shared code the catalog missed; it has to be dispatchable, so each
    # round's outside targets are lifted in the next, until none are new.
    todo, added = sorted(set(byaddr) - have), 0
    if args.add:
        # Far branch targets (true_extent `far`) of the bodies lifted before
        # the lifter collected them: found once, kept in work/far.json.
        far_json = os.path.join(WORK, 'far.json')
        if not os.path.exists(far_json):
            print('[*] --add: scanning %d lifted bodies for far branch targets...' % len(have))
            found = set()
            for a in sorted(have):
                if cs <= a < ce:
                    f, reached = set(), set()
                    true_extent(md, code, cs, a, min(a + EXTENT_REACH, ce), starts, reached=reached, far=f)
                    found |= f - reached
            json.dump(sorted(found), open(far_json, 'w'))
        far_all = {t for t in json.load(open(far_json)) if cs <= t < ce and t not in have}
        for t in far_all - set(byaddr):
            byaddr[t] = {'address': t}
        todo = sorted(set(todo) | far_all)
        idx = 1 + max(int(fn[7:11]) for fn in os.listdir(OUT) if re.match(r'recomp_\d{4}\.c$', fn))
        first_new = idx
        print('[*] --add: %d lifted already, %d new, into recomp_%04d.c on' % (len(have), len(todo), idx))
    while todo:
        outside = set()
        for addr in todo:
            fname = 'sub_%08X' % addr
            reached, behind, called, far = set(), set(), set(), set()
            end, clean = true_extent(md, code, cs, addr, min(addr + EXTENT_REACH, ce), starts,
                                     reached=reached, behind=behind, called=called, far=far)
            for r in eh_at.get(addr, ()):
                if cs <= r < ce:
                    e2, _ = true_extent(md, code, cs, r, min(r + EXTENT_REACH, ce), starts,
                                        reached=reached, behind=behind, called=called, far=far)
                    end = max(end, e2)
            outside |= {t for t in behind | far if t not in reached} | called
            dirty += not clean
            try:
                lo = min(reached) if reached else addr
                insns, leaders = (linear_disassemble_function(md, code, cs, lo, end, reached=reached)
                                  if end > addr else ([], None))
                if leaders is not None:
                    leaders.add(addr)
                eh = eh_at.get(addr)
                ehs += bool(eh)
                body = (lift_function_linear(lifter, fname, insns, leaders, addr, eh_resume=eh) if insns
                        else 'void %s(void) { }\n' % fname)
            except Exception as e:                  # noqa: BLE001 -- counted, not hidden
                body = '/* ERROR %s: %s */\nvoid %s(void) { }\n' % (fname, e, fname)
                errors += 1
            for m in re.findall(r'UNIMPLEMENTED: (\w+)', body):   # lifted as a no-op: says so
                unimpl[m] = unimpl.get(m, 0) + 1
            chunk.append((body, addr, fname))
            entries.append(addr)
            if len(chunk) >= args.split:
                write_chunk(OUT, idx, chunk)
                idx, chunk = idx + 1, []
                print('[*]   %d lifted (%d err)' % (len(entries), errors), flush=True)
        todo = sorted(t for t in outside if cs <= t < ce and t not in byaddr and t not in have)
        for t in todo:
            byaddr[t] = {'address': t}
        added += len(todo)
    if chunk:
        write_chunk(OUT, idx, chunk)
        idx += 1

    entry = info.image_base + info.entry_point_rva
    entries = sorted(set(entries) | have)
    funcs_h = os.path.join(OUT, 'recomp_funcs.h')
    add_h = os.path.join(OUT, 'recomp_funcs_add.h')
    if args.add:
        # recomp_funcs.h stays as the full lift wrote it: every chunk includes
        # it, and touching it rebuilds all of them (an hour). What --add lifts
        # is declared in recomp_funcs_add.h, which only its chunks and the
        # dispatch table include; the old chunks reach it through the table.
        base = {int(x, 16) for x in re.findall(r'void sub_([0-9A-F]{8})\(void\);', open(funcs_h).read())}
        with open(add_h, 'w', newline='\n') as f:
            f.write('/* PLUSLITE.EXE --add - AUTO-GENERATED by run_lift.py */\n#pragma once\n'
                    + ''.join('void sub_%08X(void);\n' % x for x in entries if x not in base))
        for fn in os.listdir(OUT):
            m = re.match(r'recomp_(\d{4})\.c$', fn)
            if m and int(m.group(1)) >= first_new:
                path = os.path.join(OUT, fn)
                body = open(path).read()
                if 'recomp_funcs_add.h' not in body:
                    open(path, 'w', newline='\n').write(body.replace(
                        '#include "recomp_funcs.h"\n', '#include "recomp_funcs.h"\n#include "recomp_funcs_add.h"\n', 1))
    else:
        with open(funcs_h, 'w', newline='\n') as f:
            f.write('/* PLUSLITE.EXE - AUTO-GENERATED by run_lift.py */\n#pragma once\n#include <stdint.h>\n\n'
                    + ''.join('void sub_%08X(void);\n' % a for a in entries))
        open(add_h, 'w', newline='\n').write('#pragma once\n')
    with open(os.path.join(OUT, 'recomp_dispatch.c'), 'w', newline='\n') as f:
        f.write('/* PLUSLITE.EXE - AUTO-GENERATED by run_lift.py */\n'
                '#include "recomp_types.h"\n#include "recomp_funcs.h"\n#include "recomp_funcs_add.h"\n\n'
                'const recomp_dispatch_entry_t recomp_dispatch_table[] = {\n'
                + ''.join('    { 0x%08Xu, sub_%08X },\n' % (a, a) for a in entries)
                + '};\nconst uint32_t recomp_dispatch_count = %d;\n'
                  'const uint32_t rp_entry_va = 0x%08Xu;\n' % (len(entries), entry))

    lines = sum(sum(1 for _ in open(os.path.join(OUT, fn), encoding='utf-8', errors='replace'))
                for fn in os.listdir(OUT))
    stats = {'lifted': len(entries), 'added': added, 'errors': errors, 'no_terminator': dirty,
             'catch': ehs, 'files': idx, 'lines': lines, 'unimplemented': unimpl}
    json.dump(stats, open(os.path.join(WORK, 'lift_stats.json'), 'w'), indent=1)
    print('=' * 60)
    print('  lifted %d (+%d outside the catalog)   errors %d   no terminator %d   catch %d'
          % (len(entries), added, errors, dirty, ehs))
    if unimpl:
        print('  unimplemented: ' + ' '.join('%s %d' % kv for kv in sorted(unimpl.items(), key=lambda kv: -kv[1])))
    print('  %s lines of C in %d files, %.0fs' % (format(lines, ','), idx, time.time() - t0))
    print('=' * 60)


if __name__ == '__main__':
    main()
