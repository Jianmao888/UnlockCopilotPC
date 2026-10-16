#!/usr/bin/env python3
"""
frida_ai_ready.py — 在 AI Dev Gallery 进程里调用 Windows AI 的就绪/下载流程

目标（用户思路的落点）：
  如果设备被认作 Copilot+，应用调用 Windows AI API 时系统会自动下载模型包。
  这里直接在同一进程里：
    1. 激活 Microsoft.Windows.AI.Text.LanguageModel 的 factory
    2. dump 它的静态方法槽（找到 GetReadyState / EnsureReadyAsync）
    3. 调 GetReadyState 看当前状态
    4. 调 EnsureReadyAsync 触发下载
    5. 前后对比 AIComponentManager 的已安装组件数

用法:
  python frida_ai_ready.py dump            # 只 dump vtable
  python frida_ai_ready.py call <slot>     # 调某个槽位
  python frida_ai_ready.py ready           # 走完整流程
"""
import json
import sys
import time

import frida

PID = None
for p in frida.get_local_device().enumerate_processes():
    if "aid" in p.name.lower() or "gallery" in p.name.lower():
        PID = p.pid
        break

COMMON = r"""
function combaseFns() {
  var m = Process.getModuleByName('combase.dll');
  return {
    RoInitialize: new NativeFunction(m.getExportByName('RoInitialize'), 'int', ['int'], 'win64'),
    CreateString: new NativeFunction(m.getExportByName('WindowsCreateString'), 'int', ['pointer','uint','pointer'], 'win64'),
    DeleteString: new NativeFunction(m.getExportByName('WindowsDeleteString'), 'int', ['pointer'], 'win64'),
    RawBuffer: new NativeFunction(m.getExportByName('WindowsGetStringRawBuffer'), 'pointer', ['pointer','pointer'], 'win64'),
    GetFactory: new NativeFunction(m.getExportByName('RoGetActivationFactory'), 'int', ['pointer','pointer','pointer'], 'win64')
  };
}

var IID_FACTORY = [0x35,0,0,0,0,0,0,0,0xc0,0,0,0,0,0,0,0x46];

function activateClass(c, name) {
  var h = Memory.alloc(8); h.writePointer(ptr(0));
  var s = Memory.allocUtf16String(name);
  var hr = c.CreateString(s, name.length, h);
  if (hr < 0) return null;
  var iid = Memory.alloc(16); iid.writeByteArray(IID_FACTORY);
  var out = Memory.alloc(8); out.writePointer(ptr(0));
  var hr2 = c.GetFactory(h.readPointer(), iid, out);
  c.DeleteString(h.readPointer());
  if (hr2 < 0) return null;
  return out.readPointer();
}

function slotOf(p, n) {
  var vt = p.readPointer();
  return vt.add(n * Process.pointerSize).readPointer();
}

function runtimeClass(c, p) {
  try {
    var fn = new NativeFunction(slotOf(p, 4), 'int', ['pointer','pointer'], 'win64');
    var h = Memory.alloc(8); h.writePointer(ptr(0));
    var hr = fn(p, h);
    if (hr < 0 || h.readPointer().isNull()) return null;
    var len = Memory.alloc(4); len.writeU32(0);
    var buf = c.RawBuffer(h.readPointer(), len);
    var s = buf.readUtf16String(len.readU32());
    c.DeleteString(h.readPointer());
    return s;
  } catch (e) { return null; }
}
"""

DUMP_JS = COMMON + r"""
var c = combaseFns();
c.RoInitialize(1);
send({event:'info', msg:'RoInitialize ok'});
var CLASSES = [
  "Microsoft.Windows.AI.AICapabilities",
  "Microsoft.Windows.AI.Text.LanguageModel",
  "Microsoft.Windows.AI.Imaging.ImageScaler"
];
for (var i = 0; i < CLASSES.length; i++) {
  var f = activateClass(c, CLASSES[i]);
  if (!f) { send({event:'info', msg: CLASSES[i] + ' 激活失败'}); continue; }
  var slots = [];
  for (var s = 6; s < 22; s++) slots.push(slotOf(f, s).toString());
  send({event:'vt', cls: CLASSES[i], factory: f.toString(), slots: slots});
}
send({event:'done'});
"""

CALL_JS = COMMON + r"""
var c = combaseFns();
c.RoInitialize(1);
var TARGET = __CLASS__;
var SLOT = __SLOT__;
var f = activateClass(c, TARGET);
if (!f) { send({event:'info', msg:'激活失败'}); }
else {
  send({event:'info', msg:'factory=' + f.toString() + ' 调用 slot ' + SLOT});
  try {
    var fn = new NativeFunction(slotOf(f, SLOT), 'int', ['pointer','pointer'], 'win64');
    var out = Memory.alloc(8); out.writePointer(ptr(0));
    var hr = fn(f, out);
    var o = out.readPointer();
    var info = { event:'call', cls:TARGET, slot:SLOT, hr:hr & 0xffffffff, out:o.toString() };
    if (hr >= 0 && !o.isNull()) {
      info.outClass = runtimeClass(c, o);
      // 若返回的是 IAsyncOperation，读 Status(slot 7) 和 get_Results(slot 8)
      try {
        var gs = new NativeFunction(slotOf(o, 7), 'int', ['pointer','pointer'], 'win64');
        var st = Memory.alloc(4); st.writeU32(0);
        var hr2 = gs(o, st);
        info.asyncStatus = st.readU32();
      } catch (e) { info.asyncNote = String(e); }
    }
    send(info);
  } catch (e) { send({event:'info', msg:'调用崩溃: ' + String(e)}); }
}
send({event:'done'});
"""


def run(js):
    session = frida.attach(PID)
    script = session.create_script(js)
    script.on("message", on_message)
    script.load()
    time.sleep(8)
    session.detach()


def on_message(msg, data):
    if msg.get("type") != "send":
        if msg.get("type") == "error":
            print("  [script error]", msg.get("description"))
        return
    p = msg["payload"]
    e = p.get("event")
    if e == "vt":
        print(f"\n== {p['cls']} ==")
        print(f"   factory = {p['factory']}")
        for i, a in enumerate(p["slots"]):
            print(f"     slot[{i+6:2}] = {a}")
    elif e == "call":
        print(f"\n   {p['cls']} slot[{p['slot']}] -> HRESULT 0x{p['hr']:08x} out={p['out']}")
        if p.get("outClass"): print(f"      返回对象类名 = {p['outClass']}")
        if p.get("asyncStatus") is not None: print(f"      AsyncStatus = {p['asyncStatus']}")
        if p.get("asyncNote"): print(f"      note = {p['asyncNote']}")
    elif e == "info":
        print("  ", p.get("msg"))
    elif e == "done":
        print("  ==> done")


def main():
    if PID is None:
        print("AI Dev Gallery 未运行")
        return 1
    mode = sys.argv[1] if len(sys.argv) > 1 else "dump"
    print(f"==> 附加到 AI Dev Gallery (pid={PID})  模式={mode}")
    if mode == "dump":
        run(DUMP_JS)
    elif mode == "call":
        slot = int(sys.argv[2])
        cls = sys.argv[3] if len(sys.argv) > 3 else "Microsoft.Windows.AI.Text.LanguageModel"
        run(CALL_JS.replace("__CLASS__", json.dumps(cls)).replace("__SLOT__", str(slot)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
