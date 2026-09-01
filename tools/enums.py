#!/usr/bin/env python3
"""Find comma-separated enum name tables in .rodata."""
import re, sys
SO = r"C:\Users\player\Desktop\A9 sifugc\project\work\apk-590301\lib\arm64-v8a\libAsphalt9.so"
LO, HI = 0x65f5640, 0x65f5640+0x28caa5
blob = open(SO,"rb").read()[LO:HI]
pat = re.compile(rb"[A-Za-z][A-Za-z0-9_]{2,40}(?:, ?[A-Za-z][A-Za-z0-9_]{2,40}){3,}")
va = LO
found=[]
for part in blob.split(b"\x00"):
    if part:
        s = part.decode("utf-8","ignore")
        if pat.fullmatch(part):
            found.append((va, s, s.count(",")+1))
    va += len(part)+1
found.sort(key=lambda t:-t[2])
kw = sys.argv[1].lower() if len(sys.argv)>1 else None
print(f"enum-like tables: {len(found)}\n")
for va,s,n in found:
    if kw and kw not in s.lower(): continue
    print(f"0x{va:07x}  [{n:3d}]  {s[:400]}")
    print()
