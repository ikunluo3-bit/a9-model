#!/bin/bash
set -e
OUT="C:/Users/player/Desktop/A9 sifugc/output"
python repack.py --apk "$OUT/A9-600300-6.0.0k-base.apk" --tuned "C:/Users/player/Desktop/a9模型/tuned-v2" --out "$OUT/A9-600300-v2.apk" --skip-sign
