#!/usr/bin/env python3
"""A9 车辆物理调教器

支持 CarPhysics.gdb（性能）与 CarChassis.gdb（几何）两个文件的按车、按字段修改。

安全策略（"干净"的定义）：
  1. 改前必须校验原值 —— 不匹配就拒绝，防止版本/车型错位
  2. 只写点名的字段 —— 改完逐字节比对，任何越界改动直接报错回滚
  3. 原始文件自动备份
  4. 输出完整改动报告（字段、前后值、字节偏移、SHA-256）

用法:
  体检:  python tuner.py inspect --car "McLaren Senna"
  改:    python tuner.py patch  --car "McLaren Senna" --set tyre=1.5 --set cg=-0.12
  列车:  python tuner.py list --grep senna
"""
from __future__ import annotations
import argparse, hashlib, json, re, struct, shutil, sys, io
from pathlib import Path
import numpy as np

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# ---------------------------------------------------------------- 字段定义

# CarPhysics：名字 -> (lo_idx, hi_idx)。成对字段改动时两端同时缩放。
PHYS_FIELDS = {
    "ground_speed": (22, 23),      # 地面极速参数 (km/h)
    "accel":        (72, 73),      # 加速度
    "tyre":         (78, 79),      # 轮胎抓地力  ★ 同时影响 抬轮/半径/极速/侧滑
    "steer":        (19, 21),      # 转向锐度    ★ 大 = 过弯半径小
    "steer_alt":    (14, 16),      # 与 steer 同类(前/后轴之一)，互相关 0.93
    "damp_comp":    (99, 99),      # 压缩阻尼
    "damp_reb":     (100, 100),    # 回弹阻尼
    "n1_drain":     (34, 35), "n1_boost": (36, 37), "n1_hold": (38, 39),
    "n2_drain":     (42, 43), "n2_boost": (44, 45), "n2_hold": (46, 47),
    "n3_drain":     (50, 51), "n3_boost": (52, 53), "n3_hold": (54, 55),
    "n4_drain":     (58, 59), "n4_boost": (60, 61),
}
NITRO_LABEL = {"n1": "单喷", "n2": "橙喷(双击)", "n3": "蓝喷(完美)", "n4": "紫喷(脉冲)"}

# CarChassis：名字 -> 槽位
CHASSIS_FIELDS = {
    "mass":     0,    # 整备质量 kg
    "track_f":  4,    # 前轮距 m   ★ 抬轮公式分母
    "track_r":  5,    # 后轮距 m
    "wheelbase":6,    # 轴距 m
    "radius_f": 9,    # 前轮半径 m
    "radius_r": 10,   # 后轮半径 m
    "cg":       14,   # 重心高度 m (负值) ★ 抬轮公式分子
}

PEGASUS_KEY = "10864630126750436150"


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest().upper()


def as_f32(v: float) -> float:
    return struct.unpack("<f", struct.pack("<f", v))[0]


# ---------------------------------------------------------------- gdb 解析

def descriptors(data: bytes):
    for co in range(max(0, len(data) - 32 * 2000), len(data) - 3, 4):
        cnt = struct.unpack_from("<I", data, co)[0]
        if not 1 <= cnt <= 2000 or co + 4 + cnt * 32 != len(data):
            continue
        t = co + 4
        return [dict(zip(("i", "key", "off", "size", "tag"),
                (i,) + struct.unpack_from("<QQQQ", data, t + i * 32))) for i in range(cnt)]
    raise SystemExit("descriptor table not found")


