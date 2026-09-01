import pathlib
p = pathlib.Path("fleetstats.py"); s = p.read_text(encoding="utf-8")
s = s.replace('''PHYS = [(23, "物理极速")''',
'''# 开发用参考车 / 非玩家载具 —— 会污染极值，单列出来
NON_PLAYER = ("Fastest Car", "Slowest Car", "Invisible Car", "Police Truck",
              "Police", "Traffic")

def is_np(name):
    return any(t.lower() in name.lower() for t in NON_PLAYER)

PHYS = [(23, "物理极速")''')
s = s.replace('''def block(title, rows, get, n_all):
    print(f"## {title}\n")
    print("| 项 | 最低 | 中位 | 最高 | 最高者 |")
    print("|---|---:|---:|---:|---|")
    for i, lab in rows:
        vals = sorted((get(o, i), o) for o in n_all)
        lo, mid, hi = vals[0][0], vals[len(vals) // 2][0], vals[-1][0]
        who = pname.get(vals[-1][1], "?")
        print(f"| {lab} | {lo:.4g} | {mid:.4g} | **{hi:.4g}** | {who[:30]} |")
    print()''',
'''def block(title, rows, get, n_all, namemap):
    print(f"## {title}\n")
    print("| 项 | 最低 | 最低者 | 中位 | 最高 | 最高者 |")
    print("|---|---:|---|---:|---:|---|")
    for i, lab in rows:
        vals = sorted((get(o, i), o) for o in n_all)
        vals = [(v, o) for v, o in vals if not is_np(namemap.get(o, ""))]
        lo, olo = vals[0]
        hi, ohi = vals[-1]
        mid = vals[len(vals) // 2][0]
        print("| %s | **%.4g** | %s | %.4g | **%.4g** | %s |"
              % (lab, lo, namemap.get(olo, "?")[:26], mid, hi, namemap.get(ohi, "?")[:26]))
    print()''')
s = s.replace('block("CarPhysics", PHYS, lambda o, i: F[o][i], offs)',
              'block("CarPhysics", PHYS, lambda o, i: F[o][i], offs, pname)\n'
              'print("> 已剔除开发用参考车与非玩家载具"\n'
              '      "（Fastest/Slowest Car、Invisible Car、Police Truck 等）。\n")')
s = s.replace('''print("## CarChassis\n")
print("| 项 | 最低 | 中位 | 最高 | 最高者 |")
print("|---|---:|---:|---:|---|")
for i, lab in CHAS:
    vals = sorted((CF[o][i], o) for o in set(coffs))
    print(f"| {lab} | {vals[0][0]:.4g} | {vals[len(vals)//2][0]:.4g} | "
          f"**{vals[-1][0]:.4g}** | {cname.get(vals[-1][1],'?')[:30]} |")
print()''',
'''block("CarChassis", CHAS, lambda o, i: CF[o][i], sorted(set(coffs)), cname)''')
s = s.replace('''g = sorted(F[o][79] for o in offs)''',
              '''g = sorted(F[o][79] for o in offs if not is_np(pname.get(o, "")))''')
s = s.replace('''st = sorted(F[o][21] for o in offs)''',
              '''st = sorted(F[o][21] for o in offs if not is_np(pname.get(o, "")))''')
s = s.replace('''print("## 抓地百分位（改装选值用）\n")''',
              '''print("## 蓝喷消耗百分位（越小越省）\n")
d = sorted(F[o][51] for o in offs if not is_np(pname.get(o, "")))
print("| 蓝喷消耗 | 百分位 |")
print("|---:|---:|")
for v in (9, 12, 14, 16.2, 18, 20.25, 22.5, 27, 30):
    print(f"| {v} | {100*bisect.bisect_left(d, v)/len(d):.0f}% |")
print()

print("## 抓地百分位（改装选值用）\n")''')
p.write_text(s, encoding="utf-8")
import py_compile; py_compile.compile("fleetstats.py", doraise=True); print("ok")
