#!/usr/bin/env python3
"""
frida_trigger_download.py — 在目标进程内调用 TextRecognizer 的就绪/下载流程

链路（全部在 AI Dev Gallery 进程内）：
  hook RoGetActivationFactory
  -> 捕获 Microsoft.Windows.AI.Imaging.TextRecognizer 的 factory
  -> QueryInterface(ITextRecognizerStatics)   IID 3788c2fd-e496-53ab-85a7-e54a135824e9
  -> slot[6] GetReadyState()       查状态
  -> slot[7] EnsureReadyAsync()    触发模型包下载
  -> 对比 AIComponentManager 的已安装组件数

用法: python frida_trigger_download.py [seconds]
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

TR_IID = "3788c2fd-e496-53ab-85a7-e54a135824e9"
TR_CLASS = "Microsoft.Windows.AI.Imaging.TextRecognizer"

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
function report(e,d){ send(Object.assign({event:e}, d||{})); }
function uuidBytes(s){var h=s.replace(/-/g,'');var b=[];for(var i=0;i<16;i++)b.push(parseInt(h.substr(i*2,2),16));
  return [b[3],b[2],b[1],b[0],b[5],b[4],b[7],b[6],b[8],b[9],b[10],b[11],b[12],b[13],b[14],b[15]];}
function slotOf(p,n){var vt=p.readPointer();return vt.add(n*Process.pointerSize).readPointer();}
function runtimeClass(p){try{var fn=new NativeFunction(slotOf(p,4),'int',['pointer','pointer'],'win64');
  var h=Memory.alloc(8);h.writePointer(ptr(0));if(fn(p,h)<0||h.readPointer().isNull())return null;
  var len=Memory.alloc(4);len.writeU32(0);var b=API.RawBuffer(h.readPointer(),len);
  var s=b.readUtf16String(len.readU32());API.DeleteString(h.readPointer());return s;}catch(e){return null;}}

var TARGET = __CLASS__, IID = __IID__;
var done = false;

function doWork(factory) {
  if (done) return; done = true;
  try {
    var fac = factory;
    var qi = new NativeFunction(fac.readPointer().readPointer(), 'int', ['pointer','pointer','pointer'], 'win64');
    var im = Memory.alloc(16); im.writeByteArray(uuidBytes(IID));
    var o = Memory.alloc(8); o.writePointer(ptr(0));
    var hr = qi(fac, im, o);
    report('qi', { hr: hr & 0xffffffff, ok: hr === 0 });
    if (hr !== 0) return;
    var iface = o.readPointer();
    // dump vtable
    var slots = [];
    for (var s = 6; s <= 14; s++) slots.push(slotOf(iface, s).toString());
    report('vt', { iface: iface.toString(), cls: runtimeClass(iface), slots: slots });

    // slot6 = GetReadyState（枚举输出，先按 int32 读）
    try {
      var f6 = new NativeFunction(slotOf(iface, 6), 'int', ['pointer','pointer'], 'win64');
      var o6 = Memory.alloc(16); o6.writeByteArray([0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]);
      var hr6 = f6(iface, o6);
      report('ready', { hr: hr6 & 0xffffffff, i32: o6.readU32(), ptr: o6.readPointer().toString() });
    } catch (e) { report('error', { stage: 'GetReadyState', msg: String(e) }); }

    // slot7 = EnsureReadyAsync
    try {
      var f7 = new NativeFunction(slotOf(iface, 7), 'int', ['pointer','pointer'], 'win64');
      var o7 = Memory.alloc(8); o7.writePointer(ptr(0));
      var hr7 = f7(iface, o7);
      var op = o7.readPointer();
      var info = { event:'ensure', hr: hr7 & 0xffffffff, op: op.toString() };
      if (hr7 >= 0 && !op.isNull()) info.opClass = runtimeClass(op);
      report('ensure', info);
    } catch (e) { report('error', { stage: 'EnsureReadyAsync', msg: String(e) }); }
  } catch (e) { report('error', { stage: 'work', msg: String(e) }); }
}

API.RoInitialize(1);
Interceptor.attach(combase.getExportByName('RoGetActivationFactory'), {
  onEnter: function (args) {
    this.outPtr = args[2]; this.cls = null;
    try {
      var len = Memory.alloc(4); len.writeU32(0);
      var buf = API.RawBuffer(args[0], len);
      var n = len.readU32();
      if (n > 0 && n < 200) this.cls = buf.readUtf16String(n);
    } catch (e) {}
  },
  onLeave: function (retval) {
    if (this.cls !== TARGET) return;
    if (retval.toInt32() < 0) return;
    report('caught', { cls: this.cls });
    try {
      var fac = this.outPtr.readPointer();
      setTimeout(function () { doWork(fac); }, 50);
    } catch (e) { report('error', { stage: 'caught', msg: String(e) }); }
  }
});
report('info', { msg: '等待应用激活 ' + TARGET });
"""


def on_message(msg, data):
    if msg.get("type") != "send":
        if msg.get("type") == "error":
            print("  [script error]", msg.get("description"))
        return
    p = msg["payload"]; e = p.get("event")
    if e == "caught":
        print(f"\n  *** 捕获 {p['cls']} 的 factory")
    elif e == "qi":
        print(f"  QI ITextRecognizerStatics -> 0x{p['hr']:08x}  ok={p['ok']}")
    elif e == "vt":
        print(f"  接口 {p['iface']}  类名={p['cls']}")
        for i, a in enumerate(p["slots"]):
            print(f"     slot[{i+6:2}] = {a}")
    elif e == "ready":
        print(f"  >>> GetReadyState  HRESULT=0x{p['hr']:08x}  value(i32)={p['i32']}  ptr={p['ptr']}")
    elif e == "ensure":
        print(f"  >>> EnsureReadyAsync HRESULT=0x{p['hr']:08x}  op={p['op']}")
        if p.get("opClass"): print(f"      返回对象 = {p['opClass']}")
    elif e == "info":
        print("  ", p.get("msg"))
    elif e == "error":
        print(f"  [err:{p.get('stage')}] {p.get('msg')}")


def main():
    if PID is None:
        print("AI Dev Gallery 未运行"); return 1
    secs = int(sys.argv[1]) if len(sys.argv) > 1 else 120
    print(f"==> 附加 pid={PID}，等待 TextRecognizer 激活，监听 {secs}s")
    session = frida.attach(PID)
    js = JS.replace("__CLASS__", json.dumps(TR_CLASS)).replace("__IID__", json.dumps(TR_IID))
    script = session.create_script(js)
    script.on("message", on_message)
    script.load()
    time.sleep(secs)
    session.detach()
    print("==> 结束")
    return 0


if __name__ == "__main__":
    sys.exit(main())
