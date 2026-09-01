#!/usr/bin/env python3
"""HUD 实测库：记录 / 拟合 / 反查。

只有比赛中 HUD 实读的数字才算数。面板值另存对照，不参与拟合。

用法:
  python hud.py add --car "BMW Z4" --physical 357 --hud 556 --condition "改造版直线"
  python hud.py list
  python hud.py fit
  python hud.py predict 350        # 想要 HUD 350，物理该填多少
"""
from __future__ import annotations
import argparse, json, sys, io
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DB = Path(r"C:\Users\player\Desktop\a9模型\05-HUD实测库\hud-data.json")
MIN_POINTS = 5          # 少于这个数不宣称关系已确定


def load():
    if not DB.exists():
        return {"points": []}
    return json.loads(DB.read_text(encoding="utf-8"))


def save(d):
    DB.parent.mkdir(parents=True, exist_ok=True)
    DB.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")


def cmd_add(a):
    d = load()
    d["points"].append(dict(car=a.car, physical=a.physical, hud=a.hud,
                            panel=a.panel, condition=a.condition,
                            confirmed=not a.unconfirmed, source=a.source or "车主实测"))
    save(d)
    print(f"已记录: {a.car}  物理 {a.physical} → HUD {a.hud}   ({a.condition})")
    print(f"当前确认点数: {sum(1 for p in d['points'] if p['confirmed'])}")


def confirmed_points(d):
    return [(p["physical"], p["hud"], p["car"]) for p in d["points"] if p["confirmed"]]


def cmd_list(a):
    d = load()
    if not d["points"]:
        print("库为空"); return
    print(f"{'车':<24}{'物理':>8}{'HUD':>8}{'面板':>8}  确认  条件")
    for p in d["points"]:
        pan = f"{p['panel']:.1f}" if p.get("panel") else "—"
        print(f"{p['car'][:22]:<24}{p['physical']:8.1f}{p['hud']:8.1f}{pan:>8}"
              f"  {'√' if p['confirmed'] else '?':<4}{p.get('condition','')}")
    n = len(confirmed_points(d))
    print(f"\n确认点 {n} 个" + ("" if n >= MIN_POINTS else f"  —— 少于 {MIN_POINTS}，换算关系尚不可信"))


def fit(d):
    pts = confirmed_points(d)
    if len(pts) < 2:
        return None
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    n = len(xs)
    mx = sum(xs)/n; my = sum(ys)/n
    den = sum((x-mx)**2 for x in xs)
    if den == 0:
        return None
    k = sum((x-mx)*(y-my) for x, y in zip(xs, ys)) / den
    b = my - k*mx
    ss_res = sum((y-(k*x+b))**2 for x, y in zip(xs, ys))
    ss_tot = sum((y-my)**2 for y in ys)
    r2 = 1 - ss_res/ss_tot if ss_tot else 1.0
    return k, b, r2, n


def cmd_fit(a):
    d = load(); r = fit(d)
    if r is None:
        print("确认点不足 2 个，无法拟合"); return
    k, b, r2, n = r
    print(f"HUD = {k:.4f} × 物理 {b:+.2f}     R² = {r2:.4f}   (n = {n})")
    if n < MIN_POINTS:
        print(f"⚠ 仅 {n} 个确认点（要求 ≥{MIN_POINTS}）——**此关系不可作为定论**，仅供参考")
    print("\n各点残差:")
    for x, y, car in confirmed_points(d):
        print(f"   {car[:22]:<24} 物理{x:7.1f}  实测{y:7.1f}  预测{k*x+b:7.1f}  残差{y-(k*x+b):+7.1f}")


def cmd_predict(a):
    d = load(); r = fit(d)
    if r is None:
        sys.exit("确认点不足，无法反查")
    k, b, r2, n = r
    x = (a.hud - b) / k
    print(f"想要 HUD {a.hud:.0f}  →  物理 ground_speed 填 {x:.1f}")
    if n < MIN_POINTS:
        print(f"⚠ 仅 {n} 个确认点，此结果是外推，**必须实测复核**")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("add");  p.set_defaults(fn=cmd_add)
    p.add_argument("--car", required=True); p.add_argument("--physical", type=float, required=True)
    p.add_argument("--hud", type=float, required=True); p.add_argument("--panel", type=float)
    p.add_argument("--condition", default=""); p.add_argument("--source")
    p.add_argument("--unconfirmed", action="store_true", help="非车主明确实测")
    p = sub.add_parser("list"); p.set_defaults(fn=cmd_list)
    p = sub.add_parser("fit");  p.set_defaults(fn=cmd_fit)
    p = sub.add_parser("predict"); p.set_defaults(fn=cmd_predict)
    p.add_argument("hud", type=float)
    a = ap.parse_args(); a.fn(a)
