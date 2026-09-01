#!/usr/bin/env python3
"""Scan all auth-float accesses at wheel-struct offsets (multiples of 12, 0..0xCB)."""
import numpy as np, collections
from capstone import *
SO = r"C:\Users\player\Desktop\A9 sifugc\project\work\apk-590301\lib\arm64-v8a\libAsphalt9.so"
TEXT_VA, TEXT_SZ = 0x3456700, 0x319ef3c
DEC={0x3535498,0x3535510}; ENC={0x3535860,0x3535ef0}; ASSIGN={0x35854f4}
raw=open(SO,"rb").read()
w=np.frombuffer(raw[TEXT_VA:TEXT_VA+TEXT_SZ],dtype=np.uint32)
pc=TEXT_VA+np.arange(len(w),dtype=np.int64)*4
blm=(w&0xFC000000)==0x94000000; bm=(w&0xFC000000)==0x14000000
imm=(w&0x03FFFFFF).astype(np.int64); imm=np.where(imm&(1<<25),imm-(1<<26),imm)
bl_t=np.where(blm,pc+imm*4,-1); b_t=np.where(bm,pc+imm*4,-1)
allt=DEC|ENC|ASSIGN
sites=np.nonzero((blm&np.isin(bl_t,list(allt)))|(bm&np.isin(b_t,list(allt))))[0]
KNOWN={0x6c:"spring",0x78:"dampingCompression",0x84:"dampingRebound"}
byoff=collections.defaultdict(list)
for i in sites:
    for k in range(1,10):
        j=i-k
        if j<0: break
        ins=w[j]
        if (ins&0xFFC00000)==0x91000000 and (ins&0x1F)==0:
            off=int((ins>>10)&0xFFF); rn=int((ins>>5)&0x1F)
            if off<=0xCB and off%12==0 and rn!=31:
                byoff[off].append((int(pc[i]), int(bl_t[i] if blm[i] else b_t[i])))
            break
print(f"{'wheel偏移':>10} {'字段#':>5} {'访问点':>6}  已知名        位置样本")
for off in sorted(byoff):
    idx=off//12
    ss=" ".join(f"0x{a:07x}" for a,_ in sorted(byoff[off])[:3])
    print(f"     +0x{off:02x} {idx:5d} {len(byoff[off]):6d}  {KNOWN.get(off,''):<14s}{ss}")
print(f"\n覆盖到的轮子字段: {sorted(o//12 for o in byoff)}")
print(f"未见访问的字段#: {[i for i in range(17) if i*12 not in byoff]}")
