#!/usr/bin/env python3
"""
frida_copilot_hook.py — 在目标进程内伪造 AICapabilities.HasAICapability 结果

原理（与已验证的资格 Hook 同源）：
  * hook RoGetActivationFactory
  * 当应用激活 Microsoft.Windows.AI.AICapabilities 时，拿到 factory
  * 用 IID 37968861-98ee-599c-aa38-aa79866d6ddc QueryInterface 出 IAICapabilitiesStatics
  * 在其 slot[6]（HasAICapability）上挂 Interceptor，强制把 BOOLEAN 输出改成 true
  * 保留原 HRESULT，不改其他类、不改失败调用

同时记录之后出现的 AI 类激活，便于观察是否触发模型下载。

用法: python frida_copilot_hook.py [pid] [seconds]
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

JS = r"""
'use strict';
var combase = Process.getModuleByName('combase.dll');
var API = {
  RoInitialize: new NativeFunction(combase.getExportByName('RoInitialize'), 'int', ['int'], 'win64'),
  CreateString: new NativeFunction(combase.getExportByName('WindowsCreateString'), 'int', ['pointer','uint','pointer'], 'win64'),
  DeleteString: new NativeFunction(combase.getExportByName('WindowsDeleteString'), 'int', ['pointer'], 'win64'),
  RawBuffer: new NativeFunction(combase.getExportByName('WindowsGetStringRawBuffer'), 'pointer', ['pointer','pointer'], 'win64'),
  GetFactory: new NativeFunction(combase.getExportByName('RoGetActivationFactory'), 'int', ['pointer','pointer','pointer'], 'win64')
};

var CAPS_CLASS = 'Microsoft.Windows.AI.AICapabilities';
var CAPS_IID = '37968861-98ee-599c-aa38-aa79866d6ddc';
var FORCE = __FORCE__;    // true => 强制返回 true

function report(e, d) { send(Object.assign({ event: e }, d || {})); }

function uuidBytes(s) {
  var h = s.replace(/-/g,''); var b = [];
  for (var i = 0; i < 16; i++) b.push(parseInt(h.substr(i*2,2),16));
  return [b[3],b[2],b[1],b[0], b[5],b[4], b[7],b[6], b[8],b[9],b[10],b[11],b[12],b[13],b[14],b[15]];
}

function guidStr(p) {
  try {
    var b = new Uint8Array(p.readByteArray(16));
    function h(x){ return ('0'+x.toString(16)).slice(-2); }
    return h(b[3])+h(b[2])+h(b[1])+h(b[0])+'-'+h(b[5])+h(b[4])+'-'+h(b[7])+h(b[6])+'-'
         + h(b[8])+h(b[9])+'-'+h(b[10])+h(b[11])+h(b[12])+h(b[13])+h(b[14])+h(b[15]);
  } catch (e) { return '?'; }
}

var hookedInterfaces = {};
var observed = {};

function hookCapabilityInterface(iface) {
  var key = iface.toString();
  if (hookedInterfaces[key]) return;
  hookedInterfaces[key] = true;
  var table = iface.readPointer();
  var addr = table.add(6 * Process.pointerSize).readPointer();   // slot 6 = HasAICapability
  Interceptor.attach(addr, {
    onEnter: function (args) {
      this.cat = args[1].toInt32();
      this.out = args[2];
    },
    onLeave: function (retval) {
      var hr = retval.toInt32();
      var orig = null;
      if (hr >= 0 && this.out && !this.out.isNull()) {
        orig = this.out.readU8() !== 0;
        if (FORCE && !orig) {
          this.out.writeU8(1);
          report('flip', { category: this.cat, original: orig, modified: true, hr: hr });
          return;
        }
      }
      report('cap', { category: this.cat, original: orig, modified: orig, hr: hr });
    }
  });
  report('hooked', { interface: key, slot: 6 });
}

