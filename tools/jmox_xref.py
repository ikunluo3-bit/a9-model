#!/usr/bin/env python3
"""jmox 加载器定位（M3 前置）：字符串 → ADRP+ADD 引用 → 所在函数。

用法: python jmox_xref.py libAsphalt9_600k.so
"""
from __future__ import annotations
import struct, sys, io
import numpy as np

if sys.platform == "win32" and not isinstance(sys.stdout, io.TextIOWrapper):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def xref_scan(so: bytes, S: int, window: int = 8):
    w = np.frombuffer(so, dtype="<u4")
    pg, lo = S & ~0xFFF, S & 0xFFF
    is_adrp = (w & 0x9F000000) == 0x90000000
    idxs = np.nonzero(is_adrp)[0]
    ww = w[idxs].astype(np.uint64)
    imm = ((ww >> 5) & 0x7FFFF) << 2 | ((ww >> 29) & 3)
    imm = np.where(imm >= (1 << 20), imm - (1 << 21), imm)
    pc = idxs.astype(np.uint64) * 4
    page = (pc & ~np.uint64(0xFFF)) + (imm << 12)
    cand = idxs[page == pg]
    n = len(w)
    hits = []
    for ci in cand:
        rd = int(w[ci]) & 31
        for j in range(1, window + 1):
            if ci + j >= n:
                break
            w2 = int(w[ci + j])
            if (w2 & 0xFF800000) == 0x91000000:
                imm12 = (w2 >> 10) & 0xFFF
                rn = (w2 >> 5) & 31
                if imm12 == lo and rn == rd:
                    hits.append((ci * 4, rd, j))
                    break
    return hits


def main() -> int:
    so = open(r"build\jmox_work\libAsphalt9_600k.so", "rb").read()
    targets = {
        "powderFactor": 0x66ED8DC,   # 校验用（06 文档已知）
        "jmodel#1": 0x675EA37,
        "jmodel#2": 0x67984C5,
        "jmodel#3": 0x67985B1,
        "jmox": 0x66D0421,
        "jtex#1": 0x66D6A39,
        "jtex#2": 0x67E4C40,
    }
    for name, S in targets.items():
        hits = xref_scan(so, S)
        print(f"{name} @0x{S:x} -> {len(hits)} 处引用")
        for addr, rd, dist in hits[:8]:
            print(f"    code @0x{addr:x} (x{rd}, +{dist})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
