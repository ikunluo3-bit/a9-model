#!/usr/bin/env python3
"""整车替换：让 B 车在外观/物理/几何上彻底变成 A 车，只保留 B 的身份。

    python carswap.py --swap "Aston Martin Valkyre>Chevrolet Camaro LT" --grip 0.95
                      --swap "Mercedes_AMG_One>BMW Z4 LCI E89" --grip 1.0231 --top-speed 285
                      --apply

每个微调参数 / 开关作用于**它前面最近的那个 --swap**。
自体强化写 "A>A"（只改物理，不动 CarDef）；--keep-look 保壳（换物理+几何，
外观和引擎声留受体）。默认满改锁：18 对 (低级值,满级值) 全钉满级端。

微调参数（默认满改哲学：只动增益四件套，侧向力链留给供体原厂配平——
拆抄会乱抬轮，见 04-实测反馈/11 与 01-代码层/08）
    --top-speed   极速 idx22/23          --accel      加速 idx72/73
    --grip        抓地 idx78/79          --steer      锐度 idx19/21（14/16 同比）
    --handling    操控 idx76/77          --downforce  下压力 idx30/31
    --cg / --track-f / --susp           底盘三项（会复制底盘记录后改写）
    --nitro-boost 四档氮气加成倍率      --nitro-drain    四档消耗倍率
    --purple-drain 只动紫喷消耗（治"紫喷太短"）

三个库、三种手法
    CarPhysics  供体记录整体写进受体槽位（自体强化时改自己）
    CarChassis  一律复制记录体，不用「描述符改指向」——
                改指向存的是供体记录的偏移量，一旦本库因别的车触发重排，
                偏移全变，指向就成了野指针 -> 开屏闪退（01-代码层/07 踩过）
    CarDef      供体整条车辆定义复制进受体槽位，只保留受体身份头 (+0/+8)，
                并把记录内每个逐车库的 key 回填成受体自己的
                （CarChassis / CarPhysics / CarSounds —— 漏掉任何一个，车会从车库消失）
                自体强化 / --keep-look 跳过本步

外观由 CarDef 带过来，不需要动任何资源文件。
详见 01-代码层/06-整车替换-完整方法.md 与 04-实测反馈/12-车队改装总账.md
"""
from __future__ import annotations
import argparse, json, struct, sys, io
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from index6 import table, resolve, build as build_index, G
from transplant import alias, maxed, rebuild, fmt, SHOW, CHASSIS, PAIRS

if sys.platform == "win32" and not isinstance(sys.stdout, io.TextIOWrapper):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BASE = Path(__file__).resolve().parents[1]
OUT = BASE / "tuned-carswap"
KEY_LO, KEY_HI = 0x0000090000000000, 0x00000A0000000000

# 逐车一条记录的库 —— 这些 key 属于「车辆身份」，替换时必须换成受体自己的。
# 其余库（Global / Tags / GARAGE …）是共用配置，保留供体的。
PER_CAR_GDB = ("CarPhysics.gdb", "CarChassis.gdb", "CarSounds.gdb",
               "CarThumbnails.gdb", "CarFilters.gdb", "cars.gdb")

# 可微调的性能项 -> (低级值下标, 满级值下标)。两个都写，否则会随星级插值。
TWEAK = {"top_speed": (22, 23), "accel": (72, 73), "grip": (78, 79),
         "handling": (76, 77), "downforce": (30, 31), "damp": (99, 100)}

# 转向有两对槽，全库每台车都保持固定比例，必须一起缩放：
#   19/21 转向锐度（主）   14/16 低速转向角（从）
STEER_MAIN = (19, 21)
STEER_ALT = (14, 16)

# 底盘可调项 -> CarChassis 槽位
CHASSIS_TWEAK = {"cg": 14, "track_f": 4, "mass": 0}

# 悬挂行程（米）: 前 (16,17) 后 (18,19)，每对是 (下限, 上限)。
# 行程越小车身可动范围越小 -> 视觉更贴地、侧倾时内侧轮抬得越低。
# 参照: Fordzilla P1 = 0.010/0.010（车主亲口说的「贴地车」），
#       银电 0.000/0.000（全库最低），保时捷 718 Cayman 0.080/0.100（最高）。
SUSP = {"f": (16, 17), "r": (18, 19)}

# 四级氮气的消耗槽（越小越省）。--nitro-drain 是倍率，对四级同时生效。
DRAIN_PAIRS = ((34, 35), (42, 43), (50, 51), (58, 59))

