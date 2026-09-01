#!/usr/bin/env python3
"""M2a: 从 base APK 提取 AMG One 车模 + 最小对照样本（NC/NX 直读）。"""
import zipfile, re, io, sys, os
sys.path.insert(0, r"C:\Users\player\Desktop\A9 sifugc\project\scratch")
from decrypt_pegasus_manifest import decrypt_manifest
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

OUT = r"C:\Users\player\Desktop\a9模型\build\jmox_work"
os.makedirs(OUT, exist_ok=True)
apk = zipfile.ZipFile(r"C:\Users\player\Desktop\A9 sifugc\output\A9-600300-6.0.0k-base.apk")
plain, _ = decrypt_manifest(apk.read("assets/main/397F9F0653ADA306"), "Error 3452: file not found")
LINE = re.compile(r"^(\d+):(\d+):(.*?):(?:C:(\d+)|NC:-):(?:X:(\d+)|NX:-):([0-9A-F]{16})$")
rows = []
for ln in plain.decode("utf-8").splitlines():
    m = LINE.fullmatch(ln)
    if not m:
        continue
    path = m.group(3)
    if "/gfx3D/cars/models/" in path and path.endswith("_car.json.jmodel"):
        rows.append((path.split("|")[0], int(m.group(4)) if m.group(4) else 0, m.group(6)))
print("车模条目", len(rows))
for p, s, a in rows:
    if "AMG" in p:
        print("AMG:", p, s, a)
szs = sorted((s, p, a) for p, s, a in rows)
print("最小 5:")
for s, p, a in szs[:5]:
    print(" ", s, p.split("/")[-1], a)

want = [x for x in szs if "Mercedes_AMG_One" in x[1]][:1] + szs[:2]
for s, p, a in want:
    nm = p.split("/")[-1].replace(":", "_")
    data = apk.read("assets/main/" + a)
    open(os.path.join(OUT, nm), "wb").write(data)
    print("抽出", nm, len(data), "B -> build/jmox_work/")
