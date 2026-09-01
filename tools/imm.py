#!/usr/bin/env python3
"""Find MOV/MOVZ/CMP with a given immediate, optionally limited to a code range."""
import sys, numpy as np
from capstone import *
SO = r"C:\Users\player\Desktop\A9 sifugc\project\work\apk-590301\lib\arm64-v8a\libAsphalt9.so"
TEXT_VA, TEXT_SZ = 0x3456700, 0x319ef3c
val=int(sys.argv[1],16)
lo=int(sys.argv[2],16) if len(sys.argv)>2 else TEXT_VA
hi=int(sys.argv[3],16) if len(sys.argv)>3 else TEXT_VA+TEXT_SZ
raw=open(SO,"rb").read()
w=np.frombuffer(raw[TEXT_VA:TEXT_VA+TEXT_SZ],dtype=np.uint32)
pc=TEXT_VA+np.arange(len(w),dtype=np.int64)*4
sel=(pc>=lo)&(pc<hi)
movz=((w & 0xFFE00000)==0x52800000)&(((w>>5)&0xFFFF)==val)&sel        # movz w,#imm
cmpi=((w & 0xFFC00000)==0xF1000000)&(((w>>10)&0xFFF)==val)&sel        # cmp x,#imm
addi=((w & 0xFFC00000)==0x91000000)&(((w>>10)&0xFFF)==val)&sel        # add x,x,#imm
md=Cs(CS_ARCH_ARM64,CS_MODE_LITTLE_ENDIAN)
for nm,m in (("MOVZ",movz),("CMP",cmpi),("ADD",addi)):
    idx=np.nonzero(m)[0]
    print(f"{nm} #0x{val:x} : {len(idx)} sites")
    for i in idx[:25]:
        va=int(pc[i])
        ins=next(md.disasm(raw[va:va+4],va))
        print(f"   0x{va:07x}  {ins.mnemonic:<7s} {ins.op_str}")
