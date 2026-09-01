#!/bin/bash
set -e
KS_PASS_FILE="$(dirname "$0")/keystore.local"
[ -f "$KS_PASS_FILE" ] && KS_PASS="$(cat "$KS_PASS_FILE")" || { echo "缺 $KS_PASS_FILE（放一行签名口令，不入库）"; exit 1; }
OUT="C:/Users/player/Desktop/A9 sifugc/output"
BASE="$OUT/A9-600300-6.0.0k-base.apk"
RAW="$OUT/A9-600300-monster.apk"
ALIGNED="$OUT/A9-600300-monster.aligned.apk"
KS="C:/Users/player/Desktop/A9 sifugc/project/tools/a9-repack.keystore"
ZA="$HOME/AppData/Local/Android/Sdk/build-tools/37.0.0/zipalign.exe"
AS="$HOME/AppData/Local/Android/Sdk/build-tools/37.0.0/apksigner.bat"

echo "[1/3] 回封..."
python repack.py --apk "$BASE" --tuned "C:/Users/player/Desktop/a9模型/tuned-monster" --out "$RAW" --skip-sign

echo "[2/3] zipalign..."
"$ZA" -p -f 4 "$RAW" "$ALIGNED"
echo "  对齐完成"

echo "[3/3] 签名..."
"$AS" sign --ks "$KS" --ks-pass "pass:$KS_PASS" --key-pass "pass:$KS_PASS" "$ALIGNED"
"$AS" verify --print-certs "$ALIGNED" | head -4
echo ""
echo "成品: $ALIGNED"
ls -la "$ALIGNED"
