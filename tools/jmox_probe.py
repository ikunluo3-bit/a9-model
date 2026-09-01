#!/usr/bin/env python3
"""jmox M1 探针：真实帧表 + 12B 内容哈希识别 + 未知帧 [1][2][5][6] 判型。

写入器三块前置知识：
  1. 哪些帧前缀带内容哈希、哈希函数是什么（引擎可能校验，写错就拒）
  2. [1][2] 是不是法线池（snorm16 单位长判定）
  3. [5][6] 的 UV 类流布局
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


def fnv1a64(b: bytes) -> int:
    h = 0xcbf29ce484222325
    for x in b:
        h ^= x
        h = (h * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
    return h


def fnv1a32(b: bytes) -> int:
    h = 0x811C9DC5
    for x in b:
        h ^= x
        h = (h * 0x01000193) & 0xFFFFFFFF
    return h


def main() -> int:
    data = MODEL.read_bytes()
    print(f"模型 {len(data):,}B")

    # ---- 顺序扫描 zstd magic，用前缀里的 ds 校验筛掉压缩流内伪魔数 ----
    dctx = zstd.ZstdDecompressor()
    frames = []          # (pre 24B, content)
    off = 0
    pseudo = 0
    while True:
        i = data.find(ZMAGIC, off)
        if i < 0:
            break
        do = dctx.decompressobj()
        try:
            out = do.decompress(memoryview(data)[i:])
        except Exception:
            off = i + 1
            pseudo += 1
            continue
        pre = data[max(0, i - 24):i]
        ok = False
        if len(pre) == 24:
            for ds_off in (20, 18):          # 小帧 ds 在 +20，大帧在 +18
                ds = struct.unpack_from("<I", pre, ds_off)[0]
                if ds == len(out):
                    frames.append((pre, out))
                    off = i + ((len(data) - i) - len(do.unused_data))
                    ok = True
                    break
        if not ok:
            off = i + 1
            pseudo += 1
    print(f"真实帧 {len(frames)} 个（跳过伪魔数 {pseudo}）\n")

    # ---- 帧表 ----
    for idx, (pre, out) in enumerate(frames):
        tag = "大" if len(pre) >= 22 and pre[12] == 0x01 else "小"
        print(f"[{idx:2d}] {tag} pre={pre.hex()}  ds={len(out):,}")

    # ---- 哈希识别（大帧 pre[0:12]，小帧无哈希——前缀全是计数字段） ----
    print("\n-- 哈希识别 --")
    hits = {}
    for idx, (pre, out) in enumerate(frames):
        if not (len(pre) >= 24 and pre[12] == 0x01 and pre[13] == 0x02):
            continue
        h12 = pre[:12]
        tests = {
            "md5[:12]":      hashlib.md5(out).digest()[:12],
            "sha1[:12]":     hashlib.sha1(out).digest()[:12],
            "sha256[:12]":   hashlib.sha256(out).digest()[:12],
            "sha256[16:28]": hashlib.sha256(out).digest()[16:28],
            "sha512[:12]":   hashlib.sha512(out).digest()[:12],
            "blake2b[:12]":  hashlib.blake2b(out).digest()[:12],
            "fnv64+fnv32":   struct.pack("<QI", fnv1a64(out), fnv1a32(out)),
            "crc32*3":       struct.pack("<III", zlib.crc32(out) & 0xFFFFFFFF,
                                         zlib.crc32(out, 1) & 0xFFFFFFFF,
                                         zlib.adler32(out) & 0xFFFFFFFF),
        }
        for name, dig in tests.items():
            if dig == h12:
                hits.setdefault(name, []).append(idx)
    for name, idxs in hits.items():
        print(f"  命中 {name}: {len(idxs)} 帧 {idxs[:6]}{'...' if len(idxs) > 6 else ''}")
    if not hits:
        print("  （候选哈希全部未中——需扩候选或哈希含 salt）")

    # ---- [1][2] 法线池判型：snorm16 x,y,z,(w) ÷32767 应单位长 ----
    print("\n-- [1][2] snorm16 法线判型 --")
    for idx in (1, 2):
        out = frames[idx][1]
        n = len(out) // 8
        a = np.frombuffer(out[:n * 8], dtype="<i2").reshape(n, 4)
        v = a[:, :3].astype(np.float64) / 32767.0
        ln = np.linalg.norm(v, axis=1)
        wu = np.unique(a[:, 3])
        print(f"  [{idx}] {n} 顶点  |v| 中位 {np.median(ln):.4f}  "
              f"|v|∈[0.95,1.05] 占比 {np.mean((ln > 0.95) & (ln < 1.05)) * 100:.1f}%  "
              f"w 取值 {wu[:6]}  (字节数余 {len(out) - n * 8})")

    # ---- [5][6] UV 类流判型 ----
    print("\n-- [5][6] u16 流判型 --")
    for idx in (5, 6):
        out = frames[idx][1]
        for div in (8192, 32767, 65535):
            a = np.frombuffer(out[:len(out) // 2 * 2], dtype="<u2")
            if len(a) == 0:
                continue
            v = a.astype(np.float64) / div
            if np.nanmax(v) <= 1.5:
                print(f"  [{idx}] ÷{div}: u16 值域 [0,1] 成立  max={v.max():.4f}  "
                      f"元素 {len(a):,}（{len(a)//2} 对）")
                break
        else:
            a = np.frombuffer(out[:len(out) // 2 * 2], dtype="<u2")
            print(f"  [{idx}] 非单位域  max(u16)={a.max()}")

    # ---- [0] 位置基准（供 [1] 法线与顶点对位的后续验证） ----
    out0 = frames[0][1]
    n0 = len(out0) // 8
    print(f"\n[0] 位置帧：{n0} 顶点（127,553 基准 = {n0 == 127553}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
