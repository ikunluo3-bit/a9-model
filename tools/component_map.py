#!/usr/bin/env python3
"""Build the CarPhysicsComponent authenticated-float field map.

Base is component+0x358 (proven: 0x358 + 0x5e8 = 0x940 = tyre input, the offset
the live Frida probe reads).  Only call sites inside the vehicle-physics code
region are attributed to the component.
"""
import json, collections
from pathlib import Path

OUT = Path(r"C:\Users\player\Desktop\a9模型")
sites = json.load(open(OUT/"01-代码层"/"auth-float-sites.json"))

# vehicle physics code region (CarPhysicsComponent ctor 0x3604378 .. tyre/frame fns)
LO, HI = 0x3600000, 0x3625000
BASE = 0x358

sel = [s for s in sites if s["offset"] is not None and LO <= s["site"] < HI]
byoff = collections.defaultdict(list)
for s in sel: byoff[s["offset"]].append(s["site"])

print(f"call sites in vehicle-physics region [0x{LO:x},0x{HI:x}): {len(sel)}")
print(f"distinct offsets: {len(byoff)}\n")
print(f"{'rel':>8} {'/12':>5} {'component abs':>14} {'sites':>5}  call sites")
rows=[]
for off in sorted(byoff):
    q, m = divmod(off, 12)
    absoff = BASE + off
    tag = str(q) if m == 0 else f"{q}+{m}"
    ss = " ".join(f"0x{x:07x}" for x in sorted(byoff[off])[:5])
    mark = "  <== tyre input (frida-verified)" if absoff == 0x940 else ""
    print(f"0x{off:05x} {tag:>5} {'0x%03x'%absoff:>14} {len(byoff[off]):5d}  {ss}{mark}")
    rows.append(dict(rel=off, idx12=(q if m==0 else None), abs=absoff,
                     n_sites=len(byoff[off]), sites=[f"0x{x:07x}" for x in sorted(byoff[off])]))

runs=[]; cur=[]
for off in sorted(byoff):
    if cur and off - cur[-1] == 12: cur.append(off)
    else:
        if len(cur)>1: runs.append(cur)
        cur=[off]
if len(cur)>1: runs.append(cur)
print(f"\ncontiguous 12-byte runs (consecutive fields):")
for r in runs:
    print(f"   0x{r[0]:05x}..0x{r[-1]:05x}  ({len(r)} fields)  abs 0x{BASE+r[0]:03x}..0x{BASE+r[-1]:03x}")
json.dump(rows, open(OUT/"01-代码层"/"component-authfloat-map.json","w"), indent=1)
