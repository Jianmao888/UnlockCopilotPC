#!/usr/bin/env python3
"""
frida_ready_call.py — 在 AI Dev Gallery 进程内调用 Windows AI 的就绪状态 / 下载流程

分步、可单步执行，避免整段崩溃：
  state   : 调 LanguageModel 的 GetReadyState（预期为 int 枚举输出）
  ensure  : 调 EnsureReadyAsync（触发下载流程）
  comps   : 读 AIComponentManager 已安装组件数（下载前后对比）

用法:
  python frida_ready_call.py state          # slot 6, int32 out
  python frida_ready_call.py ensure         # slot 7, void** out
  python frida_ready_call.py comps          # 组件数
  python frida_ready_call.py raw <slot> <kind>   # kind = obj | int | bool
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

SINGLE_JS = COMMON + r"""
var c = combaseFns(); c.RoInitialize(1);
var CLS = __CLASS__;
var S = __SLOT__;
var f = activateClass(c, CLS);
if (!f) { send({event:'info', msg: CLS + ' 激活失败'}); send({event:'done'}); }
else {
  send({event:'info', msg:'factory = ' + f.toString() + '  调用 slot ' + S});
  var fn = new NativeFunction(slotOf(f, S), 'int', ['pointer','pointer'], 'win64');
  var out = Memory.alloc(16);
  out.writeByteArray([0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]);
  var hr = fn(f, out);
  var p64 = out.readPointer();
  var info = { event:'single', cls: CLS, slot:S, hr: hr & 0xffffffff,
               u32: out.readU32(), ptr: p64.toString() };
  if (hr >= 0 && p64.compare(ptr("0x10000")) > 0 && p64.and(7).equals(0)) {
    try { info.outClass = runtimeClass(c, p64); } catch (e) { info.note = String(e); }
    // 若像 IAsyncOperation：slot7=Status(slot 7 起), 也试 get_Results
    try {
      var gp = new NativeFunction(slotOf(p64, 7), 'int', ['pointer','pointer'], 'win64');
      var st = Memory.alloc(4); st.writeU32(0);
      if (gp(p64, st) >= 0) info.asyncStatus = st.readU32();
    } catch (e) {}
  }
  send(info);
}
send({event:'done'});
"""

STATE_JS = COMMON + r"""
var c = combaseFns(); c.RoInitialize(1);
var f = activateClass(c, "Microsoft.Windows.AI.Text.LanguageModel");
if (!f) { send({event:'info', msg:'LanguageModel 激活失败'}); }
else {
  send({event:'info', msg:'LanguageModel factory = ' + f.toString()});
  // slot6 = GetReadyState (枚举输出), slot7 = EnsureReadyAsync, slot8 = CreateAsync
  for (var s = 6; s <= 8; s++) {
    try {
      var fn = new NativeFunction(slotOf(f, s), 'int', ['pointer','pointer'], 'win64');
      var out = Memory.alloc(16);
      out.writeByteArray([0,0,0,0,0,0,0,0, 0,0,0,0,0,0,0,0]);
      var hr = fn(f, out);
      var asU32 = out.readU32();
      var p64 = out.readPointer();
      var info = { event:'probe', slot:s, hr: hr & 0xffffffff, u32: asU32, ptr: p64.toString() };
      // 只有看起来像合法指针时才当对象处理（避免对枚举值解引用导致崩溃）
      if (hr >= 0 && p64.compare(ptr("0x10000")) > 0 && p64.and(7).equals(0)) {
        try { info.outClass = runtimeClass(c, p64); } catch (e) { info.note = String(e); }
      }
      send(info);
    } catch (e) { send({event:'info', msg:'slot ' + s + ' 异常: ' + String(e)}); }
  }
}
send({event:'done'});
"""

COMPS_JS = COMMON + r"""
var c = combaseFns(); c.RoInitialize(1);
var f = activateClass(c, "Windows.AI.Management.Internal.AIComponentManager");
if (!f) { send({event:'info', msg:'AIComponentManager 激活失败'}); send({event:'done'}); }
else {
  var fnMgr = new NativeFunction(slotOf(f, 6), 'int', ['pointer','pointer'], 'win64');
  var om = Memory.alloc(8); om.writePointer(ptr(0));
  var hr = fnMgr(f, om);
  var mgr = om.readPointer();
  if (hr < 0 || mgr.isNull()) { send({event:'info', msg:'取实例失败'}); send({event:'done'}); }
  else {
    var fnVec = new NativeFunction(slotOf(mgr, 6), 'int', ['pointer','pointer'], 'win64');
    var ov = Memory.alloc(8); ov.writePointer(ptr(0));
    var hr2 = fnVec(mgr, ov);
    var vec = ov.readPointer();
    if (hr2 < 0 || vec.isNull()) { send({event:'info', msg:'取 vector 失败'}); send({event:'done'}); }
    else {
      var fnSize = new NativeFunction(slotOf(vec, 7), 'int', ['pointer','pointer'], 'win64');
      var sz = Memory.alloc(4); sz.writeU32(0);
      var hr3 = fnSize(vec, sz);
      send({event:'count', hr: hr3 & 0xffffffff, size: sz.readU32(), vecClass: runtimeClass(c, vec)});
      // 逐项打印
      var n = sz.readU32();
      for (var i = 0; i < n; i++) {
        var fnAt = new NativeFunction(slotOf(vec, 6), 'int', ['pointer','uint','pointer'], 'win64');
        var oi = Memory.alloc(8); oi.writePointer(ptr(0));
        var hri = fnAt(vec, i, oi);
        var it = oi.readPointer();
        if (hri >= 0 && !it.isNull()) send({event:'item', idx:i, cls: runtimeClass(c, it)});
      }
    }
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
    if e == "probe":
        hr = p["hr"]
        tag = "OK  " if hr == 0 else "FAIL"
        print(f"  slot[{p['slot']}] {tag} HRESULT 0x{hr:08x}  u32={p['u32']}  ptr={p['ptr']}")
        if p.get("outClass"): print(f"        返回对象 = {p['outClass']}")
        if p.get("note"): print(f"        note = {p['note']}")
    elif e == "single":
        hr = p["hr"]
        tag = "OK  " if hr == 0 else "FAIL"
        print(f"  {p['cls']} slot[{p['slot']}] {tag} HRESULT 0x{hr:08x}  u32={p['u32']}  ptr={p['ptr']}")
        if p.get("outClass"): print(f"        返回对象 = {p['outClass']}")
        if p.get("asyncStatus") is not None: print(f"        AsyncStatus = {p['asyncStatus']}")
        if p.get("note"): print(f"        note = {p['note']}")
    elif e == "count":
        print(f"  已安装 AI 组件数 = {p['size']}   (hr=0x{p['hr']:08x})")
        if p.get("vecClass"): print(f"  vector 类名 = {p['vecClass']}")
    elif e == "item":
        print(f"    [{p['idx']}] {p['cls']}")
    elif e == "info":
        print("  ", p.get("msg"))
    elif e == "done":
        print("  ==> done")


def run(js, secs=10):
    session = frida.attach(PID)
    script = session.create_script(js)
    script.on("message", on_message)
    script.load()
    time.sleep(secs)
    session.detach()


def main():
    if PID is None:
        print("AI Dev Gallery 未运行")
        return 1
    mode = sys.argv[1] if len(sys.argv) > 1 else "state"
    print(f"==> 附加 pid={PID}  模式={mode}")
    if mode == "state":
        run(STATE_JS)
    elif mode == "comps":
        run(COMPS_JS)
    elif mode == "single":
        slot = int(sys.argv[2])
        cls = sys.argv[3] if len(sys.argv) > 3 else "Microsoft.Windows.AI.Text.LanguageModel"
        run(SINGLE_JS.replace("__SLOT__", str(slot)).replace("__CLASS__", json.dumps(cls)))
    else:
        print("未知模式")
    return 0


if __name__ == "__main__":
    sys.exit(main())
