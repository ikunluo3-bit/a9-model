#!/usr/bin/env python3
"""A9-business.gdb 面板记录扫描：内部代号 + rank + 面板极速。

记录格式（从字符串反推）:
    名字前 12 字节 = cid(u32), 0, 名字长度(u32)
    名字后 33 字节 -> u32 nt -> nt*8 字节 -> 5 个 u64:
        rank_lo, rank_hi, ?, 极速_lo x10, 极速_hi x10
"""
import sys, re, struct, io, json
from pathlib import Path
sys.path.insert(0, ".")
from index6 import G
if not isinstance(sys.stdout, io.TextIOWrapper):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

biz = (G / "A9-business.gdb").read_bytes()
cd = (G / "CarDef.gdb").read_bytes()
rows = {}
for m in re.finditer(rb"[A-Za-z0-9][ -~]{2,48}", biz):
    st, en = m.start(), m.end()
    if st < 12: continue
    cid, z, n = struct.unpack_from("<III", biz, st - 12)
    if z or n != en - st: continue
    p = en + 33
    try:
        nt = struct.unpack_from("<I", biz, p)[0]
        if nt > 64: continue
        s = struct.unpack_from("<5Q", biz, p + 4 + 8 * nt)
    except Exception:
        continue
    if not (500 <= s[0] <= 60000 and s[0] <= s[1] <= 60000): continue
    if not (100 <= s[3] <= 20000 and s[3] <= s[4] <= 20000): continue
    rows.setdefault(m.group().decode(), dict(cid=cid, rank_lo=s[0], rank_hi=s[1],
                                             ts_lo=s[3] / 10, ts_hi=s[4] / 10))
print(f"面板记录 {len(rows)} 条")
if len(sys.argv) > 1:
    q = sys.argv[1].lower()
    hit = {k: v for k, v in rows.items() if q in k.lower()}
    print(f"匹配 {q!r}: {len(hit)} 条")
    for k, v in sorted(hit.items(), key=lambda x: -x[1]["rank_hi"]):
        pos = cd.lower().find(k.lower().encode())
        print(f"  {k:<34} rank {v['rank_lo']:>5}-{v['rank_hi']:<5} "
              f"面板极速 {v['ts_lo']:.1f}-{v['ts_hi']:.1f}   CarDef@"
              + (f"0x{pos:X}" if pos >= 0 else "未出现"))
Path(r"C:\Users\player\Desktop\a9模型\03-车辆档案\business-6.0.0k.json").write_text(
    json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
