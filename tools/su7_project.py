#!/usr/bin/env python3
"""M3: SU7 表面投影 → AMG 位置帧 → 精确尺寸 jmox。

流程：
  1. SU7 点云（glb 世界空间）按轴映射 + 包围盒贴合到 AMG 空间
     （A9: X=宽, Y=车长 ±2.0, Z=上 ±0.66）
  2. cKDTree 最近点投影 AMG 165,760 顶点 → 新位置
  3. 抖动二分 + 种子轰炸，把新内容精确压到原帧 cs
  4. 外科拼接 → amg_su7.jmodel
"""
from __future__ import annotations
import struct, sys, io, time
from pathlib import Path
import numpy as np
import zstandard as zstd
from scipy.spatial import cKDTree

if sys.platform == "win32" and not isinstance(sys.stdout, io.TextIOWrapper):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ZMAGIC = b"\x28\xb5\x2f\xfd"
WORK = Path(r"build\jmox_work")
CC = zstd.ZstdCompressor(level=19)
DC = zstd.ZstdDecompressor()


def locate_data_frames(src: bytes):
    out = []
    off = 0
    while len(out) < 10:
        i = src.find(ZMAGIC, off)
        if i < 0:
            break
        do = DC.decompressobj()
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


def main() -> int:
    t0 = time.time()
    # ---- 1. AMG 原位置 ----
    src = (WORK / "amg_one.jmodel").read_bytes()
    m0, c0, ds0, t0_, ps0 = locate_data_frames(src)[0]
    pos0 = DC.decompressobj().decompress(memoryview(src)[m0:])
    n = len(pos0) // 8
    a0 = np.frombuffer(pos0, dtype="<i2").reshape(n, 4)
    P = a0[:, :3].astype(np.float64) / 8192.0
    bbox = (P.min(axis=0), P.max(axis=0))
    print(f"AMG {n} 顶点  bbox min={bbox[0].round(3)} max={bbox[1].round(3)}")

    # ---- 2. SU7 点云 → AMG 空间 ----
    d = np.load(WORK / "su7_cloud.npz", allow_pickle=True)
    names = list(d["names"])
    Su = np.vstack([d[f"v{i}"] for i in range(len(names))]) * 100.0   # 归一化还原
    # 轴映射: A9X=glbX, A9Y=glbZ, A9Z=glbY
    Su = Su[:, [0, 2, 1]]
    smin, smax = Su.min(axis=0), Su.max(axis=0)
    tmin, tmax = bbox[0], bbox[1]
    scale = (tmax - tmin) / (smax - smin)
    Su_t = tmin + (Su - smin) * scale
    print(f"SU7 {len(Su_t):,} 点  缩放 {scale.round(3)}  贴合后 bbox "
          f"{Su_t.min(axis=0).round(3)} ~ {Su_t.max(axis=0).round(3)}")

    # ---- 3. 最近点投影 ----
    tree = cKDTree(Su_t)
    dist, idx = tree.query(P, k=1, workers=-1)
    newP = Su_t[idx]
    print(f"投影完成  距离中位 {np.median(dist):.4f}m  p95 {np.percentile(dist,95):.4f}m"
          f"  用时 {time.time()-t0:.0f}s")

    # ---- 4. 量化回 i16 ----
    q = np.rint(newP * 8192.0).astype(np.int64)
    q = np.clip(q, -32768, 32767).astype(np.int16)
    content = np.hstack([q, np.full((n, 1), 0x7FFF, dtype=np.int16)]).tobytes()

    # ---- 5. 精确尺寸：三轴隐形抖动（幅值自适应）二分 + 种子轰炸 ----
    base_size = len(CC.compress(content))
    print(f"新内容 L19 压缩 {base_size:,}B  目标 {c0:,}B  差 {base_size-c0:+,}")
    cctx = zstd.ZstdCompressor(level=19)
    def make(k, J, seed=42):
        a = np.frombuffer(content, dtype="<i2").reshape(n, 4).copy()
        if k > 0:
            rs = np.random.default_rng(seed)
            idx2 = rs.choice(n, size=k, replace=False)
            for dim in (0, 1, 2):
                a[idx2, dim] += rs.integers(-J, J + 1, size=k)
            a[idx2, 3] = 0x7FFF
        return a.tobytes()
    J = 1
    while len(cctx.compress(make(n, J))) < c0:
        J *= 2
        if J > 64:
            print("幅值 64 仍不够——放弃")
            return 1
    lo, hi = 0, n
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if len(cctx.compress(make(mid, J))) < c0:
            lo = mid
        else:
            hi = mid
    print(f"幅值 ±{J} 步（±{J/8192*1000:.2f}mm）  跨越 k={lo}..{hi}")
    found = None
    for k in list(range(max(0, lo - 50), min(n, hi + 50) + 1)):
        if found:
            break
        for seed in range(12):
            c = make(k, J, seed)
            if len(cctx.compress(c)) == c0:
                found = c
                print(f"精确命中 k={k} J={J} seed={seed} cs={c0}")
                break
        if k % 10 == 0:
            print(f"  k={k} 扫过", flush=True)
    assert found, "精确尺寸未命中"
    Path(WORK / "su7_hit_content.bin").write_bytes(found)

    # ---- 6. 外科拼接 ----
    comp = cctx.compress(found)
    assert len(comp) == c0
    prefix = bytes([t0_, 0x02]) + struct.pack("<II", len(comp), len(found))
    out = src[:ps0] + prefix + comp + src[m0 + c0:]
    assert len(out) == len(src)
    (WORK / "amg_su7.jmodel").write_bytes(out)
    back = DC.decompressobj().decompress(memoryview(out)[m0:])
    print(f"拼接完成 {len(out):,}B  读回一致 {back == found}  总用时 {time.time()-t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
