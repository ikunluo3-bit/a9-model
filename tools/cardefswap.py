#!/usr/bin/env python3
"""CarDef 移植：让受体整条车辆定义用供体的内容。

为什么必须动 CarDef
    只换 3D 模型资源必崩（女武神 / 杰AB / 节点集严格子集的 Fordzilla P1 都试过）。
    崩因是引擎遍历车辆材质、按名取 shader 参数 `powderFactor`，
    模型换了、车辆定义没换 -> 空 optional -> 引擎主动断言自杀。

两种做法
    alias  受体描述符指向供体记录。文件长度不变，但**两条车共用一条定义，
           游戏按身份去重，受体在车库里会直接消失** —— 已实测，不可用。
    copy   把供体记录复制进受体槽位，只保留受体自己的身份头：
             +0  u64  身份（= 描述符 key 低 32 位 - 0x40000000）
             +8  u64  序号
             +16 起   名字长度 + 名字 + 其余定义  <- 全部来自供体
           再把记录里的 physics / chassis key 改回受体自己的，
           这样物理仍走受体记录（已由 transplant.py 移植成供体物理并满改）。
           记录变长 -> 整库重排；CarDef 尾部 376,612B 依赖表只按 key 引用、
           不含记录偏移，重排安全（已核验：区内 47,076 个 u64 命中记录偏移 0 个）。
"""
from __future__ import annotations
import argparse, json, struct, sys, io
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from index6 import table, resolve, build as build_index, G
from transplant import alias, rebuild

if sys.platform == "win32" and not isinstance(sys.stdout, io.TextIOWrapper):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BASE = Path(__file__).resolve().parents[1]
TRANSPLANT = BASE / "tuned-transplant"
OUT = BASE / "tuned-cardef"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="src", default="Aston Martin Valkyre")
    ap.add_argument("--to", dest="dst", default="Chevrolet Camaro LT")
    ap.add_argument("--mode", choices=("alias", "copy"), default="copy")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    idx = build_index()
    sk, sv = resolve(idx, a.src)
    dk, dv = resolve(idx, a.dst)
    cd = (G / "CarDef.gdb").read_bytes()
    descs = table(cd)[1]
    src_rec = next(d for d in descs if d["off"] == sv["cardef_off"])
    dst_rec = next(d for d in descs if d["off"] == dv["cardef_off"])
    print(f"供体 {sk}  CarDef 0x{src_rec['off']:X} size={src_rec['size']}")
    print(f"受体 {dk}  CarDef 0x{dst_rec['off']:X} size={dst_rec['size']} "
          f"key=0x{dst_rec['key']:016X}")

    if a.mode == "alias":
        new_cd = alias(cd, dst_rec["key"], src_rec["off"], src_rec["size"])
        print("警告：alias 模式会让受体在车库里消失（已实测），仅供对照")
    else:
        head = cd[dst_rec["off"]:dst_rec["off"] + 16]          # 受体身份头
        body = bytearray(head + cd[src_rec["off"] + 16:src_rec["off"] + src_rec["size"]])
        print(f"  身份头保留受体: +0=0x{struct.unpack_from('<Q', body, 0)[0]:X} "
              f"+8={struct.unpack_from('<Q', body, 8)[0]}")
        # 记录里所有 gdb key 按出现顺序配对回填。
        # 只补 physics/chassis 两个不够：科迈罗 +410 还有第 4 个车辆专属 key，
        # 漏了它 -> 游戏认不出这辆车 -> 车库里直接消失（已实测）。
        LO, HI = 0x0000090000000000, 0x00000A0000000000
        def keylist(buf):
            out = []
            i = 0
            while i <= len(buf) - 8:
                v = struct.unpack_from("<Q", buf, i)[0]
                if LO <= v <= HI:
                    out.append((i, v)); i += 8
                else:
                    i += 1
            return out
        src_keys = keylist(cd[src_rec["off"]:src_rec["off"] + src_rec["size"]])
        dst_keys = keylist(cd[dst_rec["off"]:dst_rec["off"] + dst_rec["size"]])
        if len(src_keys) != len(dst_keys):
            sys.exit(f"两条记录 key 数不同 {len(src_keys)} vs {len(dst_keys)}，需人工核对")
        for (si, sval), (di, dval) in zip(src_keys, dst_keys):
            if sval == dval:
                print(f"  +{si:<5d} 0x{sval:016X}  两车共用，保持")
                continue
            n = 0
            for i in range(len(body) - 7):
                if struct.unpack_from("<Q", body, i)[0] == sval:
                    struct.pack_into("<Q", body, i, dval); n += 1
            print(f"  +{si:<5d} 0x{sval:016X} -> 0x{dval:016X}  回填 {n} 处")
            if not n:
                sys.exit("回填失败")
        new_cd = rebuild(cd, {dst_rec["off"]: bytes(body)})

    print(f"CarDef {len(cd):,} -> {len(new_cd):,}B  (差 {len(new_cd)-len(cd):+d})")

    cp = (TRANSPLANT / "CarPhysics.gdb").read_bytes()
    ch = (TRANSPLANT / "CarChassis.gdb").read_bytes()
    print("CarPhysics / CarChassis 沿用 tuned-transplant（女武神物理+底盘，17 对升级值已满改）")

    if a.apply:
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / "CarDef.gdb").write_bytes(new_cd)
        (OUT / "CarPhysics.gdb").write_bytes(cp)
        (OUT / "CarChassis.gdb").write_bytes(ch)
        (OUT / "plan.json").write_text(json.dumps(
            dict(donor=sk, recipient=dk, mode=a.mode,
                 cardef_delta=len(new_cd) - len(cd)), ensure_ascii=False, indent=2),
            encoding="utf-8")
        print("已写出", OUT)


if __name__ == "__main__":
    main()
