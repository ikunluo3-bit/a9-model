#!/usr/bin/env python3
"""整车物理移植：把 A 车的物理/底盘记录整体搬到 B 车身上。

**为什么可行**
    gdb = [24B 文件头][记录体区][u32 条数][条数 x 32B 描述符 key,off,size,tag]
    记录体是**纯数据**，车辆身份只存在于描述符的 key。
    因此把 A 的记录体原样写进 B 的记录位置，B 仍是 B（key 不变、
    CarDef 引用不变、图鉴/车库/联机校验都不受影响），但**跑起来完全是 A**。

尺寸不同时自动重建整个 gdb（重排记录 + 更新描述符 off/size + 更新文件头尾指针）。

用法:
  python transplant.py --from "McLaren Senna" --to "BMW Z4 LCI E89" --preview
  python transplant.py --from "McLaren Senna" --to "BMW Z4 LCI E89" --with-chassis --maxed --apply
  python transplant.py --list-donors            # 按几项关键指标列出适合当供体的车
"""
from __future__ import annotations
import argparse, hashlib, json, struct, sys, io
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from index6 import table, resolve, build as build_index, G, TAG_PHYS, TAG_CHAS

if sys.platform == "win32" and not isinstance(sys.stdout, io.TextIOWrapper):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

OUT_DEFAULT = Path(r"C:\Users\player\Desktop\a9模型\tuned-transplant")
HDR = 0x18

# 满改：把 (低级值, 满级值) 对里的低位写成满位
PAIRS = [(22, 23), (72, 73), (78, 79), (19, 21), (14, 16),
         (34, 35), (36, 37), (38, 39), (42, 43), (44, 45), (46, 47),
         (50, 51), (52, 53), (54, 55), (58, 59), (60, 61),
         (76, 77),   # 操控
         (30, 31)]   # 下压力（抬轮总开关；291/295 方向一致，属升级对）
#——pairscan 新确认：全库 295/295 方向一致，
                     # 开发用参考车 Fastest/Slowest Car 均为 (0.0, 1.0)
# 待判候选（方向一致但语义未知，暂不锁）: (5,6) 295/295、(30,31) 291/295
SHOW = [(23, "极速"), (73, "加速"), (79, "抓地"), (21, "转向锐度"),
        (77, "操控77"), (76, "操控76"), (53, "蓝喷加成"), (55, "蓝喷维持"),
        (51, "蓝喷消耗"), (61, "紫喷加成"), (99, "压缩阻尼"), (100, "回弹阻尼")]
CHASSIS = [(0, "质量kg"), (4, "前轮距"), (5, "后轮距"), (6, "轴距"),
           (9, "前轮半径"), (10, "后轮半径"), (14, "重心高")]


def sha(b): return hashlib.sha256(b).hexdigest().upper()


def rebuild(data: bytes, replace: dict[int, bytes]) -> bytes:
    """replace: {原off: 新记录体}。尺寸可变，整库重排。"""
    co, ds = table(data)
    pad = data[max(d["off"] + d["size"] for d in ds):co]   # 记录区与计数字段之间的填充，原样保留
    out = bytearray(data[:HDR])
    newds = []
    for d in ds:
        body = replace.get(d["off"], data[d["off"]:d["off"] + d["size"]])
        newds.append(dict(key=d["key"], off=len(out), size=len(body), tag=d["tag"]))
        out += body
    end = len(out)
    struct.pack_into("<Q", out, 16, end)          # 文件头里的记录区结束指针
    out += pad
    out += struct.pack("<I", len(newds))
    for d in newds:
        out += struct.pack("<QQQQ", d["key"], d["off"], d["size"], d["tag"])
    return bytes(out)


def alias(data: bytes, key: int, off: int, size: int) -> bytes:
    """让 key 这条描述符直接指向另一条记录体（不搬字节、不改文件长度）。

    记录体只读，两条描述符共享同一段数据是安全的；
    好处是**文件长度分毫不变**，回封时不必改 Pegasus manifest 里记的明文大小。
    """
    co, ds = table(data)
    out = bytearray(data)
    tbl = co + 4
    for i, d in enumerate(ds):
        if d["key"] == key:
            struct.pack_into("<QQ", out, tbl + i * 32 + 8, off, size)
            return bytes(out)
    sys.exit(f"描述符里找不到 key 0x{key:016X}")


def maxed(body: bytes) -> bytes:
    b = bytearray(body)
    n = len(b) // 4
    for lo, hi in PAIRS:
        if hi < n:
            struct.pack_into("<f", b, lo * 4, struct.unpack_from("<f", b, hi * 4)[0])
    return bytes(b)