# 四级氮气的加成槽（速度提升）。--nitro-boost 是倍率，对四级同时生效。
BOOST_PAIRS = ((36, 37), (44, 45), (52, 53), (60, 61))


def key_owner_map():
    """key -> 所属 gdb 文件名（只收 PER_CAR_GDB）。"""
    m = {}
    for nm in PER_CAR_GDB:
        f = G / nm
        if not f.exists():
            continue
        try:
            for d in table(f.read_bytes())[1]:
                m.setdefault(d["key"], nm)
        except Exception:
            pass
    return m


def keylist(buf: bytes):
    """记录里按出现顺序排列的 gdb key。"""
    out, i = [], 0
    while i <= len(buf) - 8:
        v = struct.unpack_from("<Q", buf, i)[0]
        if KEY_LO <= v <= KEY_HI:
            out.append((i, v))
            i += 8
        else:
            i += 1
    return out


class SwapAction(argparse.Action):
    def __call__(self, parser, ns, values, option_string=None):
        if ">" not in values:
            parser.error("--swap 格式是 供体>受体")
        s, d = (x.strip() for x in values.split(">", 1))
        ns.plan.append(dict(src=s, dst=d))


class TweakAction(argparse.Action):
    def __call__(self, parser, ns, values, option_string=None):
        if not ns.plan:
            parser.error(option_string + " 必须跟在某个 --swap 后面")
        ns.plan[-1][self.dest] = values


class FlagAction(argparse.Action):
    """无值开关，作用于它前面最近的 --swap（如 --keep-look）。"""
    def __call__(self, parser, ns, values, option_string=None):
        if not ns.plan:
            parser.error(option_string + " 必须跟在某个 --swap 后面")
        ns.plan[-1][self.dest] = True


