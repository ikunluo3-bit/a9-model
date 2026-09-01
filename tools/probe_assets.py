#!/usr/bin/env python3
"""资产请求探针：monkey 启动游戏 -> frida 附加 -> 记录所有资产打开路径。

用途：判定换皮后游戏实际按哪个模型路径加载（伊莫拉换挑战者失败定位）。
日志: build/jmox_work/asset_probe.log
"""
import frida, sys, io, time, subprocess

if sys.platform == "win32" and not isinstance(sys.stdout, io.TextIOWrapper):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

PKG = "com.aligames.kuang.kybc.tap"
LOGPATH = r"build\jmox_work\asset_probe.log"
LOG = open(LOGPATH, "w", encoding="utf-8")
ADB = r"C:\Users\player\AppData\Local\Android\Sdk\platform-tools\adb.exe"

JS = r"""
'use strict';
function log(s){ send({"e":"log", "v":s}); }

// 1) 原生 AAssetManager_open
try {
    var libandroid = Process.getModuleByName("libandroid.so");
    var addr = null;
    libandroid.enumerateExports().forEach(function(e){
        if (e.name === "AAssetManager_open") addr = e.address;
    });
    if (addr) {
        Interceptor.attach(addr, {
            onEnter: function(args) {
                try { send({"e":"am", "p": args[1].readCString()}); } catch(e){}
            }
        });
        log("AAssetManager_open hooked");
    } else log("AAssetManager_open NOT FOUND");
} catch(e) { log("native err: " + e); }

// 2) libc open/openat（自研 zip 读取器路径）
try {
    var libc = Process.getModuleByName("libc.so");
    ["open", "openat"].forEach(function(fn){
        var a = null;
        libc.enumerateExports().forEach(function(e){ if (e.name === fn) a = e.address; });
        if (a) Interceptor.attach(a, {
            onEnter: function(args) {
                try {
                    var p = args[fn === "openat" ? 1 : 0].readCString();
                    if (p && p.indexOf(".apk") >= 0) send({"e":"open", "p": p});
                } catch(e){}
            }
        });
    });
    log("libc open hooked");
} catch(e) { log("libc err: " + e); }

// 3) Java AssetManager
Java.perform(function(){
    try {
        var AM = Java.use("android.content.res.AssetManager");
        AM.open.overload("java.lang.String").implementation = function(p){
            send({"e":"java", "p": p});
            return this.open(p);
        };
        AM.open.overload("java.lang.String", "int").implementation = function(p, m){
            send({"e":"java", "p": p});
            return this.open(p, m);
        };
        log("java AssetManager hooked");
    } catch(e) { log("java err: " + e); }
});
send({"e":"ready"});
"""

def on_message(msg, data):
    if msg.get("type") != "message":
        print("!!", msg); return
    p = msg["payload"]
    e = p.get("e")
    if e == "log":
        print("[js]", p["v"]); LOG.write("[js] " + p["v"] + "\n"); LOG.flush()
    elif e == "ready":
        print("[js] ready"); LOG.write("[ready]\n"); LOG.flush()
    elif e in ("am", "java"):
        line = "%s %s" % (e, p["p"])
        LOG.write(line + "\n"); LOG.flush()
        # 只把车型相关的打到控制台
        if "car" in p["p"].lower() or "main/" in p["p"]:
            print(line)
    elif e == "open":
        LOG.write("open " + p["p"] + "\n"); LOG.flush()

def find_pid(dev):
    # 反作弊会把进程名从 /proc 枚举里藏掉，应用列表还能看到
    for a in dev.enumerate_applications():
        if a.identifier == PKG and a.pid > 0:
            return a.pid
    return None

def main():
    dev = frida.get_usb_device(timeout=10)
    pid = find_pid(dev)
    if pid:
        print("游戏已在运行, attach", pid)
    else:
        print("monkey 启动游戏 ...")
        subprocess.run([ADB, "shell", "monkey", "-p", PKG,
                        "-c", "android.intent.category.LAUNCHER", "1"],
                       capture_output=True)
        for _ in range(40):           # 最多等 20s 出进程
            pid = find_pid(dev)
            if pid:
                break
            time.sleep(0.5)
        if not pid:
            sys.exit("没等到游戏进程")
    print("attach pid", pid)
    session = dev.attach(pid)
    script = session.create_script(JS)
    script.on("message", on_message)
    script.load()
    print("探针已加载，日志 ->", LOGPATH)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()
