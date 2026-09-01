#!/usr/bin/env python3
"""For every 'BLR -> ldp s,s,[x0]' site, recover which table object was used
(the 'ldr x8,[xB,#off]' feeding the virtual call) and what happens to the result."""
import numpy as np, collections
from capstone import *
SO = r"C:\Users\player\Desktop\A9 sifugc\project\work\apk-590301\lib\arm64-v8a\libAsphalt9.so"
TEXT_VA, TEXT_SZ = 0x3456700, 0x319ef3c
raw=open(SO,"rb").read()
w  = np.frombuffer(raw[TEXT_VA:TEXT_VA+TEXT_SZ], dtype=np.uint32)
pc = TEXT_VA + np.arange(len(w), dtype=np.int64)*4
ldp0 = ((w & 0xFFC00000)==0x2D400000) & (((w>>15)&0x7F)==0) & (((w>>5)&0x1F)==0)
blr  = (w & 0xFFFFFC1F)==0xD63F0000
md = Cs(CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN)

rows=[]
for i in np.nonzero(ldp0)[0]:
    bi=None
    for k in range(1,5):
        if i-k>=0 and blr[i-k]: bi=i-k; break
    if bi is None: continue
    tbl=vslot=None
    for k in range(1,14):                       # back-trace: ldr x9,[x8,#slot] & ldr x8,[xB,#off]
        j=bi-k
        if j<0: break
        ins=w[j]
        if (ins & 0xFFC00000)==0xF9400000:      # ldr Xt,[Xn,#imm]
            off=int(((ins>>10)&0xFFF)*8); rt=int(ins&0x1F); rn=int((ins>>5)&0x1F)
            if vslot is None and rt==9: vslot=off
            elif tbl is None and rt==8 and rn!=31: tbl=off
        if tbl is not None and vslot is not None: break
    # what happens after: find the store of the result
    dst=None
    for k in range(1,26):
        j=i+k
        if j>=len(w): break
        ins=w[j]
        if (ins & 0xFFC00000)==0xBD000000:      # str s,[Xn,#imm]
            dst=int(((ins>>10)&0xFFF)*4); break
    rows.append(dict(ldp=int(pc[i]), tbl=tbl, vslot=vslot, dst=dst))

print(f"{'ldp 位置':>12} {'表对象偏移':>12} {'vtable槽':>9} {'结果写入':>10}")
for r in sorted(rows, key=lambda r:r["ldp"]):
    t = f"0x{r['tbl']:x}" if r['tbl'] is not None else "?"
    v = f"+0x{r['vslot']:x}" if r['vslot'] is not None else "?"
    d = f"+0x{r['dst']:x}" if r['dst'] is not None else "?"
    print(f"  0x{r['ldp']:07x} {t:>12} {v:>9} {d:>10}")
print()
c=collections.Counter(r['tbl'] for r in rows if r['tbl'] is not None)
print("表对象使用频次:")
for t,n in c.most_common(): print(f"   [obj+0x{t:x}]  x{n}")
