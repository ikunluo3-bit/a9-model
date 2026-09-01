#!/usr/bin/env python3
"""CarDef.gdb 尾部依赖表解析。

布局（记录区结束 -> 计数字段之间的 376,612 B）:
    u32 条数
    每条: u64 记录key | u32 ? | u64 ? | u32 n | n × u64 依赖key
只按 key 引用，**不含任何记录偏移** —— 所以重排记录区不会破坏它。
"""
import sys, struct, io
sys.path.insert(0, ".")
from index6 import table, G
if not isinstance(sys.stdout, io.TextIOWrapper):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

d = (G / "CarDef.gdb").read_bytes()
co, ds = table(d)
end = max(x["off"] + x["size"] for x in ds)
r = d[end:co]
n = struct.unpack_from("<I", r, 0)[0]
print(f"尾部区 {len(r):,}B  声明条数 {n}")
p = 4
entries = []
for i in range(n):
    if p + 24 > len(r): print(f"  第 {i} 条越界，解析中断"); break
    key, a, gk, cnt = struct.unpack_from("<QIQI", r, p)
    p += 24
    if p + cnt * 8 > len(r): print(f"  第 {i} 条依赖数 {cnt} 越界"); break
    deps = struct.unpack_from(f"<{cnt}Q", r, p)
    p += cnt * 8
    entries.append((key, a, gk, deps))
print(f"成功解析 {len(entries)} 条，消耗 {p:,}/{len(r):,} 字节  剩余 {len(r)-p}")
if entries:
    kmap = {x["key"]: x for x in ds}
    hit = sum(1 for k, *_ in entries if k in kmap)
    print(f"首字段命中 CarDef 记录 key: {hit}/{len(entries)}")
    a_vals = {e[1] for e in entries}
    print(f"第二字段取值集合: {sorted(a_vals)[:8]}   依赖数范围 "
          f"{min(len(e[3]) for e in entries)}~{max(len(e[3]) for e in entries)}")
