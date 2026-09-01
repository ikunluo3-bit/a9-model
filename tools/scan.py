#!/usr/bin/env python3
"""Scan libAsphalt9.so .text for load/store of a given struct offset.

Usage: python scan.py <offset_hex> [x|w|s|d|q]      default: all widths
"""
import sys, numpy as np

SO = r"C:\Users\player\Desktop\A9 sifugc\project\work\apk-590301\lib\arm64-v8a\libAsphalt9.so"
TEXT_VA, TEXT_SZ = 0x3456700, 0x319ef3c

# (name, base_opcode, scale)
FORMS = {
    "x": (("LDR x", 0xF9400000, 8), ("STR x", 0xF9000000, 8)),
    "w": (("LDR w", 0xB9400000, 4), ("STR w", 0xB9000000, 4)),
    "s": (("LDR s", 0xBD400000, 4), ("STR s", 0xBD000000, 4)),
    "d": (("LDR d", 0xFD400000, 8), ("STR d", 0xFD000000, 8)),
    "q": (("LDR q", 0x3DC00000, 16), ("STR q", 0x3D800000, 16)),
}

def scan(off, widths=None):
    raw = open(SO, "rb").read()
    w = np.frombuffer(raw[TEXT_VA:TEXT_VA+TEXT_SZ], dtype=np.uint32)
    pc = TEXT_VA + np.arange(len(w), dtype=np.int64)*4
    out = {}
    for key in (widths or FORMS):
        for name, base, scale in FORMS[key]:
            if off % scale:
                continue
            imm = off // scale
            m = ((w & 0xFFC00000) == base) & (((w >> 10) & 0xFFF) == imm)
            idx = np.nonzero(m)[0]
            rows = []
            for i in idx:
                rn = int((w[i] >> 5) & 0x1F)
                if rn == 31:          # x31 == SP: stack access, not a field
                    continue
                rows.append((int(pc[i]), rn, int(w[i] & 0x1F)))
            if rows:
                out[name] = rows
    return out

if __name__ == "__main__":
    off = int(sys.argv[1], 16)
    widths = [sys.argv[2]] if len(sys.argv) > 2 else None
    res = scan(off, widths)
    total = sum(len(v) for v in res.values())
    print(f"offset 0x{off:x}: {total} non-stack sites")
    for name, rows in res.items():
        print(f"\n  {name}, [Xn,#0x{off:x}] : {len(rows)}")
        for va, rn, rt in rows[:50]:
            print(f"     0x{va:07x}   reg{rt} , x{rn}")
