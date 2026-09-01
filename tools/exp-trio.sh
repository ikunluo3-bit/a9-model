#!/bin/bash
# 三台实验车的累积构建（2026-08-28 实验线）。
# 铁律：每次改其中一台，**必须带着另外两台的完整行**重跑——
# carswap 从原始库全量重算，命令里没有的车会被冲回原厂（README 陷阱 12）。
# 用法: bash tools/exp-trio.sh [标签]   （默认标签 exp-trio）
set -e
cd "$(dirname "$0")/.."
TAG="${1:-exp-trio}"

python tools/carswap.py \
  --swap "Nissan 370Z>Nissan 370Z" \
      --top-speed 222.5 --accel 2.5 --handling 1.2 --grip 0.95 --steer 58000 --nitro-boost 1.2 --susp 0.000,0.020 \
  --swap "Mitsubishi Lancer Evolution>Bugatti Tourbillon" \
      --grip 1.2 --steer 70000 --handling 0.6 --nitro-drain 0.6 \
  --swap "BMW Z4 LCI E89>BMW Z4 LCI E89" \
      --mass 10000 --accel 2000 --handling 1.2 --steer 300000 --grip 20 --downforce 5000 --nitro-boost 10 \
  --swap "Pagani Zonda R>Pagani Zonda R" \
      --grip 0.92 --handling 0.6 --steer 28000 \
  --swap "Chevrolet Camaro LT>Chevrolet Camaro LT" \
      --accel 2.8 --grip 0.98 --handling 1.2 --steer 52000 --nitro-boost 1.5 --susp 0.000,0.010 \
      --damp 0.5 --downforce 300 \
  --swap "Lamborghini SC63>Lamborghini SC63" \
      --top-speed 270 --grip 0.92 --handling 0.7 --nitro-drain 0.5 \
  --swap "Puritalia Berlinetta>Puritalia Berlinetta" \
      --top-speed 270 --grip 0.92 \
  --swap "Apollo IE>Apollo IE" \
      --top-speed 270 --grip 1.2 --handling 0.75 \
  --swap "Aston Martin DBS Superleggera>Aston Martin DBS Superleggera" \
      --top-speed 270 --accel 2.5 --grip 0.92 --handling 0.72 \
  --apply

cd tools && ./build.sh "$TAG" --tuned "C:\Users\player\Desktop\a9模型\tuned-carswap" \
  --files CarPhysics.gdb CarChassis.gdb CarDef.gdb