def main():
    ap = argparse.ArgumentParser()
    ap.set_defaults(plan=[])
    ap.add_argument("--swap", action=SwapAction, help="供体>受体，可重复")
    ap.add_argument("--from", dest="src")
    ap.add_argument("--to", dest="dst")
    ap.add_argument("--top-speed", dest="top_speed", type=float, action=TweakAction,
                    help="物理极速 idx22/23")
    ap.add_argument("--accel", dest="accel", type=float, action=TweakAction,
                    help="加速 idx72/73")
    ap.add_argument("--grip", dest="grip", type=float, action=TweakAction,
                    help="抓地 idx78/79；不动极速时抓地越高半径越小 (R = v^2/a_lat)")
    ap.add_argument("--handling", dest="handling", type=str, action=TweakAction,
                    help="操控 idx76/77。单值=两端同写；'lo,hi'=保留升级差（如 0.5,0.6）。"
                         "与面板操控相关 0.7985，管漂移和过弯半径；全库最高 1.00（塞纳）")
    ap.add_argument("--downforce", dest="downforce", type=float, action=TweakAction,
                    help="下压力 idx30/31 —— 抬轮的真正总开关。"
                         "杰AB 200(抬轮高) / P1 550(不抬轮) / 恶魔16 1150(全库最高)")
    ap.add_argument("--damp", dest="damp", type=float, action=TweakAction,
                    help="压缩/回弹阻尼 idx99/100。0.3 软晃 / 0.5 硬档(Apollo/DBS) / 再高=超库钉地档")
    ap.add_argument("--steer", dest="steer", type=float, action=TweakAction,
                    help="转向锐度 idx19/21，14/16 按同比例缩放。"
                         "注意：与面板操控只相关 0.2864，更像转向响应速度而非半径")
    ap.add_argument("--cg", dest="cg", type=float, action=TweakAction,
                    help="重心高（负值）。|重心| 越小抬轮越轻，前轮才压得住")
    ap.add_argument("--susp", dest="susp", type=str, action=TweakAction,
                    help="悬挂行程 '下限,上限'（米），前后同设。"
                         "P1 贴地档 0.01,0.01；AMG One 原厂 0.04,0.08")
    ap.add_argument("--track-f", dest="track_f", type=float, action=TweakAction,
                    help="前轮距（米）。抬轮 = 抓地 x |重心| / 前轮距")
    ap.add_argument("--mass", dest="mass", type=float, action=TweakAction,
                    help="质量 kg（底盘 idx0）。370Z 1512 / Evo 2060；极端轻量=卡丁化实验")
    ap.add_argument("--nitro-drain", dest="nitro_drain", type=float, action=TweakAction,
                    help="四级氮气消耗倍率，<1 更省。全库最省是银电的蓝喷 14")
    ap.add_argument("--nitro-boost", dest="nitro_boost", type=float, action=TweakAction,
                    help="四级氮气加成倍率，>1 更猛。单位为物理速度，HUD 增量 = 倍率增量 x 2.15")
    ap.add_argument("--purple-drain", dest="purple_drain", type=float, action=TweakAction,
                    help="紫喷消耗倍率（只动紫喷一对 58/59）。紫喷太短时用：0.333 = 时长 x3")
    ap.add_argument("--nitro-a", dest="nitro_a", type=str, action=TweakAction,
                    help="四档氮气 A 对（未解字段，工作假设=完美氮气触发窗口宽度）。"
                         "单值全档同写，或 '单,橙,蓝,紫' 四值。全库最大 0.0525,0.0525,0.11,0.07")
    ap.add_argument("--no-maxed", action="store_true", help="不做满改，保留供体升级曲线")
    ap.add_argument("--keep-look", action=FlagAction, nargs=0,
                    help="保壳：只搬物理+几何，保留受体自己的外观/CarDef/引擎声")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    if a.src and a.dst:
        a.plan.insert(0, dict(src=a.src, dst=a.dst))
    if not a.plan:
        ap.error("至少要一个 --swap 或 --from/--to")

    idx = build_index()
    cp = (G / "CarPhysics.gdb").read_bytes()
    ch = (G / "CarChassis.gdb").read_bytes()
    cd = (G / "CarDef.gdb").read_bytes()
    descs = table(cd)[1]
    owner = key_owner_map()

    rep_cp, rep_ch, rep_cd = {}, {}, {}
    summary = []

    for job in a.plan:
        sk, sv = resolve(idx, job["src"])
        dk, dv = resolve(idx, job["dst"])
        self_swap = (sk == dk)   # 自体强化：只改 CarPhysics，底盘/CarDef 本来就是自己的
        keep_look = job.get("keep_look")   # 保壳：跳过 CarDef，外观/引擎声留受体的
        print("\n" + "=" * 66)
        print(sk + "   ->   " + dk
              + ("   [自体强化]" if self_swap else ("   [保壳]" if keep_look else "")))
        print("=" * 66)

        # --- CarPhysics ---
        sp, dp = sv["physics"], dv["physics"]
        body = cp[sp["off"]:sp["off"] + sp["size"]]
        if not a.no_maxed:
            body = maxed(body)     # 17 对升级值钉在满级端
        body = bytearray(body)
        before = fmt(cp[dp["off"]:dp["off"] + dp["size"]], SHOW)
        donor = fmt(cp[sp["off"]:sp["off"] + sp["size"]], SHOW)
        for fld, (lo, hi) in TWEAK.items():
            if job.get(fld) is None:
                continue
            v = float(job[fld])
            old = struct.unpack_from("<f", body, hi * 4)[0]
            for i in (lo, hi):     # 低位也写，否则会随星级插值
                struct.pack_into("<f", body, i * 4, v)
            print("  微调 %-10s %9.4f -> %9.4f  (x%.3f)" % (fld, old, v, v / old))
        if job.get("steer") is not None:
            v = float(job["steer"])
            old = struct.unpack_from("<f", body, STEER_MAIN[1] * 4)[0]
            ratio = v / old
            for i in STEER_MAIN:
                struct.pack_into("<f", body, i * 4, v if i == STEER_MAIN[1] else v / 2.0)
            struct.pack_into("<f", body, STEER_MAIN[0] * 4,
                             struct.unpack_from("<f", cp, sp["off"] + STEER_MAIN[0] * 4)[0] * ratio)
            for i in STEER_ALT:
                ov = struct.unpack_from("<f", body, i * 4)[0]
                struct.pack_into("<f", body, i * 4, ov * ratio)
            alt = struct.unpack_from("<f", body, STEER_ALT[1] * 4)[0]
            print("  转向锐度 %.0f -> %.0f (x%.3f)，低速转向角同比 -> %.0f"
                  % (old, v, ratio, alt))
        if job.get("nitro_drain") is not None:
            f_ = float(job["nitro_drain"])
            shown = []
            for lo, hi in DRAIN_PAIRS:
                nv = struct.unpack_from("<f", body, hi * 4)[0] * f_
                shown.append(nv)
                for i in (lo, hi):
                    struct.pack_into("<f", body, i * 4, nv)
            print("  氮气消耗 x%.2f -> 单%.1f 橙%.1f 蓝%.1f 紫%.1f  (越小越省)"
                  % (f_, shown[0], shown[1], shown[2], shown[3]))
        if job.get("nitro_boost") is not None:
            f_ = float(job["nitro_boost"])
            shown = []
            for lo, hi in BOOST_PAIRS:
                nv = struct.unpack_from("<f", body, hi * 4)[0] * f_
                shown.append(nv)
                for i in (lo, hi):
                    struct.pack_into("<f", body, i * 4, nv)
            print("  氮气加成 x%.2f -> 单%.2f 橙%.2f 蓝%.2f 紫%.2f  (物理速度单位)"
                  % (f_, shown[0], shown[1], shown[2], shown[3]))
        if job.get("purple_drain") is not None:
            f_ = float(job["purple_drain"])
            nv = struct.unpack_from("<f", body, 59 * 4)[0] * f_
            for i in (58, 59):
                struct.pack_into("<f", body, i * 4, nv)
            print("  紫喷消耗 x%.3f -> %.2f  (时长 x%.1f，其余档位不动)"
                  % (f_, nv, 1.0 / f_))
        if job.get("nitro_a") is not None:
            parts = [float(x) for x in str(job["nitro_a"]).split(",")]
            vals = parts * 4 if len(parts) == 1 else parts
            if len(vals) != 4:
                sys.exit("--nitro-a 需要 1 个值或 '单,橙,蓝,紫' 4 个值")
            for base, v_ in zip((32, 40, 48, 56), vals):
                for i in (base, base + 1):
                    struct.pack_into("<f", body, i * 4, v_)
            print("  氮气A(疑似完美触发窗) -> 单%.4f 橙%.4f 蓝%.4f 紫%.4f"
                  % tuple(vals))
        body = bytes(body)
        rep_cp[dp["off"]] = body
        after = fmt(body, SHOW)

        # --- CarChassis（自体强化跳过：底盘就是自己的） ---
        sc, dc = sv["chassis"], dv["chassis"]
        scb = ch[sc["off"]:sc["off"] + sc["size"]]
        geo_tweaks = {k: job[k] for k in CHASSIS_TWEAK if job.get(k) is not None}
        if job.get("susp") is not None:
            geo_tweaks["susp"] = job["susp"]
        if geo_tweaks:
            # 要改几何就不能用改指向（那会连供体本尊一起改），必须复制一份再改
            b2 = bytearray(scb)
            for k, v in geo_tweaks.items():
                if k == "susp":
                    lo, hi = (float(x) for x in str(v).split(","))
                    for ax, (s_lo, s_hi) in SUSP.items():
                        o1 = struct.unpack_from("<f", b2, s_lo * 4)[0]
                        o2 = struct.unpack_from("<f", b2, s_hi * 4)[0]
                        struct.pack_into("<f", b2, s_lo * 4, lo)
                        struct.pack_into("<f", b2, s_hi * 4, hi)
                        print("  悬挂行程 %s  %.3f/%.3f -> %.3f/%.3f" % (ax, o1, o2, lo, hi))
                    continue
                i = CHASSIS_TWEAK[k]
                old = struct.unpack_from("<f", b2, i * 4)[0]
                struct.pack_into("<f", b2, i * 4, float(v))
                print("  几何 %-10s %9.4f -> %9.4f" % (k, old, float(v)))
            scb = bytes(b2)
            rep_ch[dc["off"]] = scb
            how = "复制供体几何后改写"
        else:
            # 一律复制记录体，不用「描述符改指向」。
            # 改指向存的是供体记录的**偏移量**，一旦本库因别的车触发重排，
            # 偏移全变，那条指向就成了野指针 -> 开屏闪退（踩过）。
            rep_ch[dc["off"]] = scb
            how = "复制供体几何"
        geo = fmt(scb, CHASSIS)
        geo_old = fmt(ch[dc["off"]:dc["off"] + dc["size"]], CHASSIS)

        print("\n  %-12s%12s%12s%12s" % ("项", "受体原值", "供体", "最终"))
        for _, l in SHOW:
            if l in before and l in after:
                print("  %-12s%12.4g%12.4g%12.4g" % (l, before[l], donor.get(l, 0), after[l]))
        wl_o = before["抓地"] * abs(geo_old["重心高"]) / geo_old["前轮距"]
        wl_n = after["抓地"] * abs(geo["重心高"]) / geo["前轮距"]
        print("  %-12s%12.4f%12s%12.4f   (几何 %s)" % ("抬轮指数", wl_o, "", wl_n, how))
        # 半径代理 = v^2 / 抓地。两个基准都要报：
        #   vs 受体原厂 = 车主真正的体感基准（他开的是这台车）
        #   vs 供体原厂 = 这套物理相对它出处的变化
        # 只报后者会造成「15% 达标」的错觉，实际相对旧车可能纹丝不动。踩过。
        prox_now = after["极速"] ** 2 / after["抓地"]
        prox_rec = before["极速"] ** 2 / before["抓地"]
        prox_don = donor["极速"] ** 2 / donor["抓地"]
        print("  半径代理 v^2/抓地   受体原厂 %.0f  供体原厂 %.0f  当前 %.0f"
              % (prox_rec, prox_don, prox_now))
        print("  半径  vs 受体原厂 x%.3f  <- 体感基准     vs 供体原厂 x%.3f"
              % (prox_now / prox_rec, prox_now / prox_don))

        # --- CarDef（自体强化/保壳跳过：车辆定义不动） ---
        if not self_swap and not keep_look:
            src_rec = next(d for d in descs if d["off"] == sv["cardef_off"])
            dst_rec = next(d for d in descs if d["off"] == dv["cardef_off"])
            cb = bytearray(cd[dst_rec["off"]:dst_rec["off"] + 16] +
                           cd[src_rec["off"] + 16:src_rec["off"] + src_rec["size"]])
            sks = keylist(cd[src_rec["off"]:src_rec["off"] + src_rec["size"]])
            dks = keylist(cd[dst_rec["off"]:dst_rec["off"] + dst_rec["size"]])
            dst_by_gdb = {}
            for _, v in dks:
                g = owner.get(v)
                if g:
                    dst_by_gdb.setdefault(g, []).append(v)
            used = {}
            for si, sval in sks:
                g = owner.get(sval)
                if g is None:
                    continue           # Global/Tags 共用配置，保持供体的
                k = used.get(g, 0)
                used[g] = k + 1
                cand = dst_by_gdb.get(g, [])
                if k >= len(cand):
                    print("  ! %s 受体无第 %d 条对应记录，保留供体 key" % (g, k + 1))
                    continue
                dval = cand[k]
                if sval == dval:
                    continue
                n = 0
                for i in range(len(cb) - 7):
                    if struct.unpack_from("<Q", cb, i)[0] == sval:
                        struct.pack_into("<Q", cb, i, dval)
                        n += 1
                if not n:
                    sys.exit("key 0x%016X 回填失败" % sval)
                print("  CarDef key 回填 %-18s -> 0x%016X" % (g, dval))
            rep_cd[dst_rec["off"]] = bytes(cb)
        summary.append(dict(donor=sk, recipient=dk,
                            **{k: v for k, v in job.items() if k not in ("src", "dst")}))

    new_cp = rebuild(cp, rep_cp)
    new_ch = rebuild(ch, rep_ch) if rep_ch else ch
    new_cd = rebuild(cd, rep_cd)

    print("\n" + "=" * 66)
    print("CarPhysics %s -> %s B" % (f"{len(cp):,}", f"{len(new_cp):,}"))
    print("CarChassis %s -> %s B" % (f"{len(ch):,}", f"{len(new_ch):,}"))
    print("CarDef     %s -> %s B  (%+d，repack 会同步改 manifest 明文大小)"
          % (f"{len(cd):,}", f"{len(new_cd):,}", len(new_cd) - len(cd)))
    for nm, orig in (("CarPhysics", cp), ("CarChassis", ch), ("CarDef", cd)):
        if rebuild(orig, {}) != orig:
            sys.exit(nm + " 空重建自检失败")
    print("空重建自检：三个库逐字节一致")
    if not a.no_maxed:
        print("满改锁：%d 对升级值全部钉在满级端 —— 任何星级/改装状态都是同一套性能"
              % len(PAIRS))

    if a.apply:
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / "CarPhysics.gdb").write_bytes(new_cp)
        (OUT / "CarChassis.gdb").write_bytes(new_ch)
        (OUT / "CarDef.gdb").write_bytes(new_cd)
        (OUT / "plan.json").write_text(
            json.dumps(dict(swaps=summary, maxed=not a.no_maxed),
                       ensure_ascii=False, indent=2), encoding="utf-8")
        print("已写出 " + str(OUT))


if __name__ == "__main__":
    main()