// 挂 RoGetActivationFactory
Interceptor.attach(combase.getExportByName('RoGetActivationFactory'), {
  onEnter: function (args) {
    this.hit = false;
    this.factoryPtr = null;
    try {
      this.outPtr = args[2];                 // factory 输出参数
      this.iidPtr = args[1];                 // ★ 应用请求的 IID
      var len = Memory.alloc(4); len.writeU32(0);
      var buf = API.RawBuffer(args[0], len);
      var n = len.readU32();
      if (n > 0 && n < 200) { this.cls = buf.readUtf16String(n); this.hit = true; }
    } catch (e) {}
  },
  onLeave: function (retval) {
    if (!this.hit) return;
    var hr = retval.toInt32();
    if (hr < 0) return;

    var isAI = (this.cls.indexOf('AI') >= 0 || this.cls.indexOf('Vision') >= 0 ||
                this.cls.indexOf('SemanticSearch') >= 0 || this.cls.indexOf('Workloads') >= 0);
    if (isAI) {
      // ★ 记录类名 + 应用请求的 IID
      var iid = this.iidPtr ? guidStr(this.iidPtr) : '?';
      report('activated', { cls: this.cls, iid: iid, factory: this.outPtr && !this.outPtr.isNull() ? this.outPtr.readPointer().toString() : '' });
      if (!observed[this.cls]) observed[this.cls] = 0;
      observed[this.cls]++;
    }

    if (this.cls !== CAPS_CLASS) return;
    try {
      if (!this.outPtr || this.outPtr.isNull()) return;
      var fac = this.outPtr.readPointer();
      if (fac.isNull()) return;
      var qi = new NativeFunction(fac.readPointer().readPointer(), 'int', ['pointer','pointer','pointer'], 'win64');
      var im = Memory.alloc(16); im.writeByteArray(uuidBytes(CAPS_IID));
      var o = Memory.alloc(8); o.writePointer(ptr(0));
      var hr2 = qi(fac, im, o);
      report('qi', { iid: CAPS_IID, hr: hr2, ok: hr2 === 0 });
      if (hr2 === 0 && !o.readPointer().isNull()) hookCapabilityInterface(o.readPointer());
    } catch (e) { report('error', { stage: 'qi', msg: String(e) }); }
  }
});

report('info', { msg: 'RoGetActivationFactory 已挂载，等待 AICapabilities 激活' });
"""


def on_message(msg, data):
    if msg.get("type") != "send":
        if msg.get("type") == "error":
            print("  [script error]", msg.get("description"))
        return
    p = msg["payload"]; e = p.get("event")
    if e == "flip":
        print(f"  *** 翻转 category={p['category']}  {p['original']} -> true  (hr=0x{p['hr'] & 0xffffffff:08x})")
    elif e == "cap":
        print(f"      cap category={p['category']} 原值={p['original']} hr=0x{p['hr'] & 0xffffffff:08x}")
    elif e == "hooked":
        print(f"  [hook] 已挂 HasAICapability  (iface {p['interface']}, slot {p['slot']})")
    elif e == "activated":
        print(f"  [activate] {p['cls']}")
        print(f"             IID = {p['iid']}   factory = {p.get('factory','')}")
    elif e == "qi":
        print(f"  [QI] {p['iid']} -> 0x{p['hr'] & 0xffffffff:08x} ok={p['ok']}")
    elif e == "info":
        print("  ", p.get("msg"))
    elif e == "error":
        print("  [err]", p.get("stage"), p.get("msg"))


def main():
    if PID is None:
        print("AI Dev Gallery 未运行"); return 1
    secs = int(sys.argv[2]) if len(sys.argv) > 2 else 60
    force = True
    print(f"==> 附加 pid={PID}，强制 HasAICapability={force}，监听 {secs}s")
    session = frida.attach(PID)
    script = session.create_script(JS.replace("__FORCE__", "true" if force else "false"))
    script.on("message", on_message)
    script.load()
    time.sleep(secs)
    session.detach()
    print("==> 结束")
    return 0


if __name__ == "__main__":
    sys.exit(main())