def fmt(body: bytes, spec):
    return {lbl: struct.unpack_from("<f", body, i * 4)[0] for i, lbl in spec
            if i * 4 + 4 <= len(body)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="src")
    ap.add_argument("--to", dest="dst")
    ap.add_argument("--with-chassis", action="store_true", help="连几何一起搬（真·同一台车）")
    ap.add_argument("--maxed", action="store_true", help="移植后再满改（低级值:=满级值）")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--out", default=str(OUT_DEFAULT))
    ap.add_argument("--list-donors", action="store_true")
    a = ap.parse_args()

    idx = build_index()
    cp = (G / "CarPhysics.gdb").read_bytes()
    ch = (G / "CarChassis.gdb").read_bytes()

    if a.list_donors:
        rows = []
        for k, v in idx.items():
            p = v.get("physics")
            if not p or p["size"] != 428: continue
            b = cp[p["off"]:p["off"] + p["size"]]
            f = fmt(b, SHOW)
            rows.append((k, f["极速"], f["抓地"], f["操控77"], f["转向锐度"], f["蓝喷维持"]))
        rows.sort(key=lambda r: -(r[3] * 100 + r[1] / 10))
        print(f"{'车':<34}{'极速':>8}{'抓地':>8}{'操控77':>8}{'转向':>9}{'蓝喷维持':>10}")
        for r in rows[:40]:
            print(f"{r[0][:32]:<34}{r[1]:8.1f}{r[2]:8.3f}{r[3]:8.2f}{r[4]:9.0f}{r[5]:10.0f}")
        return

    if not a.src or not a.dst: sys.exit("需要 --from 和 --to")
    sk, sv = resolve(idx, a.src)
    dk, dv = resolve(idx, a.dst)
    print(f"供体: {sk}\n受体: {dk}\n")

    sp, dp = sv["physics"], dv["physics"]
    sbody = cp[sp["off"]:sp["off"] + sp["size"]]
    dbody = cp[dp["off"]:dp["off"] + dp["size"]]
    nbody = maxed(sbody) if a.maxed else sbody

    print(f"CarPhysics  供体 size={sp['size']}  受体 size={dp['size']}"
          + ("  尺寸相同→原地覆盖" if sp["size"] == dp["size"] else "  尺寸不同→整库重排"))
    print(f"  {'字段':<12}{'受体原值':>14}{'移植后':>14}")
    fo, fn = fmt(dbody, SHOW), fmt(nbody, SHOW)
    for _, lbl in SHOW:
        if lbl in fo and lbl in fn:
            print(f"  {lbl:<12}{fo[lbl]:14.4g}{fn[lbl]:14.4g}")

    new_cp = rebuild(cp, {dp["off"]: nbody})
    new_ch = ch
    if a.with_chassis:
        sc, dc = sv["chassis"], dv["chassis"]
        scb = ch[sc["off"]:sc["off"] + sc["size"]]
        dcb = ch[dc["off"]:dc["off"] + dc["size"]]
        print(f"\nCarChassis  供体 size={sc['size']}  受体 size={dc['size']}"
              + ("  尺寸相同→原地覆盖" if sc["size"] == dc["size"] else "  尺寸不同→改指向"))
        print(f"  {'字段':<12}{'受体原值':>14}{'移植后':>14}")
        co_, cn_ = fmt(dcb, CHASSIS), fmt(scb, CHASSIS)
        for _, lbl in CHASSIS:
            if lbl in co_ and lbl in cn_:
                print(f"  {lbl:<12}{co_[lbl]:14.4g}{cn_[lbl]:14.4g}")
        gi = lambda f: f["抓地"] * abs(co_["重心高"]) / co_["前轮距"]
        print(f"\n  抬轮指数  {fo['抓地']*abs(co_['重心高'])/co_['前轮距']:.4f}"
              f"  →  {fn['抓地']*abs(cn_['重心高'])/cn_['前轮距']:.4f}")
        if sc["size"] == dc["size"]:
            new_ch = rebuild(ch, {dc["off"]: scb})
        else:
            # 尺寸不同：改指向而不搬字节，文件长度保持不变（manifest 记的明文大小才对得上）
            new_ch = alias(ch, int(dc["key"], 16), sc["off"], sc["size"])
            print("  尺寸不同 → 采用**描述符改指向**：受体底盘描述符直接指向供体记录，"
                  "文件长度不变")
    else:
        gi_o = fo["抓地"] * abs(fmt(ch[dv['chassis']['off']:dv['chassis']['off']+dv['chassis']['size']], CHASSIS)["重心高"])
        c = fmt(ch[dv['chassis']['off']:dv['chassis']['off']+dv['chassis']['size']], CHASSIS)
        print(f"\n  几何保留（受体自身）  抬轮指数 "
              f"{fo['抓地']*abs(c['重心高'])/c['前轮距']:.4f} → {fn['抓地']*abs(c['重心高'])/c['前轮距']:.4f}")

    print(f"\nCarPhysics {len(cp):,} → {len(new_cp):,}B   CarChassis {len(ch):,} → {len(new_ch):,}B")

    # 自检：把改动撤回后必须与原文件逐字节相同
    chk = rebuild(new_cp, {[d for d in table(new_cp)[1] if d["key"] == int(dp["key"], 16)][0]["off"]: dbody})
    print("回滚自检 CarPhysics:", "通过" if chk == cp else "**失败**")
    if chk != cp: sys.exit(1)

    if a.apply:
        out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
        (out / "CarPhysics.gdb").write_bytes(new_cp)
        (out / "CarChassis.gdb").write_bytes(new_ch)
        (out / "transplant.json").write_text(json.dumps(
            dict(donor=sk, recipient=dk, with_chassis=a.with_chassis, maxed=a.maxed,
                 sha_physics=sha(new_cp), sha_chassis=sha(new_ch)),
            ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n已写出 {out}")


if __name__ == "__main__":
    main()
