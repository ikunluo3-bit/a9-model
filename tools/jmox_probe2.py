#!/usr/bin/env python3
"""jmox M1 探针 v2：
  A. 摘要帧 [1..8] 的 14B digest 识别（md5/sha/murmur3_128/xxh64 × 内容变体）
  B. [1][2] 按 LOD 位置帧判型（snorm16 ÷8192，看包围盒是否车形）
  C. [9] 索引帧前缀 14B 的结构化字段解读
"""
from __future__ import annotations
import struct, sys, io, hashlib, zlib
from pathlib import Path
import numpy as np
import zstandard as zstd

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

MODEL = Path(r"C:\Users\player\Desktop\a9模型\07-新游戏\extracted"
             r"\gfx3D\cars\models\Aston_Martin_Valkyrie_car.json"
             r"\_\Aston_Martin_Valkyrie_car.json.jmodel")
ZMAGIC = b"\x28\xb5\x2f\xfd"


def murmur3_x64_128(data: bytes, seed: int = 0):
    """MurmurHash3 x64 128（标准实现，LE 输出）。"""
    c1 = 0x87C37B91114253D5
    c2 = 0x4CF5AD432745937F
    length = len(data)
    h1 = h2 = seed
    nblocks = length // 16
    def rotl(x, r): return ((x << r) | (x >> (64 - r))) & 0xFFFFFFFFFFFFFFFF
    def fmix(k):
        k ^= k >> 33
        k = (k * 0xFF51AFD7ED558CCD) & 0xFFFFFFFFFFFFFFFF
        k ^= k >> 33
        k = (k * 0xC4CEB9FE1A85EC53) & 0xFFFFFFFFFFFFFFFF
        k ^= k >> 33
        return k
    for i in range(nblocks):
        k1, k2 = struct.unpack_from("<QQ", data, i * 16)
        k1 = (k1 * c1) & M64; k1 = rotl(k1, 31); k1 = (k1 * c2) & M64; h1 ^= k1
        h1 = rotl(h1, 27); h1 = (h1 + h2) & M64; h1 = (h1 * 5 + 0x52DCE729) & M64
        k2 = (k2 * c2) & M64; k2 = rotl(k2, 33); k2 = (k2 * c1) & M64; h2 ^= k2
        h2 = rotl(h2, 31); h2 = (h2 + h1) & M64; h2 = (h2 * 5 + 0x38495AB5) & M64
    tail = data[nblocks * 16:]
    k1 = k2 = 0
    for i in range(len(tail) - 1, -1, -1):
        b = tail[i]
        if i >= 8:
            k2 = (k2 << 8) | b
        else:
            k1 = (k1 << 8) | b
    if len(tail) > 8:
        k2 = (k2 * c2) & M64; k2 = rotl(k2, 33); k2 = (k2 * c1) & M64; h2 ^= k2
    if len(tail) > 0:
        k1 = (k1 * c1) & M64; k1 = rotl(k1, 31); k1 = (k1 * c2) & M64; h1 ^= k1
    h1 ^= length; h2 ^= length
    h1 = (h1 + h2) & M64; h2 = (h2 + h1) & M64
    h1 = fmix(h1); h2 = fmix(h2)
    h1 = (h1 + h2) & M64; h2 = (h2 + h1) & M64
    return struct.pack("<QQ", h1, h2)


M64 = 0xFFFFFFFFFFFFFFFF


def xxh64(data: bytes, seed: int = 0) -> int:
    P1, P2, P3, P4, P5 = 11400714785074694791, 14029467366897019727, \
        1609587929392839161, 9650029242287828579, 2870177450012600261
    M = 0xFFFFFFFFFFFFFFFF
    def rotl(x, r): return ((x << r) | (x >> (64 - r))) & M
    def round_(acc, inp):
        acc = (acc + (inp * P2)) & M
        acc = rotl(acc, 31)
        return (acc * P1) & M
    def merge(acc, val):
        acc ^= round_(0, val)
        return (acc * P1 + P4) & M
    n = len(data)
    if n >= 32:
        v1 = (seed + P1 + P2) & M
        v2 = (seed + P2) & M
        v3 = seed
        v4 = (seed - P1) & M
        i = 0
        while i + 32 <= n:
            v1 = round_(v1, struct.unpack_from("<Q", data, i)[0])
            v2 = round_(v2, struct.unpack_from("<Q", data, i + 8)[0])
            v3 = round_(v3, struct.unpack_from("<Q", data, i + 16)[0])
            v4 = round_(v4, struct.unpack_from("<Q", data, i + 24)[0])
            i += 32
        h = (rotl(v1, 1) + rotl(v2, 7) + rotl(v3, 12) + rotl(v4, 18)) & M
        h = merge(merge(merge(merge(h, v1), v2), v3), v4)
    else:
        h = (seed + P5) & M
        i = 0
    h = (h + n) & M
    while i + 8 <= n:
        h ^= round_(0, struct.unpack_from("<Q", data, i)[0])
        h = (rotl(h, 27) * P1 + P4) & M
        i += 8
    if i + 4 <= n:
        h ^= (struct.unpack_from("<I", data, i)[0] * P1) & M
        h = (rotl(h, 23) * P2 + P3) & M
        i += 4
    while i < n:
        h ^= (data[i] * P5) & M
        h = (rotl(h, 11) * P1) & M
        i += 1
    h ^= h >> 33
    h = (h * P2) & M
    h ^= h >> 29
    h = (h * P3) & M
    h ^= h >> 32
    return h


