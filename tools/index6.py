#!/usr/bin/env python3
"""6.0.0k 车辆索引（权威版）。

gdb 通用结构:
    [记录体区] [u32 条数] [条数 x 32B 描述符: key,off,size,tag]
**记录体是纯数据，身份只存在于描述符的 key** —— 整车物理移植可行的根本原因。

关联方式:  CarDef 中 tag=0xA14668DB 的 351 条"车辆定义"记录，
每条**同时**含车名字符串与 CarPhysics / CarChassis 的 key。
用"记录内包含"关联，取代早期"最近前置车名"的启发式——后者曾把
VLF Force V10 误判成 Ferrari LaFerrari。
"""
from __future__ import annotations
import struct, json, re, sys, io
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

G = Path(r"C:\Users\player\Desktop\a9模型\gdb-6.0.0k")
OUT = Path(r"C:\Users\player\Desktop\a9模型\03-车辆档案")
TAG_PHYS, TAG_CHAS, TAG_CARDEF = 0x83C70E66, 0x924E4D88, 0xA14668DB


def table(data: bytes):
    """尾部回退定位描述符表（起始不保证 4 字节对齐）。"""
    n = len(data); co = n
    while co - 32 >= 0:
        t = struct.unpack_from("<Q", data, co - 32 + 24)[0]
        if t >> 32 or t == 0: break
        off, size = struct.unpack_from("<QQ", data, co - 32 + 8)
        if off + size > n or not 0 < size <= 1 << 20: break
        co -= 32
    cnt = struct.unpack_from("<I", data, co - 4)[0]
    assert cnt == (n - co) // 32
    return co - 4, [dict(zip(("key", "off", "size", "tag"),
                             struct.unpack_from("<QQQQ", data, co + i * 32)))
                    for i in range(cnt)]


def build():
    cd = (G / "CarDef.gdb").read_bytes()
    cp = (G / "CarPhysics.gdb").read_bytes()
    ch = (G / "CarChassis.gdb").read_bytes()
    pk = {d["key"]: d for d in table(cp)[1] if d["tag"] == TAG_PHYS}
    ck = {d["key"]: d for d in table(ch)[1] if d["tag"] == TAG_CHAS}

    out = {}
    for r in table(cd)[1]:
        if r["tag"] != TAG_CARDEF: continue
        b = cd[r["off"]:r["off"] + r["size"]]
        # 车辆定义记录头部固定布局: +0 u64, +8 u64, +16 u32 名字长度, +20 名字
        nlen = struct.unpack_from("<I", b, 16)[0]
        name = (b[20:20 + nlen].decode("ascii", "replace") if 0 < nlen <= 64
                else f"?0x{r['off']:X}")
        P = C = None
        for i in range(len(b) - 7):
            v = struct.unpack_from("<Q", b, i)[0]
            if P is None and v in pk: P = pk[v]
            if C is None and v in ck: C = ck[v]
            if P and C: break
        e = dict(cardef_off=r["off"])
        if P: e["physics"] = dict(key=f"0x{P['key']:016X}", off=P["off"], size=P["size"])
        if C: e["chassis"] = dict(key=f"0x{C['key']:016X}", off=C["off"], size=C["size"])
        # 同名多条（基础定义 + 变体）：以 physics 偏移区分
        k = name
        if k in out and out[k].get("physics", {}).get("off") != e.get("physics", {}).get("off"):
            k = f"{name} #{sum(1 for x in out if x.startswith(name)) + 1}"
        out[k] = e
    return out


def load():
    p = OUT / "index-6.0.0k.json"
    if not p.exists(): return build()
    return json.loads(p.read_text(encoding="utf-8"))


def resolve(idx, q: str):
    """精确名优先，其次唯一子串匹配；歧义则报错列出候选。"""
    if q in idx: return q, idx[q]
    hit = [k for k in idx if q.lower() in k.lower()]
    exact = [k for k in hit if k.lower() == q.lower()]
    if exact: return exact[0], idx[exact[0]]
    if len(hit) == 1: return hit[0], idx[hit[0]]
    if not hit: sys.exit(f"找不到车: {q!r}")
    sys.exit(f"{q!r} 有歧义，候选:\n  " + "\n  ".join(hit))


if __name__ == "__main__":
    idx = build()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "index-6.0.0k.json").write_text(json.dumps(idx, ensure_ascii=False, indent=1),
                                           encoding="utf-8")
    both = sum(1 for v in idx.values() if "physics" in v and "chassis" in v)
    print(f"车辆定义 {len(idx)} 条   物理+底盘齐全 {both}")
    if len(sys.argv) > 1:
        for q in sys.argv[1:]:
            k, v = resolve(idx, q)
            p, c = v.get("physics"), v.get("chassis")
            print(f"\n{k}")
            print(f"  physics  off=0x{p['off']:X}  size={p['size']}  key={p['key']}" if p else "  physics  无")
            print(f"  chassis  off=0x{c['off']:X}  size={c['size']}  key={c['key']}" if c else "  chassis  无")
