#!/usr/bin/env python3
"""车队改装管理器 —— fleet-plan.json 的增删改查 + 一键重建。

    python tools/fleet.py                                  # 列出当前车队
    python tools/fleet.py show <受体名>                    # 看某台的完整配置
    python tools/fleet.py add "供体>受体" [微调...] [--keep-look]
    python tools/fleet.py set <受体名> [微调...] [--keep-look|--no-keep-look]
    python tools/fleet.py donor <受体名> <新供体>          # 只换供体，微调保留
    python tools/fleet.py remove <受体名>
    python tools/fleet.py build [--no-apply]               # 全量重建 tuned-carswap
    python tools/fleet.py install [标签]                   # build 后回封+签名+装机

微调参数与 carswap.py 完全同名：
    --top-speed --accel --grip --handling --downforce --steer
    --cg --track-f --susp --nitro-boost --nitro-drain --purple-drain

铁律不变：build 永远从 gdb-6.0.0k 原始库全量重算全部条目，
没有增量状态 —— fleet-plan.json 就是车队的唯一事实源。
set 只动写到的参数，其余原样保留。
"""
from __future__ import annotations
import io, json, subprocess, sys, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

if sys.platform == "win32" and not isinstance(sys.stdout, io.TextIOWrapper):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BASE = Path(__file__).resolve().parents[1]
TOOLS = BASE / "tools"
CARSWAP = TOOLS / "carswap.py"
PLAN_FILE = BASE / "fleet-plan.json"
OUT = BASE / "tuned-carswap"

# 与 carswap.py 同名的微调旗标（带值）
TWEAK_FLAGS = (
    "top_speed", "accel", "grip", "handling", "downforce", "steer",
    "cg", "track_f", "susp", "nitro_boost", "nitro_drain", "purple_drain",
    "nitro_a",
)


def die(msg: str):
    sys.exit(msg)


def load_plan() -> dict:
    if not PLAN_FILE.exists():
        die("找不到 " + str(PLAN_FILE))
    return json.loads(PLAN_FILE.read_text(encoding="utf-8"))


def save_plan(plan: dict):
    plan["updated"] = datetime.date.today().isoformat()
    # 整数值的浮点存成整数，配置文件保持人类可读
    for s in plan.get("swaps", []):
        tw = s.get("tweaks")
        if not tw:
            continue
        for k, v in list(tw.items()):
            if isinstance(v, float) and k != "susp" and v.is_integer():
                tw[k] = int(v)
    PLAN_FILE.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n",
                         encoding="utf-8")


def find_swap(plan: dict, name: str) -> dict:
    """按受体找条目：先精确匹配，再子串匹配；命中多条则报错并列出。"""
    n = name.strip().lower()
    for s in plan["swaps"]:
        if s["dst"].lower() == n:
            return s
    hits = [s for s in plan["swaps"] if n in s["dst"].lower()]
    if len(hits) == 1:
        return hits[0]
    if not hits:
        die(f"车队里没有受体「{name}」。用 `python tools/fleet.py` 看现有清单。")
    lines = "\n".join("  - " + s["dst"] for s in hits)
    die(f"「{name}」匹配到 {len(hits)} 台，请写更精确的名字：\n{lines}")


def fmt_val(v) -> str:
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)


def parse_tweaks(tokens: list[str], base: dict | None = None) -> tuple[dict, bool | None]:
    """解析 [--flag value ...] 和 [--keep-look|--no-keep-look]。base 给了则在副本上更新。"""
    out = dict(base.get("tweaks", {})) if base else {}
    look = None
    i = 0
    while i < len(tokens):
        t = tokens[i]
        if t == "--keep-look":
            look = True
            i += 1
        elif t == "--no-keep-look":
            look = False
            i += 1
        elif t.startswith("--"):
            key = t[2:].replace("-", "_")
            if key not in TWEAK_FLAGS:
                die(f"不认识的参数 {t}。\n可用微调：" +
                    " ".join("--" + k.replace("_", "-") for k in TWEAK_FLAGS)
                    + "，外加 --keep-look")
            if i + 1 >= len(tokens):
                die(t + " 缺少取值")
            raw = tokens[i + 1]
            if key in ("susp", "nitro_a"):
                out[key] = raw                       # 'lo,hi' / '单,橙,蓝,紫' 字符串原样存
            else:
                try:
                    out[key] = float(raw)
                except ValueError:
                    die(f"{t} 的取值不是数字：{raw}")
            i += 2                                   # 旗标连同取值一起跳过
        else:
            die(f"多余的位置参数：{t}")
    return out, look


