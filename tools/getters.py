#!/usr/bin/env python3
"""Enumerate authenticated-float field getters:  add x0,x0,#imm ; b <decoder>

Each such 2-instruction thunk is one physics field accessor.
Offset is relative to the object passed in x0 (for CarPhysics: component+0x358).
"""
import numpy as np, json
from pathlib import Path

SO = r"C:\Users\player\Desktop\A9 sifugc\project\work\apk-590301\lib\arm64-v8a\libAsphalt9.so"
TEXT_VA, TEXT_SZ = 0x3456700, 0x319ef3c
OUT = Path(r"C:\Users\player\Desktop\a9模型")

raw = open(SO, "rb").read()
w = np.frombuffer(raw[TEXT_VA:TEXT_VA+TEXT_SZ], dtype=np.uint32)
pc = TEXT_VA + np.arange(len(w), dtype=np.int64)*4

# add x0, x0, #imm  (64-bit, shift=0, Rn=0, Rd=0)
addm = ((w & 0xFFC00000) == 0x91000000) & (((w >> 5) & 0x1F) == 0) & ((w & 0x1F) == 0)
# b <target>
bm = (w & 0xFC000000) == 0x14000000
imm26 = (w & 0x03FFFFFF).astype(np.int64)
imm26 = np.where(imm26 & (1 << 25), imm26 - (1 << 26), imm26)
btgt = np.where(bm, pc + imm26*4, -1)

idx = np.nonzero(addm[:-1] & bm[1:])[0]
rows = []
for i in idx:
    off = int((w[i] >> 10) & 0xFFF)
    rows.append(dict(thunk=int(pc[i]), offset=off, target=int(btgt[i+1])))

tgt_count = {}
for r in rows:
    tgt_count[r["target"]] = tgt_count.get(r["target"], 0) + 1
print(f"total 'add x0,x0,#imm; b X' thunks: {len(rows)}")
print("\ntop branch targets (candidate accessors):")
for t, c in sorted(tgt_count.items(), key=lambda kv: -kv[1])[:12]:
    print(f"   0x{t:07x}  x{c}")

DEC = {0x3535498, 0x3535510, 0x353547c, 0x3535440}
sel = [r for r in rows if r["target"] in DEC]
sel.sort(key=lambda r: r["offset"])
print(f"\nthunks branching to a known auth-float decoder: {len(sel)}")
print(f"{'thunk':>11} {'offset':>8} {'/12':>7}  target")
for r in sel:
    q, m = divmod(r["offset"], 12)
    print(f"  0x{r['thunk']:07x} {r['offset']:8d}=0x{r['offset']:03x} {q:5d}{'' if m==0 else '+%d'%m}  0x{r['target']:07x}")
json.dump(rows, open(OUT/"01-代码层"/"auth-float-thunks.json","w"), indent=1)
