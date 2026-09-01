#!/usr/bin/env python3
"""Find scalar float clamp instructions (FMINNM/FMAXNM/FMIN/FMAX) in a code range."""
import sys, numpy as np
from capstone import *
SO = r"C:\Users\player\Desktop\A9 sifugc\project\work\apk-590301\lib\arm64-v8a\libAsphalt9.so"
TEXT_VA, TEXT_SZ = 0x3456700, 0x319ef3c
lo = int(sys.argv[1],16); hi = int(sys.argv[2],16)
raw=open(SO,"rb").read()
w = np.frombuffer(raw[TEXT_VA:TEXT_VA+TEXT_SZ], dtype=np.uint32)
pc = TEXT_VA + np.arange(len(w), dtype=np.int64)*4
FORMS = {0x1E207800:"fminnm", 0x1E206800:"fmaxnm", 0x1E205800:"fmin", 0x1E204800:"fmax"}
sel = (pc>=lo)&(pc<hi)
md = Cs(CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN)
n=0
for base,nm in FORMS.items():
    m = ((w & 0xFFE0FC00) == base) & sel
    idx=np.nonzero(m)[0]
    for i in idx:
        va=int(pc[i])
        code=raw[va-8:va+12]
        ins=list(md.disasm(code, va-8))
        n+=1
        print(f"0x{va:07x}  {nm}")
        for I in ins:
            mark=" <<<" if I.address==va else ""
            print(f"      0x{I.address:07x}  {I.mnemonic:<8s} {I.op_str}{mark}")
        print()
print(f"total: {n}")
