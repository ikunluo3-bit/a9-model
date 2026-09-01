#!/usr/bin/env python3
"""frida 动态追踪 JModelParser：hook 解包分发器/ReadXorBuffer/记录解析，抓 lr 调用链。"""
import frida, sys, io, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

JS = r"""
'use strict';
var base = null;
Process.enumerateModules().forEach(function(m){ if (m.name === "libAsphalt9.so") base = m.base; });
send({"e":"base","v":base.toString()});
var cnt = 0;
function hook(off, name) {
    Interceptor.attach(base.add(off), {
        onEnter: function(args) {
            if (cnt++ > 400) return;
            var x0 = this.context.x0, x1 = this.context.x1, lr = this.context.lr;
            var flag = -1;
            try { flag = Memory.readU8(x0.add(12)); } catch (e) {}
            send({"e":name, "x0":x0.toString(), "x1":x1.toString(),
                  "lr":ptr(lr).sub(base).toString(16), "flag":flag});
        }
    });
}
hook(0x606a5c8, "unpack");
hook(0x606a6d8, "readxor");
hook(0x4cb5a4c, "recparse");
hook(0x4cb67c4, "kvparse");
send({"e":"ready"});
"""

LOG = open(r"build\jmox_work\frida_trace.log", "w", encoding="utf-8")

dev = frida.get_usb_device(timeout=10)
session = dev.attach(2707)
script = session.create_script(JS)
got_base = {}

def on_msg(msg, data):
    if msg["type"] != "send":
        print("MSG:", msg)
        return
    p = msg["payload"]
    if p.get("e") == "base":
        got_base["v"] = p["v"]
        print("libAsphalt9 base =", p["v"])
        return
    if p.get("e") == "ready":
        print("hooks 就绪")
        return
    line = f'{p["e"]:<10} x0={p["x0"]} x1={p["x1"]} lr=0x{p["lr"]} flag={p["flag"]}'
    LOG.write(line + "\n")
    LOG.flush()

script.on('message', on_msg)
script.load()
print("attached, 开始导航触发模型加载... (60s 窗口)")
time.sleep(60)
print("窗口结束, 共", sum(1 for _ in open(r"build\jmox_work\frida_trace.log", encoding="utf-8")), "条")
session.detach()
