#!/usr/bin/env python3
"""Nitro block analysis across all 290 cars, mapped to player-observed tiers."""
import struct, json
import numpy as np
from pathlib import Path
OUT = Path(r"C:\Users\player\Desktop\a9模型")
arch = json.load(open(OUT/"03-车辆档案"/"carphysics-428B-cohort.json", encoding="utf-8"))
cars = list(arch.values())
def col(i): return np.array([c["fields"][str(i)] for c in cars], dtype=np.float64)

BLOCKS = {1:32, 2:40, 3:48, 4:56}
LABEL  = {1:"单喷", 2:"橙喷(完美)", 3:"蓝喷(满段)", 4:"紫喷(脉冲)"}
senna = next(c for c in cars if c["record_offset"] == "0x11800")

print("=== 塞纳四组氮气块 ===")
print(f"{'块':>12} {'A_lo':>7} {'drain_lo':>9} {'drain_hi':>9} {'spd_lo':>8} {'spd_hi':>8} {'D_lo':>8} {'D_hi':>8}")
for m, b in BLOCKS.items():
    f = senna["fields"]
    print(f"{LABEL[m]:>12} {f[str(b)]:7.3f} {f[str(b+2)]:9.3f} {f[str(b+3)]:9.3f} "
          f"{f[str(b+4)]:8.3f} {f[str(b+5)]:8.3f} {f[str(b+6)]:8.1f} {f[str(b+7)]:8.1f}")

print("\n=== 全车中位数（验证排序是否普适，n=%d）===" % len(cars))
print(f"{'块':>12} {'drain_lo':>9} {'spd_lo':>8} {'D_lo':>9}")
for m, b in BLOCKS.items():
    print(f"{LABEL[m]:>12} {np.median(col(b+2)):9.3f} {np.median(col(b+4)):8.3f} {np.median(col(b+6)):9.1f}")

print("\n=== 排序一致性（多少台车满足该序）===")
d1,d2,d3,d4 = col(34),col(42),col(50),col(58)
n=len(cars)
print(f"  消耗 单<蓝<橙<紫  (d1<d3<d2<d4): {int(((d1<d3)&(d3<d2)&(d2<d4)).sum())}/{n}")
s1,s2,s3,s4 = col(36),col(44),col(52),col(60)
print(f"  加成 单<蓝<橙<紫  (s1<s3<s2<s4): {int(((s1<s3)&(s3<s2)&(s2<s4)).sum())}/{n}")
D1,D2,D3 = col(38),col(46),col(54)
print(f"  D值  蓝最大 (D3>D1>D2):          {int(((D3>D1)&(D1>D2)).sum())}/{n}")
print(f"  D值  蓝 > 橙 (D3>D2):            {int((D3>D2).sum())}/{n}")