def main() -> int:
    data = MODEL.read_bytes()
    dctx = zstd.ZstdDecompressor()
    frames = []
    off = 0
    while True:
        i = data.find(ZMAGIC, off)
        if i < 0:
            break
        do = dctx.decompressobj()
        try:
            out = do.decompress(memoryview(data)[i:])
        except Exception:
            off = i + 1
            continue
        pre = data[max(0, i - 24):i]
        if len(pre) == 24:
            ds = struct.unpack_from("<I", pre, 20)[0]
            if ds == len(out):
                frames.append((pre, out))
                off = i + ((len(data) - i) - len(do.unused_data))
                continue
        off = i + 1

    # ---- A. digest 识别：载荷 = pre[0:14]，type = pre[14] ----
    print("-- A. [1..8] 14B digest 识别 --")
    def variants(content: bytes, tbyte: int):
        yield "md5[:14]", hashlib.md5(content).digest()[:14]
        yield "sha1[:14]", hashlib.sha1(content).digest()[:14]
        yield "sha256[:14]", hashlib.sha256(content).digest()[:14]
        yield "sha512[:14]", hashlib.sha512(content).digest()[:14]
        yield "blake2b[:14]", hashlib.blake2b(content).digest()[:14]
        yield "blake2s[:14]", hashlib.blake2s(content).digest()[:14]
        yield "murmur3_128[:14]", murmur3_x64_128(content)[:14]
        yield "xxh64le+xxh32c", struct.pack("<QI", xxh64(content),
                                            zlib.crc32(content) & 0xFFFFFFFF)
        yield "md5(t+c)[:14]", hashlib.md5(bytes([tbyte]) + content).digest()[:14]
        yield "sha256(t+c)[:14]", hashlib.sha256(bytes([tbyte]) + content).digest()[:14]
    hits = {}
    for idx in range(0, 10):
        pre, out = frames[idx]
        tbyte = pre[14]
        payload = pre[:14]
        if payload == b"\x00" * 14:
            print(f"  [{idx}] type={tbyte:#04x} 载荷全零（无摘要）")
            continue
        if idx == 9:
            print(f"  [{idx}] type={tbyte:#04x} 载荷结构化 {payload.hex()}（非摘要）")
            continue
        for name, dig in variants(out, tbyte):
            if dig == payload:
                hits.setdefault(name, []).append(idx)
        # 也试压缩字节
        for name, dig in variants(data[data.find(ZMAGIC, 0) + 0:], tbyte):
            pass  # 压缩变体成本高，先跳过
    for name, idxs in hits.items():
        print(f"  命中 {name}: 帧 {idxs}")
    if not hits:
        print("  14B 摘要：常规候选未中（每帧列首 8B 供人工比对）")
        for idx in range(1, 9):
            pre, _ = frames[idx]
            print(f"    [{idx}] type={pre[14]:#04x} digest={pre[:14].hex()}")

    # ---- B. [1][2] 按 LOD 位置判型：snorm16 ÷8192 包围盒 ----
    print("\n-- B. [1][2] LOD 位置判型 --")
    out0 = frames[0][1]
    p0 = np.frombuffer(out0, dtype="<i2").reshape(-1, 4)
    lo0 = (p0[:, :3].min(axis=0) / 8192.0, )
    hi0 = (p0[:, :3].max(axis=0) / 8192.0, )
    print(f"  [0] LOD0 bbox min={p0[:, :3].min(axis=0)/8192.0} max={p0[:, :3].max(axis=0)/8192.0}")
    for idx in (1, 2):
        out = frames[idx][1]
        n = len(out) // 8
        a = np.frombuffer(out[:n * 8], dtype="<i2").reshape(n, 4)
        lo = a[:, :3].min(axis=0) / 8192.0
        hi = a[:, :3].max(axis=0) / 8192.0
        wu = np.unique(a[:, 3])[:4]
        print(f"  [{idx}] {n} 顶点 bbox min={lo} max={hi}  尺寸={hi-lo}  w={wu}")

    # ---- C. [9] 索引帧前缀字段 ----
    pre9 = frames[9][0]
    print(f"\n-- C. [9] 前缀 14B = {pre9[:14].hex()}")
    f = struct.unpack("<HHIIHH", pre9[:14])
    print(f"    按 <HHIIHH 解释: {f}")
    f2 = struct.unpack("<IHHIIH", pre9[:14])
    print(f"    按 <IHHIIH 解释: {f2}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
