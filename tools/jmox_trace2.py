#!/usr/bin/env python3
"""frida spawn 模式：重启游戏，捕获启动期 JModel 解析全程。"""
import frida, sys, io, time, threading, subprocess

if sys.platform == "win32" and not isinstance(sys.stdout, io.TextIOWrapper):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

PKG = "com.aligames.kuang.kybc.tap"
LOG = open(r"build\jmox_work\frida_trace2.log", "w", encoding="utf-8")
ADB = r"C:\Users\player\AppData\Local\Android\Sdk\platform-tools\adb.exe"

JS = r"""
'use strict';
var base = null;
Process.enumerateModules().forEach(function(m){ if (m.name === "libAsphalt9.so") base = m.base; });
send({"e":"base", "v": base ? base.toString() : "null"});
var cnt = 0;
function hook(off, name) {
    Interceptor.attach(base.add(off), {
        onEnter: function(args) {
            cnt++;
            var x0 = this.context.x0, x1 = this.context.x1, lr = this.context.lr;
            var flag = -1;
            try { flag = Memory.readU8(x0.add(12)); } catch (e) {}
            send({"e":name, "x0":x0.toString(), "x1":x1.toString(),
                  "lr":ptr(lr).sub(base).toString(16), "flag":flag, "n":cnt});
        }
    });
}
hook(0x606a5c8, "unpack");
hook(0x606a558, "unpack2");
hook(0x606a500, "unpack3");
hook(0x4cb5a4c, "recparse");
send({"e":"ready"});
"""

dev = frida.get_usb_device(timeout=10)
pid = dev.spawn([PKG])
session = dev.attach(pid)

def on_msg(msg, data):
    if msg["type"] == "send":
        p = msg["payload"]
        if p.get("e") == "base":
            print("base =", p["v"], flush=True)
            return
        if p.get("e") == "ready":
            print("hooks ready, resuming", flush=True)
            dev.resume(pid)
            return
        LOG.write(f'{p["n"]:5d} {p["e"]:<10} x0={p["x0"]} x1={p["x1"]} lr=0x{p["lr"]} flag={p["flag"]}\n')
        if p["n"] % 50 == 0:
            LOG.flush()
            print(f'  {p["n"]} events...', flush=True)
    else:
        print("MSG-ERR:", msg.get("description", "")[:120], flush=True)

script = session.create_script(JS)
script.on("message", on_msg)
script.load()

def stopper():
    time.sleep(150)
    print("窗口结束", flush=True)
    session.detach()
    sys.exit(0)

threading.Thread(target=stopper, daemon=True).start()

while True:
    time.sleep(1)
