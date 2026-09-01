#!/usr/bin/env python3
"""Query a car's physics profile.  Usage: python car.py <name> [compare_name ...]"""
import json, sys
import numpy as np
from pathlib import Path

OUT = Path(r"C:\Users\player\Desktop\a9模型")
arch = json.load(open(OUT/"03-车辆档案"/"carphysics-428B-cohort.json", encoding="utf-8"))
flds = {r["idx"]: r for r in json.load(open(OUT/"02-字段表"/"carphysics-107-fields.json", encoding="utf-8"))}
named = {k: v for k, v in arch.items() if v["name"]}

def find(q):
    q = q.lower()
    hit = [(k, v) for k, v in named.items() if q in v["name"].lower()]
    if not hit: sys.exit(f"no car matching {q!r}")
    return hit[0]

def col(i):
    return np.array([v["fields"][str(i)] for v in named.values()], dtype=np.float64)

def pct(i, val):
    c = col(i)
    return 100.0 * float((c < val).sum()) / len(c)

KEY = [(23,"极速参数 ground_speed"),(79,"抓地 tyre_force"),(73,"加速 accel"),
       (61,"氮气加成 mode4"),(59,"氮气消耗 mode4"),(99,"压缩阻尼"),(100,"回弹阻尼"),
       (87,"未知-87"),(77,"未知-77"),(76,"未知-76"),(24,"未知-24 int64"),
       (26,"未知-26 int64"),(28,"未知-28 int64"),(16,"未知-16"),(21,"未知-21"),(31,"未知-31")]

targets = [find(a) for a in sys.argv[1:]] or [find("senna")]
print(f"{'字段':<26}", end="")
for k, v in targets: print(f"{v['name'][:20]:>22}", end="")
print()
print("-"*(26+22*len(targets)))
for i, label in KEY:
    print(f"{label:<26}", end="")
    for k, v in targets:
        val = v["fields"][str(i)]
        print(f"{val:>14.4g} ({pct(i,val):3.0f}%)", end="")
    print()
print()
for k, v in targets:
    b = v["business"]
    if b: print(f"{v['name']}: 面板 rank={b['rank_hi']} 极速={b['ts_hi']}  记录 {v['record_offset']}")
print(f"\n(百分位 = 在 {len(named)} 台有面板数据的车中的排名位置)")