def parse_pair(spec: str) -> tuple[str, str]:
    if ">" not in spec:
        die('格式应为 "供体>受体"，如 "Aston Martin Valkyre>Ford GT"')
    src, _, dst = spec.partition(">")
    src, dst = src.strip(), dst.strip()
    if not src or not dst:
        die("供体和受体都不能为空")
    return src, dst


def check_names(src: str, dst: str):
    """借 index6 提前验名，敲错当场报错，不等 build 才炸。"""
    from index6 import build as build_index, resolve
    idx = build_index()
    for role, nm in (("供体", src), ("受体", dst)):
        try:
            resolve(idx, nm)
        except SystemExit as e:              # resolve 用 sys.exit(str) 报歧义/找不到
            die(f"{role}校验失败：" + (str(e.args[0]) if e.args else ""))
        except Exception as e:
            die(f"{role}「{nm}」在库里解析失败：{e}")


def dst_exists(plan: dict, dst: str):
    for s in plan["swaps"]:
        if s["dst"].lower() == dst.strip().lower():
            die(f"受体「{s['dst']}」已在车队里。\n"
                f"要调它用：python tools/fleet.py set \"{s['dst']}\" [微调...]")


# ---------------------------------------------------------------- 子命令

def cmd_list(plan: dict):
    print(f"车队 {len(plan['swaps'])} 台 · 计划文件 {PLAN_FILE.name}"
          f" · 版本 {plan.get('version', '?')} · 更新于 {plan.get('updated', '?')}")
    print()
    print("%-3s %-42s %-34s %-4s %s" % ("#", "受体", "供体", "保壳", "微调"))
    for i, s in enumerate(plan["swaps"], 1):
        tw = ", ".join("%s=%s" % (k.replace("_", "-"), fmt_val(v))
                       for k, v in s.get("tweaks", {}).items())
        print("%-3d %-42s %-34s %-4s %s" % (
            i, s["dst"], s["src"], "√" if s.get("keep_look") else "", tw))
    print()
    print("改完记得: python tools/fleet.py build && python tools/fleet.py install")


def cmd_show(plan: dict, name: str):
    s = find_swap(plan, name)
    print(json.dumps(s, ensure_ascii=False, indent=2))


def cmd_add(plan: dict, rest: list[str]):
    if not rest or ">" not in rest[0]:
        die('用法: fleet.py add "供体>受体" [微调...] [--keep-look]')
    src, dst = parse_pair(rest[0])
    dst_exists(plan, dst)
    tweaks, look = parse_tweaks(rest[1:])
    check_names(src, dst)
    entry = {"src": src, "dst": dst}
    if look:
        entry["keep_look"] = True
    if tweaks:
        entry["tweaks"] = tweaks
    plan["swaps"].append(entry)
    save_plan(plan)
    print(f"已加入 #{len(plan['swaps'])}：{src} -> {dst}"
          + ("  [保壳]" if look else ""))
    _changed_hint()


def cmd_set(plan: dict, rest: list[str]):
    if not rest:
        die('用法: fleet.py set <受体名> [微调...] [--keep-look|--no-keep-look]')
    s = find_swap(plan, rest[0])
    tweaks, look = parse_tweaks(rest[1:], base=s)
    old_tw = dict(s.get("tweaks", {}))
    s["tweaks"] = tweaks
    if look is True:
        s["keep_look"] = True
    elif look is False:
        s.pop("keep_look", None)
    save_plan(plan)
    changed = {k: (old_tw.get(k), v) for k, v in s["tweaks"].items()
               if old_tw.get(k) != v}
    print(f"已更新「{s['dst']}」")
    for k, (o, v) in changed.items():
        print(f"  {k.replace('_','-')}: {o if o is not None else '(无)'} -> {fmt_val(v)}")
    if not changed:
        print("  （微调无变化）")
    if look is not None:
        print(f"  keep_look -> {'开(保壳)' if (look or s.get('keep_look')) else '关'}")
    _changed_hint()


