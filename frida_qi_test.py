#!/usr/bin/env python3
"""
frida_qi_test.py — 用 QueryInterface 逐一验证候选 IID 哪个是静态接口

用法: python frida_qi_test.py
"""
import sys
import time

import frida

PID = None
for p in frida.get_local_device().enumerate_processes():
    if "aid" in p.name.lower() or "gallery" in p.name.lower():
        PID = p.pid
        break

TARGETS = {
    "Microsoft.Windows.AI.Text.LanguageModel": [
        "036294fe-e53c-5e66-93d2-7c92338db881",
        "391fbf11-59cd-575d-834a-9ef823116f98",
        "5b7a28c0-7777-52e5-9934-b95b514cf535",
        "a008d9ad-25ce-5a6b-9ceb-d8e95d04e10b",
    ],
    "Microsoft.Windows.AI.AICapabilities": [
        "37968861-98ee-599c-aa38-aa79866d6ddc",
        "936a78a6-c242-5937-9814-e512d4193a6d",
        "ec5f1d67-43c1-5bdb-b9f4-a0c7110582cb",
    ],
    "Microsoft.Windows.AI.Imaging.ImageScaler": [
        "06eec88e-91c5-5326-8128-2807faafa571",
        "1bd8d67c-8a7a-5fe7-98a5-cbdfeb509452",
        "2919fdc0-d772-5fd9-a8b7-ffb56010c99c",
        "3788c2fd-e496-53ab-85a7-e54a135824e9",
    ],
}

JS = r"""
'use strict';
var combase = Process.getModuleByName('combase.dll');
var fn = {
  RoInitialize: new NativeFunction(combase.getExportByName('RoInitialize'), 'int', ['int'], 'win64'),
  CreateString: new NativeFunction(combase.getExportByName('WindowsCreateString'), 'int', ['pointer','uint','pointer'], 'win64'),
  DeleteString: new NativeFunction(combase.getExportByName('WindowsDeleteString'), 'int', ['pointer'], 'win64'),
  RawBuffer: new NativeFunction(combase.getExportByName('WindowsGetStringRawBuffer'), 'pointer', ['pointer','pointer'], 'win64'),
  GetFactory: new NativeFunction(combase.getExportByName('RoGetActivationFactory'), 'int', ['pointer','pointer','pointer'], 'win64')
};
var IID_FACTORY = [0x35,0,0,0,0,0,0,0,0xc0,0,0,0,0,0,0,0x46];

function uuidBytes(s) {
  var h = s.replace(/-/g,'');
  var b = [];
  for (var i = 0; i < 16; i++) {
    var hi = parseInt(h[i*2], 16), lo = parseInt(h[i*2+1], 16);
    b.push(hi*16 + lo);
  }
  // 前三个字段是小端
  b = [b[3],b[2],b[1],b[0], b[5],b[4], b[7],b[6], b[8],b[9],b[10],b[11],b[12],b[13],b[14],b[15]];
  return b;
}

function activate(cn) {
  var h = Memory.alloc(8); h.writePointer(ptr(0));
  var s = Memory.allocUtf16String(cn);
  if (fn.CreateString(s, cn.length, h) < 0) return null;
  var iid = Memory.alloc(16); iid.writeByteArray(IID_FACTORY);
  var out = Memory.alloc(8); out.writePointer(ptr(0));
  var hr = fn.GetFactory(h.readPointer(), iid, out);
  fn.DeleteString(h.readPointer());
  if (hr < 0) return null;
  return out.readPointer();
}

var TARGETS = __TARGETS__;
fn.RoInitialize(1);

for (var cn in TARGETS) {
  var f = activate(cn);
  send({event:'cls', cls: cn, ok: !!f, factory: f ? f.toString() : ''});
  if (!f) continue;
  var qi = new NativeFunction(f.readPointer().readPointer(), 'int', ['pointer','pointer','pointer'], 'win64');
  var cands = TARGETS[cn];
  for (var i = 0; i < cands.length; i++) {
    var ib = uuidBytes(cands[i]);
    var im = Memory.alloc(16); im.writeByteArray(ib);
    var o = Memory.alloc(8); o.writePointer(ptr(0));
    var hr = qi(f, im, o);
    send({event:'qi', cls: cn, iid: cands[i], hr: hr & 0xffffffff, iface: o.readPointer().toString()});
  }
}
send({event:'done'});
"""


def on_message(msg, data):
    if msg.get("type") != "send":
        if msg.get("type") == "error":
            print("  [script error]", msg.get("description"))
        return
    p = msg["payload"]; e = p.get("event")
    if e == "cls":
        print(f"\n== {p['cls']}  (factory {p['factory']})")
    elif e == "qi":
        hr = p["hr"]
        tag = "*** 命中" if hr == 0 else "未命中"
        print(f"   QI {p['iid']}  -> 0x{hr:08x}  {tag}")
    elif e == "done":
        print("\n==> 完成")


def main():
    if PID is None:
        print("AI Dev Gallery 未运行")
        return 1
    print(f"==> 附加 pid={PID}")
    session = frida.attach(PID)
    script = session.create_script(JS.replace("__TARGETS__", __import__("json").dumps(TARGETS)))
    script.on("message", on_message)
    script.load()
    time.sleep(10)
    session.detach()
    return 0


if __name__ == "__main__":
    sys.exit(main())
