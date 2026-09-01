#!/usr/bin/env python3
"""Find LDP s-pair loads at a given struct offset (adjacent float pairs)."""
import sys, numpy as np
from capstone import *
SO = r"C:\Users\player\Desktop\A9 sifugc\project\work\apk-590301\lib\arm64-v8a\libAsphalt9.so"
TEXT_VA, TEXT_SZ = 0x3456700, 0x319ef3c
raw=open(SO,"rb").read()
w = np.frombuffer(raw[TEXT_VA:TEXT_VA+TEXT_SZ], dtype=np.uint32)
pc = TEXT_VA + np.arange(len(w), dtype=np.int64)*4
md = Cs(CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN)

offs = [int(a,16) for a in sys.argv[1:]] or [0x58]
# LDP St,St2,[Xn,#imm]  : 0x2D400000 | imm7<<15 | Rt2<<10 | Rn<<5 | Rt
m = (w & 0xFFC00000) == 0x2D400000
imm7 = ((w >> 15) & 0x7F).astype(np.int64)
imm7 = np.where(imm7 & 0x40, imm7 - 0x80, imm7)
byteoff = imm7 * 4
for off in offs:
    hit = np.nonzero(m & (byteoff == off))[0]
    hit = [i for i in hit if ((w[i]>>5)&0x1F) != 31]     # drop SP-relative
    print(f"LDP s,s,[Xn,#0x{off:x}] : {len(hit)} non-stack sites")
    for i in hit[:24]:
        va=int(pc[i]); rn=int((w[i]>>5)&0x1F)
        ctx=list(md.disasm(raw[va-4:va+12], va-4))
        print(f"   0x{va:07x}  (base x{rn})")
        for I in ctx:
            mark=" <<<" if I.address==va else ""
            print(f"        0x{I.address:07x}  {I.mnemonic:<8s} {I.op_str}{mark}")
    print()
