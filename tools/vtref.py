#!/usr/bin/env python3
"""Find RELA relocations whose addend points at a given function (i.e. vtable slots)."""
import sys, numpy as np
SO = r"C:\Users\player\Desktop\A9 sifugc\project\work\apk-590301\lib\arm64-v8a\libAsphalt9.so"
RELA_OFF, RELA_SZ = 0x7eec8, 0x33c5028
targets=[int(a,16) for a in sys.argv[1:]]
f=open(SO,"rb"); f.seek(RELA_OFF); buf=f.read(RELA_SZ)
a=np.frombuffer(buf,dtype=np.uint64).reshape(RELA_SZ//24,3)
for t in targets:
    m=np.nonzero(a[:,2]==t)[0]
    print(f"addend == 0x{t:07x} : {len(m)} relocation(s)")
    for i in m[:20]:
        off=int(a[i,0])
        print(f"    slot at 0x{off:08x}")
        # show neighbouring slots to reveal the vtable
        lo=max(0,i-4); hi=min(len(a),i+5)
        for j in range(lo,hi):
            if abs(int(a[j,0])-off) <= 0x40:
                mark=" <<<" if j==i else ""
                print(f"        0x{int(a[j,0]):08x} -> 0x{int(a[j,2]):07x}{mark}")
