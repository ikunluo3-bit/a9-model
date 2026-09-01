#!/usr/bin/env python3
"""M4-RE1: DYNAMIC 段解析 → ZSTD* GOT 槽 → PLT 桩 → 全文件 BL 调用点。"""
from __future__ import annotations
import struct, sys, io
import numpy as np

if sys.platform == "win32" and not isinstance(sys.stdout, io.TextIOWrapper):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

SO = Path = r"build\jmox_work\libAsphalt9_600k.so"


def main() -> int:
    so = open(SO, "rb").read()
    e_shoff, = struct.unpack_from("<Q", so, 0x28)
    e_shentsize, e_shnum = struct.unpack_from("<HH", so, 0x3A)
    dyn = None
    for i in range(e_shnum):
        o = e_shoff + i * e_shentsize
        nm, typ, fl, addr, off, size = struct.unpack_from("<IIQQQQ", so, o)
        if typ == 6:  # SHT_DYNAMIC
            dyn = (addr, off, size)
    da, do, dsz = dyn
    tags = {}
    for i in range(dsz // 16):
        tag, val = struct.unpack_from("<Qq", so, do + i * 16)
        if tag == 0:
            break
        tags.setdefault(tag, val)
    DT = {5: "STRTAB", 6: "SYMTAB", 23: "JMPREL", 2: "PLTRELSZ",
          0x17: "REL", 8: "RELSZ", 7: "RELA", 1: "NEEDED"}
    print("DYNAMIC:", {DT.get(k, hex(k)): hex(v) for k, v in sorted(tags.items())})
    strtab = tags[5]
    symtab = tags[6]
    jmprel = tags.get(23)
    pltrelsz = tags.get(2, 0)

    def sym_name(idx):
        o = symtab + idx * 24
        nameoff, = struct.unpack_from("<I", so, o)
        e = so.find(b"\x00", strtab + nameoff)
        return so[strtab + nameoff:e].decode("ascii", "replace")

    # JMPREL (PLT 重定位) → 符号 → GOT 槽
    got = {}
    if jmprel:
        for i in range(pltrelsz // 24):
            ro, info, add = struct.unpack_from("<QQq", so, jmprel + i * 24)
            symidx = info >> 32
            nm = sym_name(symidx)
            if nm.startswith("ZSTD_"):
                got[nm] = ro
    for nm, slot in sorted(got.items(), key=lambda x: x[1]):
        print(f"  {nm}: GOT 0x{slot:x}")

    # PLT 桩: adrp xn, pg; ldr xn, [xn, #lo]（在 .plt 区间内找）
    w = np.frombuffer(so, dtype="<u4")
    stubs = {}
    for nm, slot in got.items():
        pg, lo = slot & ~0xFFF, slot & 0xFFF
        is_adrp = (w & 0x9F000000) == 0x90000000
        idxs = np.nonzero(is_adrp)[0]
        ww = w[idxs].astype(np.uint64)
        imm = ((ww >> 5) & 0x7FFFF) << 2 | ((ww >> 29) & 3)
        imm = np.where(imm >= (1 << 20), imm - (1 << 21), imm)
        pc = idxs.astype(np.uint64) * 4
        page = (pc & ~np.uint64(0xFFF)) + (imm << 12)
        cand = idxs[page == pg]
        n = len(w)
        for ci in cand:
            rd = int(w[ci]) & 31
            if ci + 1 >= n:
                continue
            w2 = int(w[ci + 1])
            if (w2 & 0xFFC00000) == 0xF9400000:
                if ((w2 >> 10) & 0xFFF) * 8 == lo and ((w2 >> 5) & 31) == rd:
                    stubs[nm] = ci * 4
                    break
    print("\nPLT/跳板桩:")
    for nm, s in stubs.items():
        print(f"  {nm}: 0x{s:x}")

    # 全文件扫 BL 到这些桩
    n = len(w)
    pc_all = np.arange(n, dtype=np.uint64) * 4
    print("\n调用点（JModel 区 0x4c80000-0x4d40000 高亮）:")
    for nm, T in stubs.items():
        diff = (np.int64(T) - pc_all.astype(np.int64)) >> 2
        enc = 0x94000000 | (diff.astype(np.uint64) & 0x3FFFFFF)
        idxs = np.nonzero(w == enc)[0]
        addrs = idxs * 4
        near = addrs[(addrs >= 0x4c80000) & (addrs < 0x4d40000)]
        print(f"  {nm}: 全部 {len(idxs)}  JModel区 {len(near)}",
              [hex(a) for a in near[:10]])
    return 0


if __name__ == "__main__":
    sys.exit(main())
