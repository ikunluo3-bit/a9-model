#!/usr/bin/env python3
"""Back-trace every auth-float ENCODER call site to the component offset written."""
import numpy as np, json, collections
from pathlib import Path
SO = r"C:\Users\player\Desktop\A9 sifugc\project\work\apk-590301\lib\arm64-v8a\libAsphalt9.so"
TEXT_VA, TEXT_SZ = 0x3456700, 0x319ef3c
OUT = Path(r"C:\Users\player\Desktop\a9模型")
ENC = {0x3535860, 0x3535ef0}

raw = open(SO,"rb").read()
w  = np.frombuffer(raw[TEXT_VA:TEXT_VA+TEXT_SZ], dtype=np.uint32)
pc = TEXT_VA + np.arange(len(w), dtype=np.int64)*4
blm = (w & 0xFC000000) == 0x94000000
imm = (w & 0x03FFFFFF).astype(np.int64)
imm = np.where(imm & (1<<25), imm-(1<<26), imm)
tgt = np.where(blm, pc + imm*4, -1)
sites = np.nonzero(blm & np.isin(tgt, list(ENC)))[0]
print(f"encoder call sites: {len(sites)}")

# also resolve  mov wN,#imm ; add x0, xB, xN   (large offsets)
movz = (w & 0xFFE00000) == 0x52800000
rows=[]
for i in sites:
    off=basereg=None; how=""
    for k in range(1,14):
        j=i-k
        if j<0: break
        ins=w[j]
        if (ins & 0xFFC00000)==0x91000000 and (ins & 0x1F)==0:       # add x0,xB,#imm
            off=int((ins>>10)&0xFFF); basereg=int((ins>>5)&0x1F); how="imm"; break
        if (ins & 0xFFE0FC00)==0x8B000000 and (ins & 0x1F)==0:       # add x0,xB,xN
            rn=int((ins>>5)&0x1F); rm=int((ins>>16)&0x1F)
            for k2 in range(1,10):                                    # find mov wRM,#imm
                j2=j-k2
                if j2<0: break
                i2=w[j2]
                if movz[j2] and (i2 & 0x1F)==rm:
                    off=int((i2>>5)&0xFFFF); basereg=rn; how="reg"; break
            break
    rows.append(dict(site=int(pc[i]), offset=off, base=basereg, how=how))
ok=[r for r in rows if r["offset"] is not None]
print(f"  resolved: {len(ok)}   distinct offsets: {len({r['offset'] for r in ok})}")
byoff=collections.defaultdict(list)
for r in ok: byoff[r["offset"]].append(r["site"])
print(f"\n{'component off':>14} {'sites':>5}  first call sites")
for o in sorted(byoff):
    ss=" ".join(f"0x{x:07x}" for x in sorted(byoff[o])[:4])
    mark="   <== tyre input" if o==0x940 else ""
    print(f"{'0x%04x'%o:>14} {len(byoff[o]):5d}  {ss}{mark}")
json.dump(ok, open(OUT/"01-代码层"/"auth-float-writes.json","w"), indent=1)
