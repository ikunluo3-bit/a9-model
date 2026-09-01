#!/usr/bin/env python3
"""把改好的 gdb 回封进 APK（只替换点名的 asset，其余字节不动）。

流程:  改好的 .gdb  ->  deflate  ->  Pegasus 加密  ->  替换 APK 内该条目  ->  zipalign -> 签名

安全策略:
  * 只替换 manifest 里点名的那几个 asset，其它 32000+ 条目原样复制
  * 加密后立即解密回读比对，round-trip 不一致就中止
  * 替换前后逐条目核对 CRC，未点名条目的 CRC 必须完全相同
  * 原 APK 不被修改，输出到新文件

用法:
  python repack.py --apk <原始APK> --tuned <tuner 输出目录> --out <新APK>
"""
from __future__ import annotations
import argparse, hashlib, json, shutil, struct, subprocess, sys, io, zipfile, zlib
from pathlib import Path

sys.path.insert(0, str(Path(r"C:\Users\player\Desktop\A9 sifugc\project\scratch")))
from decrypt_pegasus_manifest import decrypt_manifest              # noqa: E402
from patch_senna_revival_asset import encrypt_pegasus_stage        # noqa: E402

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

MANIFEST_ASSET = "assets/main/397F9F0653ADA306"
MANIFEST_KEY = "Error 3452: file not found"
LINE = __import__("re").compile(
    r"^(\d+):(\d+):(.*?):(?:C:(\d+)|NC:-):(?:X:(\d+)|NX:-):([0-9A-F]{16})$")


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest().upper()


