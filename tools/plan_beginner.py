#!/usr/bin/env python3
"""新手车提升方案：满改 + 整体拉到 A 级（普通版 LaFerrari）水平。

设计原则
  1. 满改：每个性能字段 low := high，任何升级/改装状态下都是满级性能
  2. 提升目标 = 普通版 Ferrari LaFerrari（A 级入门）的满级值
  3. 本来就强过基准的项目保留原值，不下调
  4. 只动 CarPhysics，面板(business)一个字节不碰

用法:
  python plan_beginner.py --preview          只看不改
  python plan_beginner.py --apply --out DIR  写出改好的 CarPhysics.gdb
"""
from __future__ import annotations
import argparse, hashlib, json, struct, sys, io
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

GDB = Path(r"C:\Users\player\Desktop\a9模型\gdb-6.0.0k")

# 记录偏移（6.0.0k，已用 CarDef 精确定位，避开同名前缀）
CARS = {
    "三菱 Lancer Evolution": 0x1CE90,
    "宝马 Z4 LCI E89":        0x1933C,
    "日产 370Z":              0x19BB0,
    "法拉利 LaFerrari":       0x1FBEC,   # A 级基准，自身只做满改
}
BASE = 0x1FBEC          # 提升目标 = 拉法

# 字段: 名字 -> (lo_idx, hi_idx, 方向)   方向 up = 越大越好, down = 越小越好
FIELDS = [
    ("极速",      22, 23, "up"),
    ("加速",      72, 73, "up"),
    ("抓地",      78, 79, "up"),
    ("转向锐度",  19, 21, "up"),
    ("单喷消耗",  34, 35, "down"), ("单喷加成", 36, 37, "up"), ("单喷维持", 38, 39, "up"),
    ("橙喷消耗",  42, 43, "down"), ("橙喷加成", 44, 45, "up"), ("橙喷维持", 46, 47, "up"),
    ("蓝喷消耗",  50, 51, "down"), ("蓝喷加成", 52, 53, "up"), ("蓝喷维持", 54, 55, "up"),
    ("紫喷消耗",  58, 59, "down"), ("紫喷加成", 60, 61, "up"),
]
# 阻尼单独处理：低于 0.4 的提到 0.4，改善落地姿态；已达标的不动
DAMP = [("压缩阻尼", 99), ("回弹阻尼", 100)]
DAMP_FLOOR = 0.40


def as_f32(v): return struct.unpack("<f", struct.pack("<f", v))[0]
def sha256(b): return hashlib.sha256(b).hexdigest().upper()


def build():
    raw = (GDB / "CarPhysics.gdb").read_bytes()
    buf = bytearray(raw)

    def rd(off, i, src=None):
        return struct.unpack_from("<f", src if src is not None else raw, off + i * 4)[0]

    target = {nm: rd(BASE, hi) for nm, lo, hi, d in FIELDS}
    plan = {}

    for car, off in CARS.items():
        rows = []
        for nm, lo, hi, direction in FIELDS:
            cur_hi = rd(off, hi)
            tgt = target[nm]
            if car.endswith("LaFerrari"):
                new = cur_hi                      # 基准车只满改，不改数值
            elif direction == "up":
                new = max(cur_hi, tgt)            # 已强于基准则保留
            else:
                new = min(cur_hi, tgt)            # 消耗类取更小(更省)
            rows.append(dict(field=nm, lo_idx=lo, hi_idx=hi,
                             before_lo=rd(off, lo), before_hi=cur_hi,
                             after=as_f32(new)))
        for nm, i in DAMP:
            cur = rd(off, i)
            rows.append(dict(field=nm, lo_idx=i, hi_idx=i,
                             before_lo=cur, before_hi=cur,
                             after=as_f32(max(cur, DAMP_FLOOR))))
        plan[car] = dict(offset=off, rows=rows)

    # 写入：low 与 high 同时置为 after（满改）
    touched = set()
    for car, p in plan.items():
        for r in p["rows"]:
            for idx in {r["lo_idx"], r["hi_idx"]}:
                b = p["offset"] + idx * 4
                struct.pack_into("<f", buf, b, r["after"])
                touched |= set(range(b, b + 4))

    diff = {i for i, (a, b) in enumerate(zip(raw, buf)) if a != b}
    stray = sorted(x for x in diff if x not in touched)
    if stray:
        sys.exit(f"越界改动: {[hex(x) for x in stray[:8]]}")
    return raw, bytes(buf), plan, len(diff)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--out", default=r"C:\Users\player\Desktop\a9模型\tuned-6.0.0k")
    a = ap.parse_args()
    raw, new, plan, nbytes = build()

    for car, p in plan.items():
        print(f"\n=== {car}  (记录 0x{p['offset']:X}) ===")
        print(f"  {'字段':<10}{'原 低/满':>22}{'改后(低=满)':>14}   变化")
        for r in p["rows"]:
            ratio = r["after"] / r["before_hi"] if r["before_hi"] else 1
            mark = "" if abs(ratio - 1) < 1e-6 else f"  x{ratio:.2f}"
            print(f"  {r['field']:<10}{('%.4g / %.4g' % (r['before_lo'], r['before_hi'])):>22}"
                  f"{r['after']:>14.4g}{mark}")
    print(f"\n总改动字节: {nbytes}")

    if a.apply:
        out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
        bak = out / "CarPhysics.gdb.orig"
        if not bak.exists(): bak.write_bytes(raw)
        (out / "CarPhysics.gdb").write_bytes(new)
        # CarChassis 未改动，也复制一份以便回封流程统一
        ch = (GDB / "CarChassis.gdb").read_bytes()
        (out / "CarChassis.gdb").write_bytes(ch)
        (out / "CarChassis.gdb.orig").write_bytes(ch)
        rep = {"target_baseline": "Ferrari LaFerrari (A级)",
               "changed_bytes": nbytes,
               "sha256_before": sha256(raw), "sha256_after": sha256(new),
               "cars": {c: {"offset": f"0x{p['offset']:X}", "rows": p["rows"]} for c, p in plan.items()}}
        (out / "plan-report.json").write_text(json.dumps(rep, ensure_ascii=False, indent=2),
                                              encoding="utf-8")
        print(f"\n已写出: {out}")
        print(f"  CarPhysics.gdb  {len(new):,} 字节  SHA256 {sha256(new)[:16]}...")


if __name__ == "__main__":
    main()
