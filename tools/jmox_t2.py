#!/usr/bin/env python3
"""T2-slim：[0] Z×0.6 / [4] U+0.25 且摘要清零 / 其余帧保留原始压缩字节。

变量隔离设计：
  * 若 T1（纯重压缩）正常而本版正常  → 摘要确实不验、管线全通，进入 M3
  * 若 T1 正常而本版崩              → [4] 摘要清零或内容修改触发校验
  * 若本版也崩且 T1 崩              → zstd 参数问题
"""
from __future__ import annotations
import struct, sys, io
from pathlib import Path
import numpy as np
import zstandard as zstd

if sys.platform == "win32" and not isinstance(sys.stdout, io.TextIOWrapper):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ZMAGIC = b"\x28\xb5\x2f\xfd"


def parse_raw(src: bytes):
    """返回 (header, [(prefix, 原始压缩字节)])，不解压重排。"""
    dctx = zstd.ZstdDecompressor()
    header = src[: src.find(ZMAGIC) - 24]
    raws = []
    off = src.find(ZMAGIC) - 24
    while True:
        i = src.find(ZMAGIC, off)
        if i < 0:
            break
        do = dctx.decompressobj()
        try:
            out = do.decompress(memoryview(src)[i:])
        except Exception:
            off = i + 1
            continue
        pre = src[i - 24:i]
        if len(pre) == 24 and struct.unpack_from("<I", pre, 20)[0] == len(out):
            consumed = (len(src) - i) - len(do.unused_data)
            raws.append((pre, src[i:i + consumed]))
            off = i + consumed
            continue
        off = i + 1
    return header, raws


def main() -> int:
    src = Path(r"build\jmox_work\amg_one.jmodel").read_bytes()
    header, raws = parse_raw(src)
    dctx = zstd.ZstdDecompressor()
    cctx = zstd.ZstdCompressor(level=19)

    # 解出 [0]/[4] 原内容用于构造修改版
    pos = dctx.decompressobj().decompress(memoryview(src)[src.find(ZMAGIC) + 24:])
    # 上面的流式解法拿不到 [4]，老实用 parse（writer 里有）
    sys.path.insert(0, str(Path(__file__).parent))
    from jmox_writer import parse
    _, frames = parse(src)

    n = len(frames[0][1]) // 8
    a = np.frombuffer(frames[0][1], dtype="<i2").reshape(n, 4).copy()
    a[:, 2] = (a[:, 2].astype(np.int64) * 6 // 10).astype(np.int16)
    a[:, 3] = 0x7FFF
    new0 = a.tobytes()
    u = np.frombuffer(frames[4][1], dtype="<u2").reshape(-1, 2).copy()
    u[:, 0] = (u[:, 0].astype(np.uint32) + 2048) % 65536
    new4 = u.tobytes()

    out = bytearray(header)
    for i, (pre, comp) in enumerate(raws):
        if i == 0:
            c2 = cctx.compress(new0)
            p2 = bytearray(pre)
            struct.pack_into("<I", p2, 16, len(c2))
            out += p2
            out += c2
        elif i == 4:
            c2 = cctx.compress(new4)
            p2 = bytearray(pre)
            p2[0:14] = b"\x00" * 14
            struct.pack_into("<I", p2, 16, len(c2))
            out += p2
            out += c2
        else:
            out += pre
            out += comp
    dst = Path(r"build\jmox_work\amg_one_squash_zerodigest.jmodel")
    dst.write_bytes(bytes(out))
    print(f"T2-slim 写出 {len(out):,}B（[0] Z×0.6，[4] U+0.25+摘要清零，其余 81 帧原始字节）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
