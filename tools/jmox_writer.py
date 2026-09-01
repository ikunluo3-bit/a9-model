#!/usr/bin/env python3
"""jmox 写入器 + round-trip 验证（M2b/M2c）。

装配格式（M1 探针钉死）：
    [头部记录表原样][帧循环: 24B 前缀 + zstd 帧]
    前缀 = [14B 载荷][1B 类型][02][cs u32][ds u32]
    cs = 本帧压缩字节数（magic 起到帧尾），ds = 解压字节数

M2b: 原 83 帧内容原样重压缩装配 → 逐帧解压必须逐字节等于原文。
M2c: 位置帧 Z 轴压到 60% + UV 平移 0.25 → 装配写出 → 解读回读必须精确等于修改值。
"""
from __future__ import annotations
import struct, sys, io
from pathlib import Path
import numpy as np
import zstandard as zstd

if sys.platform == "win32" and not isinstance(sys.stdout, io.TextIOWrapper):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ZMAGIC = b"\x28\xb5\x2f\xfd"


def parse(data: bytes):
    dctx = zstd.ZstdDecompressor()
    header = data[: data.find(ZMAGIC) - 24]
    frames = []
    off = data.find(ZMAGIC) - 24
    while True:
        i = data.find(ZMAGIC, off)
        if i < 0:
            break
        do = dctx.decompressobj()
        out = do.decompress(memoryview(data)[i:])
        pre = bytearray(data[i - 24:i])
        cs = struct.unpack_from("<I", pre, 16)[0]
        consumed = (len(data) - i) - len(do.unused_data)
        assert cs == consumed, f"cs {cs} != consumed {consumed}"
        frames.append((pre, out))
        off = i + consumed
    return header, frames


def assemble(header: bytes, frames) -> bytes:
    out = bytearray(header)
    for pre, content in frames:
        comp = zstd.ZstdCompressor(level=19).compress(content)
        pre = bytearray(pre)
        struct.pack_into("<I", pre, 16, len(comp))
        out += pre
        out += comp
    return bytes(out)


def main() -> int:
    src = Path(r"build\jmox_work\amg_one.jmodel").read_bytes()
    header, frames = parse(src)
    print(f"头部 {len(header)}B，{len(frames)} 帧")

    # ---- M2b: 原内容 round-trip ----
    rt = assemble(header, frames)
    h2, f2 = parse(rt)
    ok = len(f2) == len(frames) and all(
        a[1] == b[1] for a, b in zip(frames, f2))
    print(f"M2b round-trip: {'通过' if ok else '失败'}"
          f"（{len(rt):,}B，原 {len(src):,}B）")

    # ---- M2c: 修改位置帧 + UV 帧，写出并读回验证 ----
    mod = [(pre, content) for pre, content in frames]
    pre0, pos = mod[0]
    n = len(pos) // 8
    a = np.frombuffer(pos, dtype="<i2").reshape(n, 4).copy()
    a[:, 2] = (a[:, 2].astype(np.int64) * 6 // 10).astype(np.int16)   # Z ×0.6
    a[:, 3] = 0x7FFF
    mod[0] = (pre0, a.tobytes())
    pre4, uv = mod[4]
    u = np.frombuffer(uv, dtype="<u2").reshape(-1, 2).copy()
    u[:, 0] = (u[:, 0].astype(np.uint32) + 8192 // 4) % 65536         # U +0.25
    mod[4] = (pre4, u.tobytes())

    out = Path(r"build\jmox_work\amg_one_squash.jmodel")
    out.write_bytes(assemble(header, mod))
    _, f3 = parse(out.read_bytes())
    chk_pos = np.frombuffer(f3[0][1], dtype="<i2").reshape(n, 4)
    expect = np.frombuffer(mod[0][1], dtype="<i2").reshape(n, 4)
    ok_pos = np.array_equal(chk_pos, expect)
    ok_uv = f3[4][1] == mod[4][1]
    z_before = np.frombuffer(frames[0][1], dtype="<i2").reshape(n, 4)[:, 2]
    print(f"M2c 修改读回: 位置 {'通过' if ok_pos else '失败'}  UV {'通过' if ok_uv else '失败'}")
    print(f"  Z 轨验证: 原 |z|max={np.abs(z_before).max()/8192:.3f}m -> "
          f"{np.abs(chk_pos[:,2]).max()/8192.0*10/6:.3f}m（应≈×0.6）")
    print(f"  产物: {out}  {out.stat().st_size:,}B")
    return 0 if (ok and ok_pos and ok_uv) else 1


if __name__ == "__main__":
    sys.exit(main())
