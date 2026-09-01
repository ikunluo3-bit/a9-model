#!/usr/bin/env python3
"""Expand a .data object via RELA: show what each 8-byte slot points to."""
import sys, numpy as np
SO = r"C:\Users\player\Desktop\A9 sifugc\project\work\apk-590301\lib\arm64-v8a\libAsphalt9.so"
RELA_OFF, RELA_SZ = 0x7eec8, 0x33c5028
base=int(sys.argv[1],16); n=int(sys.argv[2]) if len(sys.argv)>2 else 24
f=open(SO,"rb"); f.seek(RELA_OFF); buf=f.read(RELA_SZ)
a=np.frombuffer(buf,dtype=np.uint64).reshape(RELA_SZ//24,3)
lo,hi=base, base+n*8
m=(a[:,0]>=lo)&(a[:,0]<hi)
sel=a[m]
sel=sel[np.argsort(sel[:,0])]
print(f"object 0x{base:08x}, {len(sel)} relocated slots in [0x{lo:x},0x{hi:x})")
for off,info,add in sel:
    print(f"  +0x{int(off)-base:04x}  (0x{int(off):08x})  ->  0x{int(add):07x}")
