#!/usr/bin/env python3
"""Scan auth-float accesses in the CarPhysics 'independent field' region
(component +0x748 .. +0x960, i.e. struct rel 0x3F0..0x600)."""
import numpy as np, collections
from capstone import *
SO = r"C:\Users\player\Desktop\A9 sifugc\project\work\apk-590301\lib\arm64-v8a\libAsphalt9.so"
TEXT_VA, TEXT_SZ = 0x3456700, 0x319ef3c
DEC={0x3535498,0x3535510,0x35355bc,0x353d7b4}; ENC={0x3535860}; ASSIGN={0x35854f4}
raw=open(SO,"rb").read()
w=np.frombuffer(raw[TEXT_VA:TEXT_VA+TEXT_SZ],dtype=np.uint32)
pc=TEXT_VA+np.arange(len(w),dtype=np.int64)*4
blm=(w&0xFC000000)==0x94000000; bm=(w&0xFC000000)==0x14000000
imm=(w&0x03FFFFFF).astype(np.int64); imm=np.where(imm&(1<<25),imm-(1<<26),imm)
bl_t=np.where(blm,pc+imm*4,-1); b_t=np.where(bm,pc+imm*4,-1)
allt=DEC|ENC|ASSIGN
sites=np.nonzero((blm&np.isin(bl_t,list(allt)))|(bm&np.isin(b_t,list(allt))))[0]
BASE=0x358
byoff=collections.defaultdict(list)
for i in sites:
    for k in range(1,10):
        j=i-k
        if j<0: break
        ins=w[j]
        if (ins&0xFFC00000)==0x91000000 and (ins&0x1F)==0:
            off=int((ins>>10)&0xFFF); rn=int((ins>>5)&0x1F)
            if rn!=31 and 0x740<=off<=0x980:
                byoff[off].append(int(pc[i]))
            break
KNOWN={0x934:"材质插值因子 t",0x940:"tyre_force"}
print(f"{'component':>10} {'struct rel':>11} {'独立区#':>8} {'访问':>5}  已知           位置")
for off in sorted(byoff):
    rel=off-BASE; idx=(rel-0x3F0)//12 if rel>=0x3F0 and (rel-0x3F0)%12==0 else None
    ss=" ".join(f"0x{a:07x}" for a in sorted(byoff[off])[:3])
    print(f"    +0x{off:03x} {'+0x%03x'%rel:>11} {str(idx) if idx is not None else '-':>8} {len(byoff[off]):5d}  {KNOWN.get(off,''):<14s}{ss}")
