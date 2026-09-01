#!/usr/bin/env python3
"""Find code sites that reference a given VA (ADRP+ADD pair) in libAsphalt9.so.

Usage:  python strref.py <target_va_hex> [max_results]

Used to map stripped code back to source files via retained assert strings
(C:\asphalt9-ali\code\source\game\...).
"""
import sys, numpy as np

SO = r"C:\Users\player\Desktop\A9 sifugc\project\work\apk-590301\lib\arm64-v8a\libAsphalt9.so"
TEXT_VA, TEXT_SZ = 0x3456700, 0x319ef3c


def load():
    raw = open(SO, "rb").read()
    w = np.frombuffer(raw[TEXT_VA:TEXT_VA + TEXT_SZ], dtype=np.uint32)
    pc = TEXT_VA + np.arange(len(w), dtype=np.int64) * 4
    return raw, w, pc


def adrp_targets(w, pc):
    m = (w & 0x9F000000) == 0x90000000
    immhi = ((w >> 5) & 0x7FFFF).astype(np.int64)
    immlo = ((w >> 29) & 0x3).astype(np.int64)
    imm = (immhi << 2) | immlo
    imm = np.where(imm & (1 << 20), imm - (1 << 21), imm)
    return m, (pc & ~0xFFF) + imm * 4096


def find(target, limit=40):
    raw, w, pc = load()
    m, tgt = adrp_targets(w, pc)
    page, low = target & ~0xFFF, target & 0xFFF
    cand = np.nonzero(m & (tgt == page))[0]
    hits = []
    for i in cand:
        rd = w[i] & 0x1F
        for k in range(1, 9):                     # ADD must follow closely
            j = i + k
            if j >= len(w):
                break
            ins = w[j]
            if (ins & 0xFFC00000) == 0x91000000:  # ADD imm, shift=0
                if ((ins >> 5) & 0x1F) == rd and ((ins >> 10) & 0xFFF) == low:
                    hits.append(int(pc[i]))
                    break
    return hits


if __name__ == "__main__":
    t = int(sys.argv[1], 16)
    lim = int(sys.argv[2]) if len(sys.argv) > 2 else 40
    h = find(t, lim)
    print(f"references to 0x{t:07x}: {len(h)}")
    for a in h[:lim]:
        print(f"   0x{a:07x}")
