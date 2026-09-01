#!/usr/bin/env python3
"""Find every 'virtual call -> ldp s,s,[x0]' pattern: reads of a (low,high)
field pair returned by a lookup().  This is the CarPhysics field access shape.
"""
import numpy as np, collections
from capstone import *
SO = r"C:\Users\player\Desktop\A9 sifugc\project\work\apk-590301\lib\arm64-v8a\libAsphalt9.so"
TEXT_VA, TEXT_SZ = 0x3456700, 0x319ef3c
raw=open(SO,"rb").read()
w  = np.frombuffer(raw[TEXT_VA:TEXT_VA+TEXT_SZ], dtype=np.uint32)
pc = TEXT_VA + np.arange(len(w), dtype=np.int64)*4

# LDP St,St2,[x0,#0]  -> 0x2D400000, imm7=0, Rn=0
ldp0 = ((w & 0xFFC00000)==0x2D400000) & (((w>>15)&0x7F)==0) & (((w>>5)&0x1F)==0)
# BLR xN
blr  = (w & 0xFFFFFC1F)==0xD63F0000
idx = np.nonzero(ldp0)[0]
print(f"'ldp s,s,[x0]' sites: {len(idx)}")

md = Cs(CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN)
hits=[]
for i in idx:
    for k in range(1,5):
        if i-k >= 0 and blr[i-k]:
            hits.append((int(pc[i]), int(pc[i-k]), k)); break
print(f"  ...preceded by BLR within 4 insns: {len(hits)}\n")

# group by enclosing 0x1000 page for a rough module view
byreg = collections.Counter(hex(v>>12<<12) for v,_,_ in hits)
print("distribution by 4K page:")
for p,c in byreg.most_common(20): print(f"   {p}  x{c}")

print(f"\n=== sites inside vehicle-physics region 0x3600000-0x3625000 ===")
for va, blrva, gap in hits:
    if not (0x3600000 <= va < 0x3625000): continue
    print(f"\n--- ldp at 0x{va:07x}  (blr at 0x{blrva:07x}) ---")
    for I in md.disasm(raw[blrva-0x30:va+0x18], blrva-0x30):
        mark = " <<<" if I.address in (va, blrva) else ""
        print(f"    0x{I.address:07x}  {I.mnemonic:<8s} {I.op_str}{mark}")
