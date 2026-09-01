#!/usr/bin/env python3
"""jmox 外科手术写入器 v3 —— 只换数据帧的 zstd 流，其余字节原封不动。

结构定论（M1-M2 探针链）：
    数据帧  [type u8][02][cs u32][ds u32][zstd 流]      前缀 10B
    绘制帧  [X..][02][cs][ds][zstd 流] + 节间裸数据       结构另考，不碰
    头部    记录表（节点+材质名），无流偏移 → 顺序解析，尺寸漂移安全

T1v3: 帧[0] 内容原样重压缩拼接（管线验证）
T2v3: 帧[0] Z×0.6（视觉验证：车变矮）
T3v3: 帧[0]+帧[4]（SU7 投影用同一管路）
"""
from __future__ import annotations
import struct, sys, io
from pathlib import Path
import numpy as np
import zstandard as zstd

if sys.platform == "win32" and not isinstance(sys.stdout, io.TextIOWrapper):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ZMAGIC = b"\x28\xb5\x2f\xfd"
_CCTX = zstd.ZstdCompressor(level=19)
_DCTX = zstd.ZstdDecompressor()


def locate_data_frames(src: bytes):
    """顺序定位 10 个数据帧。返回 [(magic, cons, ds, type, pre_start)]。"""
    out = []
    off = 0
    while len(out) < 10:
        i = src.find(ZMAGIC, off)
        if i < 0:
            break
        do = _DCTX.decompressobj()
        try:
            content = do.decompress(memoryview(src)[i:])
        except Exception:
            off = i + 1
            continue
        consumed = (len(src) - i) - len(do.unused_data)
        ds = struct.unpack_from("<I", src, i - 4)[0]
        cs = struct.unpack_from("<I", src, i - 8)[0]
        if ds == len(content) and cs == consumed:
            out.append((i, consumed, ds, src[i - 10], i - 10))
            off = i + consumed
            continue
        off = i + 1
    return out


def splice(src: bytes, edits: dict) -> bytes:
    """edits: {帧序号: 新内容}。只重压这些帧，其余字节原样。"""
    locs = locate_data_frames(src)
    out = bytearray()
    cur = 0
    for k, (magic, cons, ds, t, pre_start) in enumerate(locs):
        out += src[cur:pre_start]
        content = edits.get(k)
        if content is None:
            out += src[pre_start:magic + cons]          # 原前缀+原流
        else:
            comp = _CCTX.compress(content)
            assert len(comp) < 1 << 32
            out += bytes([t, 0x02])
            out += struct.pack("<II", len(comp), len(content))
            out += comp
        cur = magic + cons
    out += src[cur:]
    return bytes(out)


def verify(path: Path, edits: dict) -> bool:
    data = path.read_bytes()
    locs = locate_data_frames(data)
    for k, (magic, cons, ds, t, _) in enumerate(locs):
        content = _DCTX.decompressobj().decompress(memoryview(data)[magic:])
        if len(content) != ds:
            return False
        if k in edits and content != edits[k]:
            return False
        if k not in edits and k < len(ORIG) and content != ORIG[k]:
            return False
    return True


ORIG = []


def main() -> int:
    src = Path(r"build\jmox_work\amg_one.jmodel").read_bytes()
    locs = locate_data_frames(src)
    global ORIG
    ORIG = []
    for magic, cons, ds, t, ps in locs:
        ORIG.append(_DCTX.decompressobj().decompress(memoryview(src)[magic:]))
    print(f"数据帧 {len(locs)} 个，类型 {[hex(l[3]) for l in locs]}")

    pos0 = ORIG[0]
    n = len(pos0) // 8
    a = np.frombuffer(pos0, dtype="<i2").reshape(n, 4).copy()

    # T1v3 内容不变
    t1 = splice(src, {})
    Path(r"build\jmox_work\amg_t1v3.jmodel").write_bytes(t1)
    print("T1v3 纯重压缩:", f"{len(t1):,}B（原 {len(src):,}B）",
          "读回", "通过" if verify(Path(r"build\jmox_work\amg_t1v3.jmodel"), {}) else "失败")

    # T2v3 Z×0.6
    b = a.copy()
    b[:, 2] = (b[:, 2].astype(np.int64) * 6 // 10).astype(np.int16)
    b[:, 3] = 0x7FFF
    t2 = splice(src, {0: b.tobytes()})
    p = Path(r"build\jmox_work\amg_t2v3.jmodel")
    p.write_bytes(t2)
    ok = verify(p, {0: b.tobytes()})
    print("T2v3 Z×0.6:", f"{len(t2):,}B", "读回", "通过" if ok else "失败")
    return 0


if __name__ == "__main__":
    sys.exit(main())
