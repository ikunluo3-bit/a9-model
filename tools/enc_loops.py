#!/usr/bin/env python3
"""Find loops that encode auth floats with a 12-byte stride (bulk field fill)."""
import numpy as np
from capstone import *
SO = r"C:\Users\player\Desktop\A9 sifugc\project\work\apk-590301\lib\arm64-v8a\libAsphalt9.so"
TEXT_VA, TEXT_SZ = 0x3456700, 0x319ef3c
ENC={0x3535860,0x3535ef0}; ASSIGN={0x35854f4}
raw=open(SO,"rb").read()
w=np.frombuffer(raw[TEXT_VA:TEXT_VA+TEXT_SZ],dtype=np.uint32)
pc=TEXT_VA+np.arange(len(w),dtype=np.int64)*4
blm=(w & 0xFC000000)==0x94000000
imm=(w & 0x03FFFFFF).astype(np.int64); imm=np.where(imm&(1<<25),imm-(1<<26),imm)
tgt=np.where(blm, pc+imm*4, -1)
# add xN, xN, #0xc   (stride of an auth float)
stride=((w & 0xFFC00000)==0x91000000)&(((w>>10)&0xFFF)==0xc)
md=Cs(CS_ARCH_ARM64,CS_MODE_LITTLE_ENDIAN)
targets=list(ENC|ASSIGN)
sites=np.nonzero(blm & np.isin(tgt,targets))[0]
print(f"encode/assign 调用点: {len(sites)}")
hits=[]
for i in sites:
    for k in range(1,8):
        if i+k<len(w) and stride[i+k]:
            hits.append((int(pc[i]), int(pc[i+k]), int(tgt[i]))); break
print(f"  其后 8 条内带 'add x,x,#0xc' 的（循环填充）: {len(hits)}\n")
seen=set()
for va,sva,t in hits:
    fn=va & ~0xFFF
    print(f"--- bl 0x{t:07x} @ 0x{va:07x} ---")
    for I in md.disasm(raw[va-0x28:va+0x24], va-0x28):
        mark=" <<<" if I.address==va else ""
        print(f"    0x{I.address:07x}  {I.mnemonic:<8s} {I.op_str}{mark}")
    print()
