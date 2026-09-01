#!/usr/bin/env python3
"""全库统计表生成器 —— 防止「全库最高是 XXX」这类数字过期。

任何文档里出现的全库极值/百分位，都必须由本脚本生成并带版本戳。
手写的全库数字会随版本失效，已经出过三次错：
  * 「转向锐度 56500 = 全库最高」  -> 6.0.0k 实际 98,900，56500 只到 90 百分位
  * 「抓地 1.153 = 全库最高」      -> 实际 1.300
  * 「银电蓝喷消耗 14 = 全库最低」 -> 实际 9.00（保时捷 911 GT3 RS）
第一条还被后续分析引用，得出「转向没余量可挖」的错误结论。

用法: python fleetstats.py > ../02-字段表/fleet-stats.md
"""
import sys, struct, io, bisect
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from index6 import table, build, G, TAG_PHYS

if not isinstance(sys.stdout, io.TextIOWrapper):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# 开发用参考车 / 非玩家载具 —— 会污染极值，一律剔除
NON_PLAYER = ("Fastest Car", "Slowest Car", "Invisible Car", "Police", "Traffic")


def is_np(name):
    return any(t.lower() in name.lower() for t in NON_PLAYER)


PHYS = [(23, "物理极速"), (73, "加速"), (79, "抓地"), (21, "转向锐度"),
        (77, "操控 idx77"), (76, "操控 idx76"),
        (35, "单喷消耗"), (43, "橙喷消耗"), (51, "蓝喷消耗"), (59, "紫喷消耗"),
        (53, "蓝喷加成"), (55, "蓝喷维持")]
CHAS = [(0, "质量kg"), (4, "前轮距"), (5, "后轮距"), (6, "轴距"), (14, "重心高")]

cp = (G / "CarPhysics.gdb").read_bytes()
ch = (G / "CarChassis.gdb").read_bytes()
idx = build()
offs = [d["off"] for d in table(cp)[1] if d["tag"] == TAG_PHYS and d["size"] == 428]
F = {o: struct.unpack_from("<107f", cp, o) for o in offs}
pname = {v["physics"]["off"]: k for k, v in idx.items() if "physics" in v}
coffs = sorted({v["chassis"]["off"] for v in idx.values() if "chassis" in v})
cname = {v["chassis"]["off"]: k for k, v in idx.items() if "chassis" in v}
CF = {o: struct.unpack_from("<20f", ch, o) for o in coffs}


def block(title, rows, get, keys, namemap):
    print("## " + title)
    print("")
    print("| 项 | 最低 | 最低者 | 中位 | 最高 | 最高者 |")
    print("|---|---:|---|---:|---:|---|")
    for i, lab in rows:
        vals = [(get(o, i), o) for o in keys if not is_np(namemap.get(o, ""))]
        vals.sort()
        lo, olo = vals[0]
        hi, ohi = vals[-1]
        mid = vals[len(vals) // 2][0]
        print("| %s | **%.4g** | %s | %.4g | **%.4g** | %s |"
              % (lab, lo, namemap.get(olo, "?")[:26], mid,
                 hi, namemap.get(ohi, "?")[:26]))
    print("")


def pct_table(title, idx_slot, probes, unit=""):
    col = sorted(F[o][idx_slot] for o in offs if not is_np(pname.get(o, "")))
    print("## " + title)
    print("")
    print("| 值 | 百分位 |")
    print("|---:|---:|")
    for v in probes:
        print("| %s%s | %.0f%% |" % (v, unit, 100 * bisect.bisect_left(col, v) / len(col)))
    print("")


n_real = sum(1 for o in offs if not is_np(pname.get(o, "")))
print("# 全库统计（%s）" % G.name)
print("")
print("**由 `tools/fleetstats.py` 自动生成，勿手改。**")
print("数据源 `%s/`，428B 队列 %d 台，剔除开发用参考车与非玩家载具后 %d 台。"
      % (G.name, len(offs), n_real))
print("")
print("> 引用任何「全库最高/最低」时都要连版本一起写。")
print("> 跨版本沿用手写数字已经出过三次错 —— 见 README「常见陷阱」。")
print("")

block("CarPhysics", PHYS, lambda o, i: F[o][i], offs, pname)
block("CarChassis", CHAS, lambda o, i: CF[o][i], coffs, cname)

pct_table("抓地百分位（改装选值用）", 79,
          (0.6, 0.7, 0.8, 0.9, 0.95, 1.0, 1.05, 1.1, 1.15, 1.2, 1.28, 1.3))
pct_table("转向锐度百分位", 21,
          (30000, 40000, 50000, 56500, 58000, 70000, 83000, 98900))
pct_table("蓝喷消耗百分位（越小越省）", 51,
          (9, 12, 14, 16.2, 18, 20.25, 22.5, 27, 30))
pct_table("物理极速百分位", 23, (200, 230, 250, 266, 278, 285, 300, 320, 340, 357))