def manifest_entries(apk: zipfile.ZipFile):
    plain, _ = decrypt_manifest(apk.read(MANIFEST_ASSET), MANIFEST_KEY)
    out = {}
    for ln in plain.decode("utf-8").splitlines():
        m = LINE.fullmatch(ln)
        if not m:
            continue
        out[m.group(3)] = dict(plain_size=int(m.group(4)) if m.group(4) else None,
                               x_key=m.group(5), asset=m.group(6))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apk", required=True, type=Path)
    ap.add_argument("--tuned", required=True, type=Path, help="tuner.py 的输出目录")
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--files", nargs="*", default=["CarPhysics.gdb", "CarChassis.gdb"])
    ap.add_argument("--manifest", type=Path,
                    help="改好的 manifest 明文（外观移植用）；长度必须与原 manifest 一致")
    ap.add_argument("--asset-swap", type=Path,
                    help="JSON {受体asset_id: 供体asset_id}：把供体资源的字节直接写进受体条目。"
                         "两边都必须是 NC/NX（未压缩未加密），manifest 完全不动")
    ap.add_argument("--skip-sign", action="store_true")
    args = ap.parse_args()

    src = zipfile.ZipFile(args.apk)
    ent = manifest_entries(src)

    # 1. 为每个改动文件重新加密
    replace = {}
    size_fix: dict[str, tuple[int, int]] = {}
    report = {"apk_in": str(args.apk), "files": []}
    for name in args.files:
        newp = args.tuned / name
        if not newp.exists():
            print(f"  跳过 {name}（tuned 目录中不存在）")
            continue
        oldp = args.tuned / (name + ".orig")
        data = newp.read_bytes()
        if oldp.exists() and oldp.read_bytes() == data:
            print(f"  跳过 {name}（与原始一致，无改动）")
            continue
        meta = next((v for k, v in ent.items() if k.endswith("|/" + name)), None)
        if meta is None:
            sys.exit(f"manifest 里找不到 {name}")
        if meta["plain_size"] is not None and len(data) != meta["plain_size"]:
            # 明文大小变了 -> manifest 里记的 C:<size> 必须同步改。
            # 位数相同才行，否则 manifest 行长变化（要另想办法）。
            if len(str(len(data))) != len(str(meta["plain_size"])):
                sys.exit(f"{name}: 明文 {meta['plain_size']} -> {len(data)} 位数不同，"
                         f"manifest 行长会变，暂不支持")
            size_fix[name] = (meta["plain_size"], len(data))
            print(f"  {name} 明文 {meta['plain_size']:,} -> {len(data):,}，同步改 manifest")
        stage = data
        if meta["plain_size"] is not None:
            co = zlib.compressobj(level=9, wbits=-15)
            stage = co.compress(data) + co.flush()
        member = "assets/main/" + meta["asset"]
        original_raw = src.read(member)
        if meta["x_key"]:
            counter = struct.unpack_from("<I", original_raw)[0]
            enc = encrypt_pegasus_stage(stage, meta["x_key"], counter)
            # round-trip 校验
            back, _ = decrypt_manifest(enc, meta["x_key"])
            if back != stage:
                sys.exit(f"{name}: Pegasus 加解密 round-trip 失败")
            if meta["plain_size"] is not None and zlib.decompress(back, wbits=-15) != data:
                sys.exit(f"{name}: inflate round-trip 失败")
        else:
            enc = stage
        replace[member] = enc
        report["files"].append(dict(name=name, member=member,
                                    plain_size=len(data), raw_size=len(enc),
                                    sha256_plain=sha256(data), sha256_raw=sha256(enc)))
        print(f"  重封 {name}: 明文 {len(data):,} -> 密文 {len(enc):,}  ({member})")

    # 1b-0. gdb 明文大小变了就就地改 manifest 里对应的 C:<size>
    if size_fix and not args.manifest:
        raw_m = src.read(MANIFEST_ASSET)
        plain_m, _ = decrypt_manifest(raw_m, MANIFEST_KEY)
        txt = plain_m
        for name, (old, new) in size_fix.items():
            member = next(k for k, v in ent.items() if k.endswith("|/" + name))
            pat = (":" + member + ":C:" + str(old) + ":").encode()
            rep = (":" + member + ":C:" + str(new) + ":").encode()
            if txt.count(pat) != 1:
                sys.exit(f"manifest 里 {name} 的 C:{old} 不唯一（{txt.count(pat)} 个）")
            txt = txt.replace(pat, rep)
        assert len(txt) == len(plain_m), "manifest 长度变了"
        counter = struct.unpack_from("<I", raw_m)[0]
        enc_m = encrypt_pegasus_stage(txt, MANIFEST_KEY, counter)
        back_m, _ = decrypt_manifest(enc_m, MANIFEST_KEY)
        if back_m != txt: sys.exit("manifest round-trip 失败")
        replace[MANIFEST_ASSET] = enc_m
        print(f"  manifest 已同步 {len(size_fix)} 处大小")

    # 1b. 可选：替换 manifest 自身（外观移植改的是它里面的 asset_id）
    if args.manifest:
        raw = src.read(MANIFEST_ASSET)
        old_plain, _ = decrypt_manifest(raw, MANIFEST_KEY)
        new_plain = args.manifest.read_bytes()
        if len(new_plain) != len(old_plain):
            sys.exit(f"manifest 长度变了 {len(old_plain)} -> {len(new_plain)}——"
                     f"asset_id 是定长 16 位，长度不该变")
        counter = struct.unpack_from("<I", raw)[0]
        enc = encrypt_pegasus_stage(new_plain, MANIFEST_KEY, counter)
        back, _ = decrypt_manifest(enc, MANIFEST_KEY)
        if back != new_plain:
            sys.exit("manifest: Pegasus 加解密 round-trip 失败")
        nlines = sum(1 for a, b in zip(old_plain.splitlines(), new_plain.splitlines())
                     if a != b)
        replace[MANIFEST_ASSET] = enc
        report["files"].append(dict(name="manifest", member=MANIFEST_ASSET,
                                    plain_size=len(new_plain), raw_size=len(enc),
                                    changed_lines=nlines,
                                    sha256_plain=sha256(new_plain), sha256_raw=sha256(enc)))
        print(f"  重封 manifest: {nlines} 行改动，明文 {len(new_plain):,} -> 密文 {len(enc):,}")

    # 1c. 可选：直接换资源内容（外观移植的正确做法——不产生重复 asset_id）
    if args.asset_swap:
        by_asset = {v["asset"]: (k, v) for k, v in ent.items()}
        for dst_id, src_id in json.loads(args.asset_swap.read_text(encoding="utf-8")).items():
            for aid in (dst_id, src_id):
                if aid not in by_asset:
                    sys.exit(f"manifest 里没有 asset {aid}")
                _, meta = by_asset[aid]
                if meta["plain_size"] is not None or meta["x_key"]:
                    sys.exit(f"{aid} 不是 NC/NX，暂不支持直接换内容")
            data = src.read("assets/main/" + src_id)
            replace["assets/main/" + dst_id] = data
            report["files"].append(dict(name=by_asset[dst_id][0], member="assets/main/" + dst_id,
                                        donor=by_asset[src_id][0], donor_asset=src_id,
                                        raw_size=len(data), sha256_raw=sha256(data)))
        print(f"  换资源内容 {len(json.loads(args.asset_swap.read_text(encoding='utf-8')))} 个"
              f"（manifest 未改动）")

    if not replace:
        sys.exit("没有任何改动需要回封")

    # 2. 逐条目复制，替换点名的
    args.out.parent.mkdir(parents=True, exist_ok=True)
    tmp = args.out.with_suffix(".tmp")
    n_same = 0
    with zipfile.ZipFile(tmp, "w", allowZip64=True) as dst:
        for info in src.infolist():
            if info.filename in replace:
                zi = zipfile.ZipInfo(info.filename, date_time=info.date_time)
                zi.compress_type = info.compress_type
                zi.external_attr = info.external_attr
                dst.writestr(zi, replace[info.filename])
            else:
                zi = zipfile.ZipInfo(info.filename, date_time=info.date_time)
                zi.compress_type = info.compress_type
                zi.external_attr = info.external_attr
                dst.writestr(zi, src.read(info.filename))
                n_same += 1
    print(f"  原样复制条目 {n_same}，替换 {len(replace)}")

    # 3. 核对未改条目的 CRC
    with zipfile.ZipFile(tmp) as chk:
        a = {i.filename: i.CRC for i in src.infolist()}
        b = {i.filename: i.CRC for i in chk.infolist()}
        if set(a) != set(b):
            sys.exit("条目集合发生变化")
        bad = [k for k in a if k not in replace and a[k] != b[k]]
        if bad:
            sys.exit(f"未点名条目 CRC 变化: {bad[:5]}")
    print(f"  CRC 核对通过：{len(a)-len(replace)} 个未改条目全部一致")

    shutil.move(tmp, args.out)
    report["apk_out"] = str(args.out)
    (args.out.parent / (args.out.stem + "-repack-report.json")).write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  产物: {args.out}")
    print(f"  报告: {args.out.parent / (args.out.stem + '-repack-report.json')}")
    if not args.skip_sign:
        print("\n  ⚠ 尚未签名。APK 改动后必须重新签名才能安装：")
        print(f"     zipalign -p -f 4 \"{args.out}\" \"{args.out.with_suffix('.aligned.apk')}\"")
        print(f"     apksigner sign --ks <你的keystore> \"{args.out.with_suffix('.aligned.apk')}\"")


if __name__ == "__main__":
    main()
