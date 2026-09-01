#!/usr/bin/env python3
"""iOS 回封：tuned-ios 三库 -> Pegasus 加密 -> 重建 main.pack -> 重封 IPA。

产物: Downloads/狂野飙车9-6.0.0-21车mod-未签名.ipa （Apple ID 工具自签安装）
"""
import io, sys, struct, zlib, zipfile, shutil, time
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "tools"))
from repack import manifest_entries
from decrypt_pegasus_manifest import decrypt_manifest
from patch_senna_revival_asset import encrypt_pegasus_stage

IPA = Path(r"C:\Users\player\Downloads\狂野飙车9-6.0.0_.ipa")
OUT = Path(r"C:\Users\player\Downloads\狂野飙车9-6.0.0-21车mod-未签名.ipa")
MEMBER = "Payload/Asphalt9.app/main.pack"

AIDS = {"CarPhysics.gdb": "397F9F67A1876D4E",
        "CarChassis.gdb": "397F9F67F1D6C9A1",
        "CarDef.gdb": "397F9F6813099F74"}

za = zipfile.ZipFile(r"C:\Users\player\Desktop\A9 sifugc\output\A9-600300-6.0.0k-base.apk")
ent = manifest_entries(za)
keys = {n: next(v for k, v in ent.items() if k.endswith("|/" + n))["x_key"] for n in AIDS}

zi = zipfile.ZipFile(str(IPA))
pack_bytes = zi.read(MEMBER)
prefix, mi = pack_bytes[:2], zipfile.ZipFile(io.BytesIO(pack_bytes))

# 1) 加密三库（counter 沿用 iOS 原 blob 的头 4 字节）
new_blobs = {}
for name, aid in AIDS.items():
    tuned = (BASE / "tuned-ios" / name).read_bytes()
    orig = mi.read(aid)
    counter = struct.unpack_from("<I", orig)[0]
    co = zlib.compressobj(level=9, wbits=-15)
    stage = co.compress(tuned) + co.flush()
    enc = encrypt_pegasus_stage(stage, keys[name], counter)
    back, _ = decrypt_manifest(enc, keys[name])
    assert back == stage, f"{name}: Pegasus round-trip 失败"
    assert zlib.decompress(back, wbits=-15) == tuned, f"{name}: inflate round-trip 失败"
    new_blobs[aid] = enc
    print(f"{name}: 明文 {len(tuned):,} -> 密文 {len(enc):,}  round-trip OK")

# 2) 重建 main.pack（保持条目顺序，STORED，前缀保留）
buf = io.BytesIO()
with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as zout:
    for info in mi.infolist():
        payload = new_blobs.get(info.filename)
        if payload is None:
            payload = mi.read(info.filename)
        di = zipfile.ZipInfo(info.filename, date_time=info.date_time)
        di.compress_type = zipfile.ZIP_STORED
        di.external_attr = info.external_attr
        zout.writestr(di, payload)
new_pack = prefix + buf.getvalue()
print(f"main.pack 重建: {len(pack_bytes):,} -> {len(new_pack):,} B")

# 3) 自检：新 main.pack 可开、三库解密回原 tuned
chk = zipfile.ZipFile(io.BytesIO(new_pack))
for name, aid in AIDS.items():
    blob = chk.read(aid)
    back, _ = decrypt_manifest(blob, keys[name])
    tuned = (BASE / "tuned-ios" / name).read_bytes()
    assert zlib.decompress(back, wbits=-15) == tuned, f"{name}: 新包自检失败"
print("新 main.pack 自检: 三库解密==tuned  OK")

# 4) 重封 IPA（流式拷贝，main.pack 用新内容）
t0 = time.time()
with zipfile.ZipFile(str(OUT), "w", allowZip64=True) as zout:
    for info in zi.infolist():
        if info.filename == MEMBER:
            di = zipfile.ZipInfo(info.filename, date_time=info.date_time)
            di.compress_type = zipfile.ZIP_DEFLATED
            zout.writestr(di, new_pack)
            print("  main.pack 已替换")
            continue
        di = zipfile.ZipInfo(info.filename, date_time=info.date_time)
        di.compress_type = info.compress_type
        di.external_attr = info.external_attr
        with zi.open(info.filename) as src, zout.open(di, "w") as dst:
            shutil.copyfileobj(src, dst, 1 << 20)
print(f"IPA 重封完成: {OUT}  ({time.time()-t0:.0f}s, {OUT.stat().st_size:,} B)")
