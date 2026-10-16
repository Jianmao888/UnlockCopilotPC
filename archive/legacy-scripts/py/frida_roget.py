#!/usr/bin/env python3
"""
frida_roget.py — hook RoGetActivationFactory + QueryInterface，捕获应用激活 WinRT 类时使用的 IID

原理：
  应用调用 WinRT 投影 API 时，内部会走
     RoGetActivationFactory(className, IID_StaticInterface, &factory)
  只要 hook 这个函数，就能拿到 (类名, IID) 的对应关系 ——
  这正是我们缺的那块拼图，也是之后精确 hook 静态方法的基础。

  同时 hook IUnknown::QueryInterface 太吵；这里只在 RoGetActivationFactory 命中时，
  对返回的 factory 再 QueryInterface 试几个候选 IID（可选）。

用法: python frida_roget.py [pid] [seconds]
"""
import sys
import time

import frida

FILTER = ("Windows.AI", "Microsoft.Windows.AI", "Microsoft.Windows.Vision",
          "Microsoft.Windows.Workloads", "Microsoft.Windows.SemanticSearch",
          "AIComponent", "AIPlatformCapability", "Microsoft.Graphics.Imaging")

JS = r"""
'use strict';
var combase;
try { combase = Process.getModuleByName('combase.dll'); }
catch (e) { send({event:'error', msg:'no combase'}); }

function guidOf(p) {
  try {
    var b = new Uint8Array(p.readByteArray(16));
    function h(x){ return ('0'+x.toString(16)).slice(-2); }
    var s = h(b[3])+h(b[2])+h(b[1])+h(b[0])+'-'+h(b[5])+h(b[4])+'-'+h(b[7])+h(b[6])+'-'
          + h(b[8])+h(b[9])+'-'+h(b[10])+h(b[11])+h(b[12])+h(b[13])+h(b[14])+h(b[15]);
    return s;
  } catch (e) { return '?'; }
}

var FILTER = __FILTER__;

if (combase) {
  var CreateString = new NativeFunction(combase.getExportByName('WindowsCreateString'),
      'int', ['pointer','uint','pointer'], 'win64');
  var RawBuffer = new NativeFunction(combase.getExportByName('WindowsGetStringRawBuffer'),
      'pointer', ['pointer','pointer'], 'win64');
  var DeleteString = new NativeFunction(combase.getExportByName('WindowsDeleteString'),
      'int', ['pointer'], 'win64');

  Interceptor.attach(combase.getExportByName('RoGetActivationFactory'), {
    onEnter: function (args) {
      this.className = null;
      this.iidPtr = args[1];
      try {
        var len = Memory.alloc(4); len.writeU32(0);
        var buf = RawBuffer(args[0], len);
        var n = len.readU32();
        if (n > 0 && n < 200) this.className = buf.readUtf16String(n);
      } catch (e) {}
    },
    onLeave: function (retval) {
      var cn = this.className;
      if (!cn) return;
      var hit = FILTER.some(function (f) { return cn.indexOf(f) >= 0; });
      if (!hit) return;
      var hr = retval.toInt32();
      var iid = guidOf(this.iidPtr);
      var out = { event: 'activate', cls: cn, hr: hr, iid: iid };
      if (hr >= 0) {
        try {
          // args 在 onLeave 不可用，改用 this 保存
          out.factory = this.factoryPtr ? this.factoryPtr.toString() : '';
        } catch (e) {}
      }
      send(out);
    }
  });
  send({event:'ready', msg:'RoGetActivationFactory hooked'});
}
"""


def on_message(msg, data):
    if msg.get("type") != "send":
        if msg.get("type") == "error":
            print("  [script error]", msg.get("description"))
        return
    p = msg["payload"]
    e = p.get("event")
    if e == "activate":
        print(f"  cls = {p['cls']}")
        print(f"      IID = {p['iid']}   hr = 0x{p['hr'] & 0xffffffff:08x}")
    elif e in ("ready", "error"):
        print("  ", p.get("msg"))


def main():
    pid = int(sys.argv[1]) if len(sys.argv) > 1 else None
    if pid is None:
        for p in frida.get_local_device().enumerate_processes():
            if "aid" in p.name.lower() or "gallery" in p.name.lower():
                pid = p.pid; break
    if pid is None:
        print("找不到 AI Dev Gallery"); return 1
    secs = int(sys.argv[2]) if len(sys.argv) > 2 else 60
    print(f"==> 附加 pid={pid}，监听 {secs} 秒")
    session = frida.attach(pid)
    script = session.create_script(JS.replace("__FILTER__", str(list(FILTER))))
    script.on("message", on_message)
    script.load()
    time.sleep(secs)
    session.detach()
    print("==> 结束")
    return 0


if __name__ == "__main__":
    sys.exit(main())
