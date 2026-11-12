#!/usr/bin/env python3
"""Done check: the same POS script through the original exe and the recomp, outputs compared.

    py -3 tools/pos_diff.py [--game game] [--recomp build/retailplusrecomp.exe] [--only orig|recomp]

Each program gets a fresh copy of game\\ (the install as extracted, no data
yet) in a temporary folder, runs on a hidden desktop, and is driven through
window messages:
  1. File > Inventory > Open, Edit > Add Item: a new STANDARD item, RPX1.
  2. File > Point Of Sale: sell 2 of RPX1, total, pay cash, save.
  3. Inventory Tools > Export Inventory: the comma-delimited export.
Then the DBF rows (inventory, sales, totals, transactions) and the export
text are compared. Fields that hold today's date or the time are the same
for both runs (same day); the trial date file v2.dll is too.
Exit 0 if every output matches, or with a 'skipped' line without the program.
"""
import argparse
import ctypes
import os
import shutil
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rp    # noqa: E402
import dbf   # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WM_SETTEXT, WM_COMMAND, BM_CLICK, CB_SETCURSEL = 0x000C, 0x0111, 0x00F5, 0x014E
# ShellWindow menu
ID_POS, ID_INV_OPEN = 27479, 27481
# Inventory window menu
ID_ADD_ITEM, ID_EXPORT, ID_INV_EXIT = 1449, 1507, 1447
FOLDER = ['']                                      # the run folder, for the export path


def ctl(d, i):
    for k in rp.kids(d):
        if rp.u.GetDlgCtrlID(k) == i:
            return k
    raise KeyError('control %d' % i)


def settext(h, s):
    b = ctypes.create_unicode_buffer(s)
    rp.u.SendMessageW(h, WM_SETTEXT, 0, ctypes.addressof(b))


def top(pid, title=None, cls=None, timeout=30):
    return rp.wait(lambda: [h for h in rp.tops(pid)
                            if (title is None or rp.text(h).strip().startswith(title))
                            and (cls is None or rp.cls(h) == cls)], title or cls, timeout)[0]


def add_item(pid, main):
    rp.u.PostMessageW(main, WM_COMMAND, ID_INV_OPEN, 0)
    time.sleep(3)
    rp.u.PostMessageW(main, WM_COMMAND, ID_ADD_ITEM, 0)
    d = top(pid, 'NEW ITEM ENTRY')
    cb = ctl(d, 104)                                  # Item Type: STANDARD
    rp.u.SendMessageW(cb, CB_SETCURSEL, 0, 0)
    rp.u.SendMessageW(d, WM_COMMAND, (1 << 16) | 104, cb)
    for i, s in [(100, 'RPX1'), (101, 'RECOMP TEST WIDGET'), (102, '12.34'), (103, '5'), (109, '6.00')]:
        settext(ctl(d, i), s)
    time.sleep(0.5)
    rp.u.PostMessageW(ctl(d, 113), BM_CLICK, 0, 0)    # Save (the form clears for the next item)
    time.sleep(2)
    rp.u.PostMessageW(ctl(d, 114), BM_CLICK, 0, 0)    # Exit
    time.sleep(2)
    rp.u.PostMessageW(main, WM_COMMAND, ID_INV_EXIT, 0)


def sale(pid, main):
    rp.u.PostMessageW(main, WM_COMMAND, ID_POS, 0)
    time.sleep(3)
    pos = [k for k in rp.kids(main) if rp.text(k).strip().startswith('POS STATION')][0]
    rp.u.PostMessageW(ctl(pos, 101), BM_CLICK, 0, 0)  # F2 Start
    def scan_dlg():
        return rp.wait(lambda: [h for h in rp.tops(pid) if any(rp.text(k).startswith('Stock Code Or Scan')
                                                             for k in rp.kids(h))], 'scan')[0]
    d = scan_dlg()
    settext(ctl(d, 100), 'RPX1')
    rp.u.PostMessageW(ctl(d, 101), BM_CLICK, 0, 0)    # Enter OK
    d = top(pid, 'ITEM DETAIL')
    settext(ctl(d, 100), '2')                         # Quantity
    time.sleep(0.5)
    rp.u.PostMessageW(ctl(d, 105), BM_CLICK, 0, 0)    # Accept
    time.sleep(2)
    rp.u.PostMessageW(ctl(scan_dlg(), 105), BM_CLICK, 0, 0)   # F4 Total
    d = top(pid, 'TOTAL SALE')
    rp.u.PostMessageW(ctl(d, 130), BM_CLICK, 0, 0)    # F9 Save (no receipt printer)
    d = top(pid, 'CONFIRM')                           # "save this sale without printing it?"
    rp.u.PostMessageW(ctl(d, 1), BM_CLICK, 0, 0)
    time.sleep(3)
    rp.u.PostMessageW(ctl(pos, 104), BM_CLICK, 0, 0)  # F12 Exit