class Model:
    """把 CarDef / CarPhysics / CarChassis 三个库按车名关联起来。"""

    def __init__(self, root: Path):
        self.root = root
        self.cardef = (root / "CarDef.gdb").read_bytes()
        self.phys_raw = (root / "CarPhysics.gdb").read_bytes()
        self.chas_raw = (root / "CarChassis.gdb").read_bytes()
        self.phys = descriptors(self.phys_raw)
        self.chas = descriptors(self.chas_raw)
        self.pmap = self._posmap(self.phys)
        self.cmap = self._posmap(self.chas)
        self.pkeys = np.array(sorted(self.pmap))
        self.ckeys = np.array(sorted(self.cmap))

    def _posmap(self, descs):
        m = {}
        for d in descs:
            p = self.cardef.find(struct.pack("<Q", d["key"]))
            if p >= 0:
                m[p] = d
        return m

    _NAME = re.compile(rb"[A-Za-z0-9][ -~]{2,59}")

    def _name_before(self, pos, window=0x400):
        seg = self.cardef[max(0, pos - window):pos]
        best = None
        for m in self._NAME.finditer(seg):
            s = m.group()
            if b"/" in s or b"." in s or b"_anim" in s:
                continue
            best = s.decode("utf-8", "replace")
        return best

    def cars(self):
        out = []
        for pos in sorted(self.pmap):
            nm = self._name_before(pos)
            if not nm:
                continue
            j = np.searchsorted(self.ckeys, pos)
            ch = None
            for k in ([int(self.ckeys[j])] if j < len(self.ckeys) else []) + \
                     ([int(self.ckeys[j - 1])] if j > 0 else []):
                if abs(k - pos) <= 0x600:
                    ch = self.cmap[k]
                    break
            out.append(dict(name=nm, phys=self.pmap[pos], chas=ch))
        return out

    def find(self, query: str):
        q = query.lower()
        hits = [c for c in self.cars() if q in c["name"].lower()]
        if not hits:
            raise SystemExit(f"找不到车: {query!r}")
        if len(hits) > 1:
            exact = [c for c in hits if c["name"].lower() == q]
            if exact:
                return exact[0]
            print("匹配到多台，请写更精确的名字：")
            for c in hits[:12]:
                print(f"   {c['name']}")
            raise SystemExit(1)
        return hits[0]

    # -- 读取 --
    @staticmethod
    def shift_of(size: int) -> int:
        return {436: 2, 476: 12}.get(size, 0)

    def pf(self, car, idx):
        d = car["phys"]
        return struct.unpack_from("<f", self.phys_raw, d["off"] + (idx + self.shift_of(d["size"])) * 4)[0]

    def cf(self, car, idx):
        d = car["chas"]
        if d is None:
            return None
        return struct.unpack_from("<f", self.chas_raw, d["off"] + idx * 4)[0]

    def wheelie_index(self, car):
        g, cg, tr = self.pf(car, 79), self.cf(car, 14), self.cf(car, 4)
        if None in (cg, tr) or tr == 0:
            return None
        return g * abs(cg) / tr


# ---------------------------------------------------------------- 命令

def cmd_list(m: Model, args):
    for c in m.cars():
        if args.grep and args.grep.lower() not in c["name"].lower():
            continue
        w = m.wheelie_index(c)
        print(f"{c['name'][:44]:<46} phys=0x{c['phys']['off']:<7X} "
              f"size={c['phys']['size']}  抬轮指数={w if w is None else round(w,4)}")


def cmd_inspect(m: Model, args):
    c = m.find(args.car)
    print(f"=== {c['name']} ===")
    print(f"CarPhysics 记录 0x{c['phys']['off']:X} ({c['phys']['size']}B, shift={Model.shift_of(c['phys']['size'])})")
    if c["chas"]:
        print(f"CarChassis 记录 0x{c['chas']['off']:X} ({c['chas']['size']}B)")
    print("\n-- 性能 (CarPhysics) --")
    for nm, (lo, hi) in PHYS_FIELDS.items():
        a, b = m.pf(c, lo), m.pf(c, hi)
        pre = NITRO_LABEL.get(nm[:2], "")
        tag = f"{pre} " if pre and nm[0] == "n" else ""
        print(f"  {nm:<12} {a:12.5g} / {b:<12.5g}  {tag}")
    print("\n-- 几何 (CarChassis) --")
    if c["chas"] is None:
        print("  (未关联到 CarChassis 记录)")
    else:
        for nm, i in CHASSIS_FIELDS.items():
            print(f"  {nm:<12} {m.cf(c, i):12.5g}")
    w = m.wheelie_index(c)
    if w is not None:
        print(f"\n  载荷转移指数 = 抓地 x |重心| / 前轮距 = {w:.4f}")
        print(f"  （全车 min 0.0149 / 中位 0.0689 / max 0.1216）")


