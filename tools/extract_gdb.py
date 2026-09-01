#!/usr/bin/env python3
"""从 APK 里解出任意 gdb（Pegasus: 解密 -> inflate）。

用法: python extract_gdb.py CarSounds.gdb CarFilters.gdb ...
      不给参数则解出 manifest 里全部 .gdb
"""
import sys, io, re, zlib, zipfile
from pathlib import Path
sys.path.insert(0, r"C:\Users\player\Desktop\A9 sifugc\project\scratch")
from decrypt_pegasus_manifest import decrypt_manifest
if not isinstance(sys.stdout, io.TextIOWrapper):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

APK = Path(r"C:\Users\player\Desktop\A9 sifugc\output\A9-600300-6.0.0k-base.apk")
OUT = Path(r"C:\Users\player\Desktop\a9模型\gdb-6.0.0k")
LINE = re.compile(r"^(\d+):(\d+):(.*?):(NC:-|C:(\d+)):(NX:-|X:(\d+)):([0-9A-F]{16})$")

z = zipfile.ZipFile(APK)
man = (OUT / "manifest.txt").read_text(encoding="utf-8", errors="replace")
want = set(sys.argv[1:])
n = 0
for ln in man.splitlines():
    m = LINE.fullmatch(ln)
    if not m: continue
    path = m.group(3)
    if not path.endswith(".gdb"): continue
    name = path.split("/|/")[-1]
    if want and name not in want: continue
    raw = z.read("assets/main/" + m.group(8))
    data = raw
    if m.group(7):
        data, _ = decrypt_manifest(raw, m.group(7))
    if m.group(5):
        data = zlib.decompress(data, wbits=-15)
    (OUT / name).write_bytes(data)
    print(f"  {name:<28} {len(data):>10,}B")
    n += 1
print(f"共解出 {n} 个")
