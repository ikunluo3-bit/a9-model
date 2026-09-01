#!/usr/bin/env python3
"""Find code loading a float constant: ADRP xN,<page> + LDR s?,[xN,#off]."""
import sys, numpy as np
from capstone import *
SO = r"C:\Users\player\Desktop\A9 sifugc\project\work\apk-590301\lib\arm64-v8a\libAsphalt9.so"
TEXT_VA, TEXT_SZ = 0x3456700, 0x319ef3c
target=int(sys.argv[1],16)
raw=open(SO,"rb").read()
w=np.frombuffer(raw[TEXT_VA:TEXT_VA+TEXT_SZ],dtype=np.uint32)
pc=TEXT_VA+np.arange(len(w),dtype=np.int64)*4
page, off = target & ~0xFFF, target & 0xFFF
adrp=(w & 0x9F000000)==0x90000000
immhi=((w>>5)&0x7FFFF).astype(np.int64); immlo=((w>>29)&0x3).astype(np.int64)
imm=(immhi<<2)|immlo; imm=np.where(imm&(1<<20),imm-(1<<21),imm)
tgt=(pc & ~0xFFF)+imm*4096
cand=np.nonzero(adrp & (tgt==page))[0]
md=Cs(CS_ARCH_ARM64,CS_MODE_LITTLE_ENDIAN)
hits=[]
for i in cand:
    rd=int(w[i] & 0x1F)
    for k in range(1,12):
        j=i+k
        if j>=len(w): break
        ins=w[j]
        # LDR s,[Xn,#imm]  0xBD400000 scale4 ; LDR d 0xFD400000 scale8
        for base,scale in ((0xBD400000,4),(0xFD400000,8)):
            if (ins & 0xFFC00000)==base and ((ins>>5)&0x1F)==rd and ((ins>>10)&0xFFF)*scale==off:
                hits.append((int(pc[i]),int(pc[j]))); break
        else:
            continue
        break
print(f"ADRP+LDR loading 0x{target:07x}: {len(hits)} site(s)")
for a,l in hits:
    print(f"\n--- ldr at 0x{l:07x} (adrp 0x{a:07x}) ---")
    for I in md.disasm(raw[l-0x18:l+0x28], l-0x18):
        mark=" <<<" if I.address==l else ""
        print(f"    0x{I.address:07x}  {I.mnemonic:<8s} {I.op_str}{mark}")
