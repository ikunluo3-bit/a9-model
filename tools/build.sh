#!/bin/bash
# 一条龙：回封 -> 签名 -> 删中间包 -> 安装 -> 崩溃复现测试
KS_PASS_FILE="$(dirname "$0")/keystore.local"
[ -f "$KS_PASS_FILE" ] && KS_PASS="$(cat "$KS_PASS_FILE")" || { echo "缺 $KS_PASS_FILE（放一行签名口令，不入库）"; exit 1; }
set -o pipefail
# 用法: ./build.sh <标签> <repack 额外参数...>
set -e
O="/c/Users/player/Desktop/A9 sifugc/output"
OW="C:\Users\player\Desktop\A9 sifugc\output"
SDKW="C:\Users\player\AppData\Local\Android\Sdk"
O_SDK="/c/Users/player/AppData/Local/Android/Sdk"
ADB="/c/Users/player/AppData/Local/Android/Sdk/platform-tools/adb.exe"
KS="C:\Users\player\Desktop\A9 sifugc\project\tools\a9-repack.keystore"
TAG="$1"; shift
if [ ! -f "$O/A9-$TAG.apk" ]; then
  python repack.py --apk "$O/A9-600300-6.0.0k-base.apk" --out "$O/A9-$TAG.apk" --skip-sign "$@" | tail -4
fi
# 自动探测最高 build-tools（37.0.0 已被卸载；35.0.0 签 3.5GB 会 32 位溢出）
BT=$(ls "$O_SDK/build-tools" 2>/dev/null | sort -V | tail -1)
if [ -z "$BT" ]; then echo "找不到 build-tools"; exit 1; fi
ASIGN="$SDKW\\build-tools\\$BT\\apksigner.bat"
echo "apksigner: $ASIGN"
powershell -NoProfile -Command "& '$ASIGN' sign --ks '$KS' --ks-pass "pass:$KS_PASS" --key-pass "pass:$KS_PASS" --out '$OW\A9-$TAG.signed.apk' '$OW\A9-$TAG.apk'" && echo "签名OK" || { echo "签名失败，保留未签名包供排查"; exit 1; }
rm -f "$O/A9-$TAG.apk"                       # 签名成功才删中间包，别把盘塞满
"$ADB" install -r "$O/A9-$TAG.signed.apk" | tail -1
# crashtest 已按车主要求停用：会 force-stop 游戏打断实测（油白费）。
# 需要崩溃复现时手动跑: ./crashtest.sh <标签>
