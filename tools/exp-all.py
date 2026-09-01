#!/usr/bin/env python3
"""合并构建：原版 fleet-plan（21车）在前 + 实验九车在后。

同槽位冲突时**后写胜出**：科迈罗LT / Zonda R / SC63 / Apollo IE / DBS
的物理以实验配置为准；但外观（CarDef）不被自体强化覆盖——
LT 会带女武神壳、Z4 会带 AMG 壳（来自原版 swap）。
"""
import json, subprocess, sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
CARSWAP = BASE / "tools" / "carswap.py"

plan = json.loads((BASE / "fleet-plan.json").read_text(encoding="utf-8"))
argv = [sys.executable, str(CARSWAP)]
for s in plan["swaps"]:
    argv += ["--swap", f"{s['src']}>{s['dst']}"]
    if s.get("keep_look"):
        argv.append("--keep-look")
    for k, v in s.get("tweaks", {}).items():
        argv += ["--" + k.replace("_", "-"), str(v)]

EXP = [
  ("Nissan 370Z>Nissan 370Z",
   ["--top-speed", "222.5", "--accel", "2.5", "--handling", "1.2", "--grip", "0.95",
    "--steer", "58000", "--nitro-boost", "1.2", "--susp", "0.000,0.020"]),
  ("Mitsubishi Lancer Evolution>Mitsubishi Lancer Evolution",
   ["--mass", "120", "--accel", "2.8", "--handling", "1.2", "--steer", "54000",
    "--grip", "0.92", "--susp", "0.000,0.030"]),
  ("BMW Z4 LCI E89>BMW Z4 LCI E89",
   ["--mass", "10000", "--accel", "2000", "--handling", "1.2", "--steer", "300000",
    "--grip", "20", "--downforce", "5000", "--nitro-boost", "10"]),
  ("Pagani Zonda R>Pagani Zonda R",
   ["--grip", "0.92", "--handling", "0.6", "--steer", "28000"]),
  ("Chevrolet Camaro LT>Chevrolet Camaro LT",
   ["--accel", "2.8", "--grip", "0.98", "--handling", "1.2", "--steer", "52000",
    "--nitro-boost", "1.5", "--susp", "0.000,0.010", "--damp", "0.5", "--downforce", "300"]),
  ("Lamborghini SC63>Lamborghini SC63",
   ["--top-speed", "270", "--grip", "0.92", "--handling", "0.7", "--nitro-drain", "0.5"]),
  ("Puritalia Berlinetta>Puritalia Berlinetta",
   ["--top-speed", "270", "--grip", "0.92"]),
  ("Apollo IE>Apollo IE",
   ["--top-speed", "270", "--grip", "0.92", "--handling", "0.75"]),
  ("Aston Martin DBS Superleggera>Aston Martin DBS Superleggera",
   ["--top-speed", "270", "--accel", "2.5", "--grip", "0.92", "--handling", "0.72"]),
]
for spec, tw in EXP:
    argv += ["--swap", spec] + tw
argv.append("--apply")

r = subprocess.run(argv, cwd=str(BASE / "tools"))
sys.exit(r.returncode)
