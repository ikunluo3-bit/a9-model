#!/usr/bin/env python3
"""Recover every authenticated-float access: find BL/B to the decoder and
back-trace how x0 was formed (add x0, xBase, #imm)."""
import numpy as np, json, collections
from capstone import *
from pathlib import Path

SO = r"C:\Users\player\Desktop\A9 sifugc\project\work\apk-590301\lib\arm64-v8a\libAsphalt9.so"
TEXT_VA, TEXT_SZ = 0x3456700, 0x319ef3c
OUT = Path(r"C:\Users\player\Desktop\a9模型")
DECODERS = {0x3535498, 0x3535510}

raw = open(SO,"rb").read()
w  = np.frombuffer(raw[TEXT_VA:TEXT_VA+TEXT_SZ], dtype=np.uint32)
pc = TEXT_VA + np.arange(len(w), dtype=np.int64)*4

def branch_targets(mask_op):
    m = (w & 0xFC000000) == mask_op
    imm = (w & 0x03FFFFFF).astype(np.int64)
    imm = np.where(imm & (1<<25), imm-(1<<26), imm)
    return m, np.where(m, pc + imm*4, -1)

blm, bltgt = branch_targets(0x94000000)
bm,  btgt  = branch_targets(0x14000000)
sites = sorted(set(np.nonzero(blm & np.isin(bltgt, list(DECODERS)))[0]) |
               set(np.nonzero(bm  & np.isin(btgt,  list(DECODERS)))[0]))
print(f"decoder call sites: {len(sites)}")

md = Cs(CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN)
recs = []
for i in sites:
    # walk back up to 12 insns looking for the last write to x0
    off = base = None
    for k in range(1, 13):
        j = i - k
        if j < 0: break
        ins = w[j]
        if (ins & 0xFFC00000) == 0x91000000 and (ins & 0x1F) == 0:      # add x0, xN, #imm
            off  = int((ins >> 10) & 0xFFF)
            base = int((ins >> 5) & 0x1F)
            break
        if (ins & 0xFFE0FFE0) == 0xAA0003E0:                             # mov x0, xN
            base = int((ins >> 16) & 0x1F); off = 0
            break
    recs.append(dict(site=int(pc[i]), offset=off, base_reg=base))

known = [r for r in recs if r["offset"] is not None]
print(f"  resolved to an explicit offset: {len(known)}")
offs = sorted({r["offset"] for r in known})
print(f"  distinct offsets: {len(offs)}")
mult12 = [o for o in offs if o % 12 == 0]
print(f"  offsets divisible by 12 (auth-float stride): {len(mult12)}")
print(f"\n{'offset':>8} {'hex':>7} {'idx=/12':>8}  sites")
byoff = collections.defaultdict(list)
for r in known: byoff[r["offset"]].append(r["site"])
for o in offs:
    q, m = divmod(o, 12)
    tag = f"{q}" if m == 0 else f"{q}+{m}"
    ss = " ".join(f"0x{s:07x}" for s in sorted(byoff[o])[:4])
    print(f"{o:8d} 0x{o:05x} {tag:>8}  {ss}")
json.dump(known, open(OUT/"01-代码层"/"auth-float-sites.json","w"), indent=1)
