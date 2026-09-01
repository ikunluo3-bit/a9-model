#!/usr/bin/env python3
"""Dump encoder call sites whose target offset could not be resolved automatically."""
import numpy as np
from capstone import *
SO = r"C:\Users\player\Desktop\A9 sifugc\project\work\apk-590301\lib\arm64-v8a\libAsphalt9.so"
TEXT_VA, TEXT_SZ = 0x3456700, 0x319ef3c
ENC={0x3535860,0x3535ef0}
raw=open(SO,"rb").read()
w  = np.frombuffer(raw[TEXT_VA:TEXT_VA+TEXT_SZ], dtype=np.uint32)
pc = TEXT_VA + np.arange(len(w), dtype=np.int64)*4
blm=(w & 0xFC000000)==0x94000000
imm=(w & 0x03FFFFFF).astype(np.int64); imm=np.where(imm&(1<<25),imm-(1<<26),imm)
tgt=np.where(blm, pc+imm*4, -1)
sites=np.nonzero(blm & np.isin(tgt,list(ENC)))[0]
md=Cs(CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN)
un=[]
for i in sites:
    ok=False
    for k in range(1,14):
        j=i-k
        if j<0: break
        ins=w[j]
        if (ins & 0xFFC00000)==0x91000000 and (ins & 0x1F)==0: ok=True; break
        if (ins & 0xFFE0FC00)==0x8B000000 and (ins & 0x1F)==0: ok=True; break
    if not ok: un.append(i)
print(f"未解析的 encoder 调用点: {len(un)}\n")
for i in un:
    va=int(pc[i])
    print(f"--- bl encoder @ 0x{va:07x} ---")
    for I in md.disasm(raw[va-0x28:va+8], va-0x28):
        mark=" <<<" if I.address==va else ""
        print(f"    0x{I.address:07x}  {I.mnemonic:<8s} {I.op_str}{mark}")
    print()