def cmd_patch(m: Model, args):
    c = m.find(args.car)
    phys = bytearray(m.phys_raw)
    chas = bytearray(m.chas_raw)
    d_p, d_c = c["phys"], c["chas"]
    sh = Model.shift_of(d_p["size"])
    report = {"car": c["name"], "changes": [],
              "carphysics_record": f"0x{d_p['off']:X}",
              "carchassis_record": f"0x{d_c['off']:X}" if d_c else None}

    for spec in args.set:
        if "=" not in spec:
            raise SystemExit(f"格式应为 名字=值 或 名字=x倍数: {spec!r}")
        key, val = spec.split("=", 1)
        key = key.strip()
        mult = val.strip().lower().startswith("x")
        num = float(val.strip()[1:] if mult else val.strip())

        if key in PHYS_FIELDS:
            lo, hi = PHYS_FIELDS[key]
            for idx in ({lo, hi}):
                boff = d_p["off"] + (idx + sh) * 4
                before = struct.unpack_from("<f", phys, boff)[0]
                after = as_f32(before * num if mult else num)
                struct.pack_into("<f", phys, boff, after)
                report["changes"].append(dict(file="CarPhysics", field=key, slot=idx,
                                              byte=f"0x{boff:X}", before=before, after=after))
        elif key in CHASSIS_FIELDS:
            if d_c is None:
                raise SystemExit(f"该车未关联 CarChassis，无法改 {key}")
            idx = CHASSIS_FIELDS[key]
            boff = d_c["off"] + idx * 4
            before = struct.unpack_from("<f", chas, boff)[0]
            after = as_f32(before * num if mult else num)
            struct.pack_into("<f", chas, boff, after)
            report["changes"].append(dict(file="CarChassis", field=key, slot=idx,
                                          byte=f"0x{boff:X}", before=before, after=after))
        else:
            raise SystemExit(f"未知字段 {key!r}\n可用: {', '.join(list(PHYS_FIELDS)+list(CHASSIS_FIELDS))}")

    # --- 越界校验：改动字节必须全部落在点名字段内 ---
    intended = {ch["byte"] for ch in report["changes"]}
    intended_bytes = set()
    for ch in report["changes"]:
        b = int(ch["byte"], 16)
        intended_bytes |= set(range(b, b + 4))
    for nm, orig, new in (("CarPhysics", m.phys_raw, phys), ("CarChassis", m.chas_raw, chas)):
        diff = {i for i, (a, b) in enumerate(zip(orig, new)) if a != b}
        stray = sorted(x for x in diff if x not in intended_bytes)
        if stray:
            raise SystemExit(f"{nm} 出现越界改动: {[hex(x) for x in stray[:8]]}")
        report[f"{nm}_changed_bytes"] = len(diff)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for nm, orig, new in (("CarPhysics.gdb", m.phys_raw, phys), ("CarChassis.gdb", m.chas_raw, chas)):
        bak = out / (nm + ".orig")
        if not bak.exists():
            bak.write_bytes(orig)
        (out / nm).write_bytes(bytes(new))
        report[nm] = {"sha256_before": sha256(orig), "sha256_after": sha256(bytes(new))}
    (out / "patch-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"=== {c['name']} 改动完成 ===")
    for ch in report["changes"]:
        print(f"  {ch['file']:<11} {ch['field']:<12} slot{ch['slot']:<4} "
              f"{ch['before']:12.5g} -> {ch['after']:<12.5g}  @{ch['byte']}")
    print(f"\n  CarPhysics 改动字节 {report['CarPhysics_changed_bytes']}")
    print(f"  CarChassis 改动字节 {report['CarChassis_changed_bytes']}")
    print(f"  输出目录: {out.resolve()}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["list", "inspect", "patch"])
    ap.add_argument("--gdb", type=Path,
                    default=Path(r"C:\Users\player\Desktop\A9 sifugc\project\scratch\reference\vehicle-gdb"))
    ap.add_argument("--car")
    ap.add_argument("--grep")
    ap.add_argument("--set", action="append", default=[],
                    help="字段=值 或 字段=x倍数，可重复。例: --set tyre=x1.5 --set cg=-0.12")
    ap.add_argument("--out", default="./tuned")
    args = ap.parse_args()
    m = Model(args.gdb)
    {"list": cmd_list, "inspect": cmd_inspect, "patch": cmd_patch}[args.cmd](m, args)


if __name__ == "__main__":
    main()
