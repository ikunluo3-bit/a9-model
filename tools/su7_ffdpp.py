#!/usr/bin/env python3
"""FFD++ 精修投影 → 精确尺寸 → 拼接（一站式，产出 amg_ffdpp.jmodel）。

改进（对比首版 FFD）：
  * 晶格 40x20x14（更细，保留特征）
  * 晶格聚合用中值（抗离群）
  * 两轮渐进：投影→拟合→位移后再投影→再拟合
  * 轮区/远距顶点保留原位
  * R=4 坐标粗化 + 抖动精确命中 cs
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
G = (40, 20, 14)
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


def ffd_fit(P: np.ndarray, D: np.ndarray, G=G, rounds: int = 2):
    """晶格拟合 D 场（中值），返回插值函数。"""
    mn, mx = P.min(axis=0), P.max(axis=0)
    cell = (mx - mn) / np.array(G)
    lat = np.zeros((G[0], G[1], G[2], 3))
    weight = np.zeros((G[0], G[1], G[2]))
    ijk = np.clip(((P - mn) / cell).astype(np.int64), 0, np.array(G) - 1)
    for it in range(rounds):
        lat[:] = 0
        weight[:] = 0
        cur = P + D if it == 0 else P + D
        cid = ijk[:, 0] * G[1] * G[2] + ijk[:, 1] * G[2] + ijk[:, 2]
        # 中值聚合: 按格收集(内存安全: 只对非零D)
        nz = np.nonzero(np.any(D != 0, axis=1))[0]
        order = np.argsort(cid[nz], kind="stable")
        cnz = cid[nz][order]
        bounds = np.searchsorted(cnz, np.arange(G[0] * G[1] * G[2] + 1))
        dnz = D[nz][order]
        for g in range(G[0] * G[1] * G[2]):
            s, e = bounds[g], bounds[g + 1]
            if e - s >= 3:
                lat.reshape(-1, 3)[g] = np.median(dnz[s:e], axis=0)
                weight.reshape(-1)[g] = e - s
        # 填洞 + 平滑 2 轮
        lv = lat.reshape(-1, 3)
        bad = weight.reshape(-1) < 3
        if bad.any():
            t = cKDTree(lv[~bad])
            _, ni = t.query(lv[bad], k=1)
            lv[bad] = lv[~bad][ni]
        L = lv.reshape(G[0], G[1], G[2], 3)
        Lp = np.pad(L, ((1, 1), (1, 1), (1, 1), (0, 0)), mode="edge")
        L = (Lp[:-2, :-2, :-2] + Lp[:-2, :-2, 2:] + Lp[:-2, 2:, :-2] +
             Lp[2:, :-2, :-2] + Lp[:-2, 2:, 2:] + Lp[2:, :-2, 2:] +
             Lp[2:, 2:, :-2] + Lp[2:, 2:, 2:] + L * 8) / 16.0
        lat = L
        # 本轮用平滑场重算 D 的低频分量（高频保留原投影）
        f = (P - mn) / cell
        i0 = np.clip(np.floor(f).astype(np.int64), 0, np.array(G) - 2)
        tt = np.clip(f - i0, 0, 1)
        Dlow = np.zeros_like(D)
        for dx in (0, 1):
            for dy in (0, 1):
                for dz in (0, 1):
                    wgt = ((tt[:, 0] if dx else 1 - tt[:, 0]) *
                           (tt[:, 1] if dy else 1 - tt[:, 1]) *
                           (tt[:, 2] if dz else 1 - tt[:, 2]))
                    cid2 = ((i0[:, 0] + dx) * G[1] + (i0[:, 1] + dy)) * G[2] + (i0[:, 2] + dz)
                    Dlow += lat.reshape(-1, 3)[cid2] * wgt[:, None]
        D = Dlow                                             # 高频(锡纸)全弃
    return lat, mn, cell


def main() -> int:
    t0 = time.time()
    src = (WORK / "amg_one.jmodel").read_bytes()
    m0, c0, ds0, ty0, ps0 = locate_data_frames(src)[0]
    pos0 = DC.decompressobj().decompress(memoryview(src)[m0:])
    n = len(pos0) // 8
    a0 = np.frombuffer(pos0, dtype="<i2").reshape(n, 4)
    P = a0[:, :3].astype(np.float64) / 8192.0

    d = np.load(WORK / "su7_cloud.npz", allow_pickle=True)
    names = list(d["names"])
    Su = np.vstack([d[f"v{i}"] for i in range(len(names))]) * 100.0
    Su = Su[:, [0, 2, 1]]
    smin, smax = Su.min(axis=0), Su.max(axis=0)
    tmin, tmax = P.min(axis=0), P.max(axis=0)
    scale = (tmax - tmin) / (smax - smin)
    Su_t = tmin + (Su - smin) * scale
    tree = cKDTree(Su_t)

    # 轮区保护
    wc = np.array([[0.80, -1.40, -0.45], [-0.80, -1.40, -0.45],
                   [0.80, 1.40, -0.45], [-0.80, 1.40, -0.45]])
    dwheel = np.min(np.linalg.norm(P[:, None, :] - wc[None, :, :], axis=2), axis=1)
    keep = dwheel < 0.55

    # 两轮渐进投影+FFD
    D = np.zeros_like(P)
    for rnd in range(2):
        cur = P + D
        dist, idx = tree.query(cur, k=1, workers=-1)
        target = Su_t[idx]
        Dn = target - cur
        Dn[keep] = 0
        Dn[dist > 0.30] = 0
        D = D + Dn * 0.8
        lat, mn, cell = ffd_fit(P, D)
        # 用拟合场替代 D（低频由场给出，高频由投影差补充）
        f = (P - mn) / cell
        i0 = np.clip(np.floor(f).astype(np.int64), 0, np.array(G) - 2)
        tt = np.clip(f - i0, 0, 1)
        Dlow = np.zeros_like(D)
        for dx in (0, 1):
            for dy in (0, 1):
                for dz in (0, 1):
                    wgt = ((tt[:, 0] if dx else 1 - tt[:, 0]) *
                           (tt[:, 1] if dy else 1 - tt[:, 1]) *
                           (tt[:, 2] if dz else 1 - tt[:, 2]))
                    cid2 = ((i0[:, 0] + dx) * G[1] + (i0[:, 1] + dy)) * G[2] + (i0[:, 2] + dz)
                    Dlow += lat.reshape(-1, 3)[cid2] * wgt[:, None]
        D = Dlow
        print(f"轮 {rnd}: 位移中位 {np.median(np.linalg.norm(D,axis=1))*1000:.1f}mm", flush=True)

    newP = np.clip(P + D, tmin - 0.05, tmax + 0.05)
    q = np.rint(newP * 8192.0).astype(np.int64)
    q = np.clip(q, -32768, 32767).astype(np.int16)
    q4 = np.ones((n, 4), dtype=np.int16)
    q4[:, :3] = q
    q4[:, 3] = 0x7FFF
    content0 = q4.tobytes()

    # R=4 粗化
    aa = np.frombuffer(content0, dtype="<i2").reshape(n, 4).copy()
    aa[:, :3] = ((aa[:, :3].astype(np.int32) + 2) // 4) * 4
    content = aa.tobytes()

    s0 = len(CC.compress(content))
    print(f"内容压缩 {s0:,}B  目标 {c0:,}B  差 {s0-c0:+,}", flush=True)
    def make(k, seed=42):
        b = np.frombuffer(content, dtype="<i2").reshape(n, 4).copy()
        if k > 0:
            rs = np.random.default_rng(seed)
            idx2 = rs.choice(n, size=k, replace=False)
            for dim in (0, 1, 2):
                b[idx2, dim] += rs.integers(-1, 2, size=k)
            b[idx2, 3] = 0x7FFF
        return b.tobytes()
    if s0 < c0:
        lo, hi = 0, n
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if len(CC.compress(make(mid))) < c0:
                lo = mid
            else:
                hi = mid
        print(f"跨越 k={lo}..{hi}", flush=True)
        found = None
        for k in range(max(0, lo - 60), min(n, hi + 60) + 1):
            if found:
                break
            for seed in range(12):
                c = make(k, seed)
                if len(CC.compress(c)) == c0:
                    found = c
                    print(f"精确命中 k={k} seed={seed}")
                    break
        assert found, "未命中"
    else:
        # 超过目标: 提高 R
        for R in (5, 6, 8):
            bb = np.frombuffer(content0, dtype="<i2").reshape(n, 4).copy()
            bb[:, :3] = ((bb[:, :3].astype(np.int32) + R // 2) // R) * R
            c2 = bb.tobytes()
            if len(CC.compress(c2)) <= c0:
                content = c2
                break
        found = content
        print(f"用 R 粗化命中区间 (R={R})")
    comp = CC.compress(found)
    assert len(comp) == c0
    prefix = bytes([ty0, 0x02]) + struct.pack("<II", len(comp), len(found))
    out = src[:ps0] + prefix + comp + src[m0 + c0:]
    assert len(out) == len(src)
    back = DC.decompressobj().decompress(memoryview(out)[m0:])
    assert back == found
    (WORK / "amg_ffdpp.jmodel").write_bytes(out)
    print(f"FFD++ 装配完成 {len(out):,}B  总用时 {time.time()-t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
