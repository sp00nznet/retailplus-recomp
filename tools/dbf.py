"""Rows of a dBase III / FoxPro .DBF (stdlib only): python -I tools/dbf.py FILE"""
import struct, sys


def rows(path):
    d = open(path, 'rb').read()
    n, hl, rl = struct.unpack_from('<IHH', d, 4)
    fields, p = [], 32
    while d[p] != 0x0D:
        fields.append((d[p:p + 11].split(b'\0')[0].decode('latin1'), chr(d[p + 11]), d[p + 16]))
        p += 32
    out = []
    for i in range(n):
        r = d[hl + i * rl:hl + (i + 1) * rl]
        rec, q = {'_deleted': r[:1] == b'*'}, 1
        for name, t, ln in fields:
            rec[name] = r[q:q + ln].decode('latin1').rstrip() if t not in 'MGB' or ln != 4 else r[q:q + ln].hex()
            q += ln
        out.append(rec)
    return [f[0] for f in fields], out


if __name__ == '__main__':
    names, rs = rows(sys.argv[1])
    print(names)
    for r in rs:
        print(r)