def cmd_donor(plan: dict, rest: list[str]):
    if len(rest) < 2:
        die("用法: fleet.py donor <受体名> <新供体>")
    s = find_swap(plan, rest[0])
    new_src = rest[1].strip()
    check_names(new_src, s["dst"])
    old = s["src"]
    s["src"] = new_src
    save_plan(plan)
    print(f"已换供体：「{s['dst']}」  {old} -> {new_src}（微调原样保留）")
    _changed_hint()


def cmd_remove(plan: dict, rest: list[str]):
    if not rest:
        die("用法: fleet.py remove <受体名>")
    s = find_swap(plan, rest[0])
    plan["swaps"].remove(s)
    save_plan(plan)
    print(f"已移出车队：「{s['dst']}」（供体 {s['src']}，配置一并清除）")
    _changed_hint()


def cmd_build(plan: dict, rest: list[str]):
    apply_ = "--no-apply" not in rest
    argv = [sys.executable, str(CARSWAP)]
    for s in plan["swaps"]:
        argv += ["--swap", f"{s['src']}>{s['dst']}"]
        if s.get("keep_look"):
            argv.append("--keep-look")
        for k, v in s.get("tweaks", {}).items():
            argv += ["--" + k.replace("_", "-"), fmt_val(v)]
    if apply_:
        argv.append("--apply")
    print("全量重建 %d 台 ..." % len(plan["swaps"]))
    r = subprocess.run(argv, cwd=str(TOOLS))
    if r.returncode != 0:
        die(f"carswap 退出码 {r.returncode}，tuned 输出不可信")
    if apply_:
        print("\n完成。下一步装机: python tools/fleet.py install [标签]")


def cmd_install(plan: dict, rest: list[str]):
    tag = rest[0] if rest else "fleet-" + datetime.date.today().strftime("%m%d")
    if not OUT.exists():
        die("还没有 build 产物，先跑 python tools/fleet.py build")
    bash = None
    for cand in ("bash", r"C:\Program Files\Git\bin\bash.exe"):
        import shutil
        p = shutil.which(cand)
        if p:
            bash = p
            break
    if not bash:
        die("找不到 bash。手动执行:\n"
            f"  cd {TOOLS} && ./build.sh {tag} --tuned \"{OUT}\" "
            "--files CarPhysics.gdb CarChassis.gdb CarDef.gdb")
    argv = [bash, "build.sh", tag,
            "--tuned", str(OUT),
            "--files", "CarPhysics.gdb", "CarChassis.gdb", "CarDef.gdb"]
    print("回封+签名+装机:", tag)
    r = subprocess.run(argv, cwd=str(TOOLS))
    if r.returncode != 0:
        die(f"build.sh 退出码 {r.returncode}")


def _changed_hint():
    print("尚未生效 —— 记得跑: python tools/fleet.py build && python tools/fleet.py install")


VERBS = {
    "show":   lambda: cmd_show(load_plan(), sys.argv[2]),
    "add":    lambda: cmd_add(load_plan(), sys.argv[2:]),
    "set":    lambda: cmd_set(load_plan(), sys.argv[2:]),
    "donor":  lambda: cmd_donor(load_plan(), sys.argv[2:]),
    "remove": lambda: cmd_remove(load_plan(), sys.argv[2:]),
    "build":  lambda: cmd_build(load_plan(), sys.argv[2:]),
    "install": lambda: cmd_install(load_plan(), sys.argv[2:]),
}


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "help", "list"):
        cmd_list(load_plan())
        return
    verb = sys.argv[1]
    fn = VERBS.get(verb)
    if fn is None:
        die(f"不认识的命令「{verb}」。\n可用: show/add/set/donor/remove/build/install/list")
    fn()


if __name__ == "__main__":
    main()
