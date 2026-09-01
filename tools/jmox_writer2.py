#!/usr/bin/env python3
"""jmox 写入器 v2 —— 前缀宽度实测修正版。

M1 复盘：数据帧前缀实宽 14B（gap=−14 实测），绘制帧 24B（原结构自洽）。
    数据帧 14B = [4B 流ID?][type][02][cs u32][ds u32]   （cs@6, ds@10）
    绘制帧 24B = [X][05][Y][07][Z][k][02][cs][ds]       （cs@16, ds@20）
前缀里的 4B 流ID 与 14B"摘要"一律按管线元数据处理：原样保留或写零，装机裁决。

parse() 自动探测每帧前缀宽度（24/14/10 候选，ds+cs 双重校验），
assemble() 逐帧原宽重装、只更新 cs。
"""
from __future__ import annotations
import struct, sys, io
from pathlib import Path
import zstandard as zstd

if sys.platform == "win32" and not isinstance(sys.stdout, io.TextIOWrapper):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ZMAGIC = b"\x28\xb5\x2f\xfd"
_CCTX = zstd.ZstdCompressor(level=19)
_DCTX = zstd.ZstdDecompressor()


def parse(data: bytes):
    """返回 (header, frames)。真宽度 W 由下一帧 magic − 本帧尾 推出（gap 实测法）。

    cs/ds 相对 magic 的偏移与 W 无关（cs=[-8:-4], ds=[-4:]），因此先按内容
    定位所有帧，再用相邻帧几何关系求 W。
    """
    located = []
    off = 0
    while True:
        i = data.find(ZMAGIC, off)
        if i < 0:
            break
        do = _DCTX.decompressobj()
        try:
            out = do.decompress(memoryview(data)[i:])
        except Exception:
            off = i + 1
            continue
        consumed = (len(data) - i) - len(do.unused_data)
        ds = struct.unpack_from("<I", data, i - 4)[0]
        cs = struct.unpack_from("<I", data, i - 8)[0]
        if ds == len(out) and cs == consumed:
            located.append(dict(magic=i, consumed=consumed, ds=ds, cs=cs,
                                content=out))
            off = i + consumed
            continue
        off = i + 1
    for k, f in enumerate(located):
        if k + 1 < len(located):
            f["w"] = located[k + 1]["magic"] - (f["magic"] + f["consumed"])
        else:
            f["w"] = 24          # 末帧无法从后推，按绘制帧 24 处理（末帧必为绘制帧）
        f["pre"] = data[f["magic"] - f["w"]:f["magic"]]
    header = data[: located[0]["magic"] - located[0]["w"]]
    frames = located
    return header, frames


def parse_with_gaps(data: bytes):
    """同 parse，另返回每帧 (magic_i, consumed) 用于间隙审计。"""
    header, frames = parse(data)
    gaps = []
    for k in range(len(frames) - 1):
        gaps.append(frames[k + 1]["_next_pre"] - frames[k]["end"]
                    if "_next_pre" in frames[k] else None)
    return header, frames


def assemble(header: bytes, frames) -> bytes:
    """frames 的 content 可被替换；comp 缺失或 content 变化则重压缩，cs 同步。"""
    out = bytearray(header)
    for f in frames:
        content = f["content"]
        if "comp" not in f or f.get("content_changed"):
            comp = _CCTX.compress(content)
            pre = bytearray(f["pre"])
            cs_off = {24: 16, 14: 6, 10: 2}[f["w"]]
            struct.pack_into("<I", pre, cs_off, len(comp))
        else:
            comp = f["comp"]
            pre = f["pre"]
        out += pre
        out += comp
    return bytes(out)


def roundtrip_check(src: bytes) -> bool:
    header, frames = parse(src)
    rt = assemble(header, [dict(f, content_changed=False) for f in frames])
    _, f2 = parse(rt)
    return len(f2) == len(frames) and all(
        a["content"] == b["content"] for a, b in zip(frames, f2))


def main() -> int:
    src = Path(r"build\jmox_work\amg_one.jmodel").read_bytes()
    header, frames = parse(src)
    print(f"头部 {len(header)}B  {len(frames)} 帧")
    ws = [f["w"] for f in frames]
    print("前缀宽度分布:", {w: ws.count(w) for w in set(ws)})
    ok = roundtrip_check(src)
    print("round-trip:", "通过" if ok else "失败")

    # 写 T1v2：纯重压缩（内容不变）
    rt = assemble(header, [dict(f, content_changed=False) for f in frames])
    Path(r"build\jmox_work\amg_one_rt2.jmodel").write_bytes(rt)
    print("T1v2 纯重压缩版写出", f"{len(rt):,}B")

    # 写 T2v2：[0] Z×0.6、[4] U+0.25（前缀原样，仅 cs 更新）
    import numpy as np
    mod = [dict(f) for f in frames]
    n = len(mod[0]["content"]) // 8
    a = np.frombuffer(mod[0]["content"], dtype="<i2").reshape(n, 4).copy()
    a[:, 2] = (a[:, 2].astype(np.int64) * 6 // 10).astype(np.int16)
    a[:, 3] = 0x7FFF
    mod[0]["content"] = a.tobytes()
    mod[0]["content_changed"] = True
    u = np.frombuffer(mod[4]["content"], dtype="<u2").reshape(-1, 2).copy()
    u[:, 0] = (u[:, 0].astype(np.uint32) + 2048) % 65536
    mod[4]["content"] = u.tobytes()
    mod[4]["content_changed"] = True
    out = assemble(header, mod)
    Path(r"build\jmox_work\amg_one_squash_v2.jmodel").write_bytes(out)
    _, chk = parse(out)
    ok2 = (np.frombuffer(chk[0]["content"], dtype="<i2").reshape(n, 4) == a).all() \
        and chk[4]["content"] == mod[4]["content"]
    print("T2v2 压扁版写出+读回:", "通过" if ok2 else "失败",
          f"{len(out):,}B")
    return 0 if (ok and ok2) else 1


if __name__ == "__main__":
    sys.exit(main())