def export(pid, main):
    rp.u.PostMessageW(main, WM_COMMAND, ID_INV_OPEN, 0)
    time.sleep(3)
    rp.u.PostMessageW(main, WM_COMMAND, ID_EXPORT, 0)
    d = top(pid, 'EXPORT FILENAME')
    settext(ctl(d, 1152), os.path.join(FOLDER[0], 'EXPORT.CSV'))
    ok = [k for k in rp.kids(d) if rp.u.GetDlgCtrlID(k) == 1 and rp.cls(k) == 'Button'][0]
    rp.u.PostMessageW(ok, BM_CLICK, 0, 0)
    rp.wait(lambda: os.path.exists(os.path.join(FOLDER[0], 'EXPORT.CSV')), 'export', 20)


# GetWindowsDirectory\pluslite.INI: the app keeps its last inventory path
# there, and Windows virtualises the write into the user's VirtualStore.
INI = os.path.join(os.environ.get('LOCALAPPDATA', ''), 'VirtualStore', 'Windows', 'pluslite.INI')


def run(cmd, folder, steps, shots=None, log=None):
    if os.path.exists(INI):
        os.remove(INI)
    pid = rp.launch(cmd, folder, log=log)
    try:
        main = top(pid, cls='ShellWindow', timeout=60)
        time.sleep(2)
        for s in steps:
            try:
                s(pid, main)
            except Exception:
                rp.dump(pid)
                if shots:
                    for i, h in enumerate(rp.tops(pid)):
                        rp.snap(h, os.path.join(shots, 'fail_%d.png' % i))
                raise
            time.sleep(3)
            if shots:
                for i, h in enumerate(rp.tops(pid)):
                    rp.snap(h, os.path.join(shots, '%s_%d.png' % (s.__name__, i)))
    finally:
        rp.kill(pid)


def outputs(folder):
    out = {}
    for sub in ('TestData', '.'):
        p = os.path.join(folder, sub)
        for fn in sorted(os.listdir(p)):
            if fn.upper().endswith('.DBF'):
                names, rows = dbf.rows(os.path.join(p, fn))
                # the time of day of the sale differs between the two runs: masked
                out[os.path.join(sub, fn).upper()] = [names] + [
                    sorted((k, '<time>' if 'TIME' in k and v else v) for k, v in r.items()) for r in rows]
            elif fn.upper().endswith(('.TXT', '.DAT', '.CSV')):
                out[os.path.join(sub, fn).upper()] = open(os.path.join(p, fn), 'rb').read()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--game', default=os.path.join(ROOT, 'game'))
    ap.add_argument('--recomp', default=os.path.join(ROOT, 'build', 'retailplusrecomp.exe'))
    ap.add_argument('--only', choices=['orig', 'recomp'])
    ap.add_argument('--host-args', default='', help='more arguments for the recomp host (--native-trace)')
    ap.add_argument('--twice', action='store_true', help='the original against itself (checks the harness)')
    ap.add_argument('--keep', action='store_true', help='leave the run folders')
    ap.add_argument('--shots', help='screenshot folder')
    a = ap.parse_args()
    exe = os.path.join(a.game, 'PLUSLITE.EXE')
    if not os.path.exists(exe):
        print('skipped: no %s' % exe)
        return 0
    steps = [add_item, sale, export]
    res = {}
    for who in ('orig', 'recomp'):
        if a.only and a.only != who:
            continue
        folder = tempfile.mkdtemp(prefix='rp_%s_' % who)
        shutil.copytree(a.game, folder, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns('TestData', 'PICS', 'v2.dll', 'SETUP.DBF', 'NUMBERS.DBF',
                                                      'STAFF.*', 'USERS.*'))
        cmd = '"%s"' % os.path.join(folder, 'PLUSLITE.EXE') if who == 'orig' or a.twice else \
            '"%s" --run --game "%s" %s' % (a.recomp, folder, a.host_args)
        print('== %s in %s' % (who, folder))
        FOLDER[0] = folder
        run(cmd, folder, steps, a.shots,
            os.path.join(folder, 'recomp.log') if who == 'recomp' and not a.twice else None)
        if os.path.exists(os.path.join(folder, 'recomp.log')):     # the host's own report
            log = open(os.path.join(folder, 'recomp.log'), errors='replace').read()
            shutil.copy(os.path.join(folder, 'recomp.log'), os.path.join(ROOT, 'work', 'recomp.log'))
            print(log[-1500:])
        res[who] = outputs(folder)
        if not a.keep:
            shutil.rmtree(folder, ignore_errors=True)
    if len(res) < 2:
        for k, v in res[a.only].items():
            print(k, len(v))
        return 0
    bad = 0
    for k in sorted(set(res['orig']) | set(res['recomp'])):
        same = res['orig'].get(k) == res['recomp'].get(k)
        bad += not same
        print('%-28s %s' % (k, 'IDENTICAL' if same else 'DIFFERENT'))
    print('%d/%d identical' % (len(res['orig']) - bad, len(res['orig'])))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
