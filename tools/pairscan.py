#!/usr/bin/env python3
"""找出 CarPhysics 428B 记录里所有 (低级值, 满级值) 升级对。

判据（对全队列 295 台同时成立）:
  * 方向一致：要么全车 lo<=hi（越升越大），要么全车 lo>=hi（消耗类，越升越小）
    —— 允许 <=2 台例外
  * 至少 30% 的车 lo != hi（否则只是一对相等常量）
  * 比值有界（0.05 ~ 20），排掉 int 槽误读
"""
import sys, struct, statistics
sys.path.insert(0, ".")
from index6 import G, table, TAG_PHYS

cp = (G / "CarPhysics.gdb").read_bytes()
offs = [d["off"] for d in table(cp)[1] if d["tag"] == TAG_PHYS and d["size"] == 428]
F = [struct.unpack_from("<107f", cp, o) for o in offs]
n = len(F)
INT_SLOTS = {0,7,17,24,26,28,62,64,66,68,83,12,75,88,1,8,18,25,27,29,63,65,67,69,84}
KNOWN = {(22,23),(72,73),(78,79),(19,21),(14,16),(34,35),(36,37),(38,39),
         (42,43),(44,45),(46,47),(50,51),(52,53),(54,55),(58,59),(60,61)}

rows = []
for gap in (1, 2):
    for i in range(107 - gap):
        j = i + gap
        if i in INT_SLOTS or j in INT_SLOTS: continue
        lo = [r[i] for r in F]; hi = [r[j] for r in F]
        if any(h == 0 or h != h for h in hi): continue
        up = sum(1 for a, b in zip(lo, hi) if a <= b + 1e-9)
        dn = sum(1 for a, b in zip(lo, hi) if a >= b - 1e-9)
        diff = sum(1 for a, b in zip(lo, hi) if abs(a - b) > 1e-9)
        if max(up, dn) < n - 2 or diff < n * 0.30: continue
        # 两个槽都必须随车变化，否则只是两个常量凑出来的固定比值
        if len(set(lo)) < 6 or len(set(hi)) < 6: continue
        rr = [a / b for a, b in zip(lo, hi)]
        if max(rr) - min(rr) < 0.02 or max(rr) > 20: continue
        rows.append((i, j, "升" if up >= dn else "降", max(up, dn), diff,
                     statistics.median(rr), min(rr), max(rr)))

print(f"队列 {n} 台\n{'对':>9}{'方向':>5}{'一致':>8}{'lo≠hi':>8}{'比值中位':>10}{'比值范围':>18}   状态")
for i, j, d, c, df, med, mn, mx in rows:
    print(f"{i:4d}/{j:<4d}{d:>5}{c:>6}/{n}{df:>8}{med:10.3f}{f'{mn:.3f} ~ {mx:.3f}':>18}   "
          + ("已知" if (i, j) in KNOWN else "**新**"))
got = {(i, j) for i, j, *_ in rows}
print(f"\n已知对未被扫出: {sorted(KNOWN - got)}")
print(f"新发现: {sorted(got - KNOWN)}")
