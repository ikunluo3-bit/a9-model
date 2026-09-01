#!/usr/bin/env python3
"""iOS 版构建：gdb-ios-6.0.0 基础库上只跑点名的 swap（不带车队）。

产物写到 tuned-ios/。当前配置（2026-08-31 车主点名）：
  1. Infiniti Project Black S -> Bugatti Tourbillon
     抓地1.2 锐度70000 操控0.6 氮气消耗x0.6
  2. Bugatti Divo 本尊（iOS 账号已解锁）
     锐度72000 操控0.65 极速290 氮气消耗x0.8
满改锁默认开。
"""
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "tools"))

import index6
index6.G = BASE / "gdb-ios-6.0.0"          # 必须在 import carswap 之前换库

import carswap
carswap.OUT = BASE / "tuned-ios"           # 产物隔离

SWAPS = [
    ("Infiniti Project Black S>Bugatti Tourbillon",
     ["--grip", "1.2", "--steer", "70000", "--handling", "0.6", "--nitro-drain", "0.6"]),
    ("Bugatti Divo>Bugatti Divo",
     ["--steer", "72000", "--handling", "0.65", "--top-speed", "290", "--nitro-drain", "0.8"]),
]

argv = ["carswap.py"]
for spec, tw in SWAPS:
    argv += ["--swap", spec] + tw
argv.append("--apply")

sys.argv = argv
carswap.main()
