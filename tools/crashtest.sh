#!/bin/bash
# A9 崩溃复现：启动 -> 等连接错误弹窗 -> 点重试 -> 判定
# 判定用「进程消失 + dumpsys exit-info」，不用 logcat crash buffer（会漏）
# 阴性对照已验证：纯物理版 v2 走同一路径不崩
ADB="/c/Users/player/AppData/Local/Android/Sdk/platform-tools/adb.exe"
PKG=com.aligames.kuang.kybc.tap
S="/c/Users/YJLJIJ~1/AppData/Local/Temp/claude/C--Users-yjl-jiji-xiao-Desktop-A9-sifugc/3e90de05-6bfb-45cf-99ae-e6f352fe5720/scratchpad"
TAG="${1:-test}"
"$ADB" logcat -c -b all 2>/dev/null
"$ADB" shell am force-stop $PKG
"$ADB" shell monkey -p $PKG -c android.intent.category.LAUNCHER 1 >/dev/null 2>&1
for i in $(seq 1 12); do sleep 5; [ -n "$("$ADB" shell pidof $PKG 2>/dev/null|tr -d '\r')" ] && break; done
sleep 40
"$ADB" exec-out screencap -p > "$S/$TAG-before.png" 2>/dev/null
"$ADB" shell input tap 1396 935          # 「重试」
RES=2
for i in $(seq 1 14); do
  sleep 5
  P=$("$ADB" shell pidof $PKG 2>/dev/null | tr -d '\r')
  if [ -z "$P" ]; then
    sleep 3
    R=$("$ADB" shell "dumpsys activity exit-info $PKG 2>/dev/null | grep -m1 -A1 'process=com.aligames' | grep -o 'reason=[0-9]* ([A-Z ()]*)'" | tr -d '\r')
    echo "[$TAG] 进程在点重试后 $((i*5))s 消失 -> ${R:-未知}"
    echo "$R" | grep -q "APP CRASH" && RES=1 || RES=2
    break
  fi
  RES=0
done
[ "$RES" = 0 ] && { echo "[$TAG] 点重试后 70s 进程仍在 (pid=$P) —— **未崩**"; "$ADB" exec-out screencap -p > "$S/$TAG-after.png" 2>/dev/null; }
"$ADB" shell am force-stop $PKG   # 不让游戏一直跑
exit $RES
