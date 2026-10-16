#!/usr/bin/env python3
"""
frida_activate_test.py — 在具有包身份的进程里测试 Windows AI 类能否激活

思路：
  Microsoft.Windows.AI.* / Microsoft.Windows.Vision.* 由 AIFabric 框架包注册，
  未打包进程激活会得到 REGDB_E_CLASSNOTREG。
  但在打包应用（AI Dev Gallery）进程里，包图存在，应该能激活。

用法: python frida_activate_test.py [pid]
"""
import sys
import time
import frida

JS = r"""
'use strict';
var CLASSES = [
  "Microsoft.Windows.AI.AICapabilities",
  "Microsoft.Windows.AI.AIFeatureReadyResult",
  "Microsoft.Windows.AI.Text.LanguageModel",
  "Microsoft.Windows.Vision.TextRecognizer",
  "Microsoft.Windows.Vision.ScreenRegionDetector",
  "Microsoft.Windows.AI.Imaging.ImageScaler",
  "Microsoft.Windows.SemanticSearch.SemanticTextEmbeddingsCreator",
  "Microsoft.Windows.Workloads.WorkloadManager",
  "Windows.AI.Management.Internal.AIComponentManager"
];

function run() {
  var combase;
  try { combase = Process.getModuleByName('combase.dll'); }
  catch (e) { send({ event: 'error', msg: 'no combase' }); return; }

  var RoInitialize = new NativeFunction(combase.getExportByName('RoInitialize'), 'int', ['int'], 'win64');
  var hr0 = RoInitialize(1);
  send({ event: 'init', hr: hr0 });

  var WindowsCreateString = new NativeFunction(combase.getExportByName('WindowsCreateString'),
      'int', ['pointer', 'uint', 'pointer'], 'win64');
  var WindowsDeleteString = new NativeFunction(combase.getExportByName('WindowsDeleteString'),
      'int', ['pointer'], 'win64');
  var WindowsGetStringRawBuffer = new NativeFunction(combase.getExportByName('WindowsGetStringRawBuffer'),
      'pointer', ['pointer', 'pointer'], 'win64');
  var RoGetActivationFactory = new NativeFunction(combase.getExportByName('RoGetActivationFactory'),
      'int', ['pointer', 'pointer', 'pointer'], 'win64');

  // IID_IActivationFactory
  var iid = Memory.alloc(16);
  iid.writeByteArray([0x35,0x00,0x00,0x00,0x00,0x00,0x00,0x00,
                      0xc0,0x00,0x00,0x00,0x00,0x00,0x00,0x46]);

  function activate(name) {
    var h = Memory.alloc(8);
    h.writePointer(ptr(0));
    var s = Memory.allocUtf16String(name);
    var hr = WindowsCreateString(s, name.length, h);
    if (hr < 0) return { name: name, hr: hr, note: 'CreateString 失败' };
    var out = Memory.alloc(8);
    out.writePointer(ptr(0));
    var hr2 = RoGetActivationFactory(h.readPointer(), iid, out);
    var fac = out.readPointer();
    var res = { name: name, hr: hr2, factory: fac.toString() };
    if (hr2 >= 0 && !fac.isNull()) {
      // 读 vtable，尝试 GetRuntimeClassName 验证
      try {
        var vt = fac.readPointer();
        var grcn = new NativeFunction(vt.add(4 * Process.pointerSize).readPointer(),
            'int', ['pointer', 'pointer'], 'win64');
        var cn = Memory.alloc(8); cn.writePointer(ptr(0));
        var hr3 = grcn(fac, cn);
        if (hr3 >= 0 && !cn.readPointer().isNull()) {
          var len = Memory.alloc(4); len.writeU32(0);
          var buf = WindowsGetStringRawBuffer(cn.readPointer(), len);
          res.runtimeClass = buf.readUtf16String(len.readU32());
          WindowsDeleteString(cn.readPointer());
        }
      } catch (e) { res.note = String(e); }
    }
    WindowsDeleteString(h.readPointer());
    return res;
  }

  for (var i = 0; i < CLASSES.length; i++) {
    try { send({ event: 'result', data: activate(CLASSES[i]) }); }
    catch (e) { send({ event: 'error', msg: CLASSES[i] + ': ' + String(e) }); }
  }
  send({ event: 'done' });
}

run();
"""


def on_message(msg, data):
    if msg.get("type") != "send":
        if msg.get("type") == "error":
            print("  [script error]", msg.get("description"))
        return
    p = msg["payload"]
    e = p.get("event")
    if e == "init":
        print(f"RoInitialize -> 0x{p['hr'] & 0xffffffff:08x}\n")
    elif e == "result":
        d = p["data"]
        hr = d["hr"] & 0xffffffff
        tag = "OK  " if hr == 0 else "FAIL"
        cls = d.get("runtimeClass", "")
        note = d.get("note", "")
        print(f"  {tag} 0x{hr:08x}  {d['name']}")
        if cls: print(f"         runtimeClass = {cls}")
        if note: print(f"         note = {note}")
    elif e == "error":
        print("  [err]", p.get("msg"))
    elif e == "done":
        print("\n==> 完成")


def main():
    pid = int(sys.argv[1]) if len(sys.argv) > 1 else None
    if pid is None:
        for p in frida.get_local_device().enumerate_processes():
            if "aid" in p.name.lower() or "gallery" in p.name.lower():
                pid = p.pid
                print(f"找到 {p.name} (pid={p.pid})")
                break
    if pid is None:
        print("找不到 AI Dev Gallery 进程")
        return 1
    session = frida.attach(pid)
    script = session.create_script(JS)
    script.on("message", on_message)
    script.load()
    time.sleep(6)
    session.detach()
    return 0


if __name__ == "__main__":
    sys.exit(main())
