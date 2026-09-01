#!/usr/bin/env python3
"""SU7 闪电黄车漆 JTEX 重写：carpaint01_al + LOD_al。

JTEX 容器（jtex_mips 逆向）：magic \\x89jtex，w/h@27，fmt@32(25=ASTC10x10)，
镜像 w/h@51，mip 表@69：每级 [bts=u32][cs=u32][ds=u32][flag u8@+12][9B][blob]
flag 3 = zstd；blob 解压 == ds；bts = blob+22-? （blob=cs-8）
"""
from __future__ import annotations
import struct, sys, io, zipfile, subprocess, os
from pathlib import Path
import numpy as np
import zstandard as zstd
from PIL import Image

if sys.platform == "win32" and not isinstance(sys.stdout, io.TextIOWrapper):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ZMAGIC = b"\x28\xb5\x2f\xfd"
APK = Path(r"C:\Users\player\Desktop\A9 sifugc\output\A9-600300-6.0.0k-base.apk")
ASTCENC = Path(r"C:\Users\player\Desktop\A9 sifugc\project\scratch"
               r"\jtex-tools\astcenc-5.7.0\bin\astcenc-avx2.exe")
WORK = Path(r"build\jmox_work")
YELLOW = (232, 205, 40)          # SU7 Ultra 闪电黄（近似）

SWAPS = {
    # asset_id: (逻辑名, 说明)
    "397F9F2010EC1D78": "car_Mercedes_AMG_One_carpaint01_al.tga",
    "397F9D5EF2D2A414": "car_Mercedes_AMG_One_LOD_al.tga",
}


def jtex_mips(data: bytes):
    assert data.startswith(b"\x89jtex"), data[:8].hex()
    w, h = struct.unpack_from("<HH", data, 27)
    fmt = data[32]
    assert fmt == 25, fmt
    mips, off, lvl = [], 69, 0
    while off < len(data):
        bts, cs, ds = struct.unpack_from("<III", data, off)
        flag = data[off + 12]
        blob = data[off + 22: off + 22 + (ds if flag == 0 else cs - 8)]
        raw = (zstd.ZstdDecompressor().decompress(blob, max_output_size=ds)
               if flag == 3 else
               blob if flag == 0 else None)
        mips.append(dict(off=off, bts=bts, cs=cs, ds=ds, flag=flag,
                         hdr=bytes(data[off:off + 22]), raw=raw))
        off += 22 + len(blob)
        lvl += 1
    return w, h, mips


def solid_png(path: Path, w: int, h: int, rgb):
    Image.new("RGB", (max(w, 1), max(h, 1)), rgb).save(path)


def astc_payload(png_in: Path, w: int, h: int, tmp: Path) -> bytes:
    ast = tmp / f"{png_in.stem}.astc"
    if ast.exists():
        ast.unlink()
    subprocess.run([str(ASTCENC), "-cs", str(png_in), str(ast), "10x10", "-fastest"],
                   check=True, capture_output=True)
    d = ast.read_bytes()
    return d[16:]          # 去标准 ASTC 16B 头，留裸块


def rebuild_jtex(orig: bytes, yellow_rgb) -> bytes:
    w, h, mips = jtex_mips(orig)
    header = orig[:69]
    tmp = WORK / "jtex_tmp"
    tmp.mkdir(exist_ok=True)
    out = bytearray(header)
    for lvl, m in enumerate(mips):
        mw, mh = max(1, w >> lvl), max(1, h >> lvl)
        png = tmp / f"m{lvl}.png"
        solid_png(png, mw, mh, yellow_rgb)
        payload = astc_payload(png, mw, mh, tmp)
        exp = ((mw + 9) // 10) * ((mh + 9) // 10) * 16
        assert len(payload) == exp, (lvl, len(payload), exp)
        blob = zstd.ZstdCompressor(level=19).compress(payload)
        entry = bytearray(m["hdr"])                       # 22B 原头
        struct.pack_into("<I", entry, 0, len(blob) + 22)  # bts
        struct.pack_into("<I", entry, 4, len(blob) + 8)   # cs = blob+8
        entry[12] = 3                                     # 强制 zstd
        out += entry
        out += blob
    return bytes(out)


def main() -> int:
    WORK.mkdir(exist_ok=True)
    apk = zipfile.ZipFile(APK)
    for aid, lname in SWAPS.items():
        orig = apk.read("assets/main/" + aid)
        w, h, mips = jtex_mips(orig)
        print(f"{lname}: {w}x{h} {len(mips)} mips, 原 {len(orig):,}B")
        new = rebuild_jtex(orig, YELLOW)
        outp = WORK / (aid + ".jtex")
        outp.write_bytes(new)
        # 自校验
        w2, h2, m2 = jtex_mips(new)
        assert (w2, h2) == (w, h) and len(m2) == len(mips)
        print(f"  重写 {len(new):,}B  自校验通过 -> {outp.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
