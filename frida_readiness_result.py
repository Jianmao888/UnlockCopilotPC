#!/usr/bin/env python3
"""
frida_readiness_result.py — 调用 EnsureReadyAsync，等待完成并读取结果；对比组件数

IAsyncOperationWithProgress<TResult, TProgress> vtable（x64 标准 WinRT）：
  6 put_Progress   7 get_Progress
  8 put_Completed  9 get_Completed
  10 GetResults    11 get_Status   12 get_ErrorCode  13 get_Id  14 Cancel  15 Close

AsyncStatus: 0=Started 1=Completed 2=Canceled 3=Error

用法: python frida_readiness_result.py [seconds]
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
MGMT = "Windows.AI.Management.Internal.AIComponentManager"

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
function rcls(p){try{var fn=new NativeFunction(slotOf(p,4),'int',['pointer','pointer'],'win64');
  var h=Memory.alloc(8);h.writePointer(ptr(0));if(fn(p,h)<0||h.readPointer().isNull())return null;
  var len=Memory.alloc(4);len.writeU32(0);var b=API.RawBuffer(h.readPointer(),len);
  var s=b.readUtf16String(len.readU32());API.DeleteString(h.readPointer());return s;}catch(e){return null;}}

function getFactory(cn, iidHex) {
  var h = Memory.alloc(8); h.writePointer(ptr(0));
  var s = Memory.allocUtf16String(cn);
  if (API.CreateString(s, cn.length, h) < 0) return null;
  var ib = iidHex ? uuidBytes(iidHex) : [0x35,0,0,0,0,0,0,0,0xc0,0,0,0,0,0,0,0x46];
  var im = Memory.alloc(16); im.writeByteArray(ib);
  var o = Memory.alloc(8); o.writePointer(ptr(0));
  var hr = API.GetFactory(h.readPointer(), im, o);
  API.DeleteString(h.readPointer());
  if (hr < 0) return null;
  return o.readPointer();
}

function componentCount() {
  try {
    var f = getFactory("Windows.AI.Management.Internal.AIComponentManager", null);
    if (!f) return -1;
    var f6 = new NativeFunction(slotOf(f, 6), 'int', ['pointer','pointer'], 'win64');
    var om = Memory.alloc(8); om.writePointer(ptr(0));
    if (f6(f, om) < 0) return -1;
    var mgr = om.readPointer();
    var fv = new NativeFunction(slotOf(mgr, 6), 'int', ['pointer','pointer'], 'win64');
    var ov = Memory.alloc(8); ov.writePointer(ptr(0));
    if (fv(mgr, ov) < 0) return -1;
    var vec = ov.readPointer();
    var fs = new NativeFunction(slotOf(vec, 7), 'int', ['pointer','pointer'], 'win64');
    var sz = Memory.alloc(4); sz.writeU32(0);
    if (fs(vec, sz) < 0) return -1;
    return sz.readU32();
  } catch (e) { return -2; }
}

var TARGET = __CLASS__, IID = __IID__;
var started = false;

function doWork(factory) {
  if (started) return; started = true;
  try {
    report('before', { count: componentCount() });
    var qi = new NativeFunction(factory.readPointer().readPointer(), 'int', ['pointer','pointer','pointer'], 'win64');
    var im = Memory.alloc(16); im.writeByteArray(uuidBytes(IID));
    var o = Memory.alloc(8); o.writePointer(ptr(0));
    var hr = qi(factory, im, o);
    if (hr !== 0) { report('error', { stage:'qi', msg:'0x'+ (hr>>>0).toString(16) }); return; }
    var iface = o.readPointer();

    var f6 = new NativeFunction(slotOf(iface, 6), 'int', ['pointer','pointer'], 'win64');
    var o6 = Memory.alloc(16); o6.writeByteArray([0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]);
    var hr6 = f6(iface, o6);
    report('ready', { hr: hr6 & 0xffffffff, state: o6.readU32() });

    var f7 = new NativeFunction(slotOf(iface, 7), 'int', ['pointer','pointer'], 'win64');
    var o7 = Memory.alloc(8); o7.writePointer(ptr(0));
    var hr7 = f7(iface, o7);
    var op = o7.readPointer();
    report('ensure', { hr: hr7 & 0xffffffff, cls: op.isNull()?null:rcls(op) });
    if (hr7 < 0 || op.isNull()) return;

    // 轮询 Status（slot 11），超时 120s
    var fd = Memory.alloc(8);
    var completed = false;
    for (var i = 0; i < 240; i++) {
      var st32 = -1;
      try {
        var fs = new NativeFunction(slotOf(op, 11), 'int', ['pointer','pointer'], 'win64');
        var sp = Memory.alloc(4); sp.writeU32(0);
        if (fs(op, sp) >= 0) st32 = sp.readU32();
      } catch (e) { report('error', { stage:'status', msg:String(e) }); break; }
      if (i % 20 === 0) report('status', { i: i, status: st32 });
      if (st32 !== 0) { report('status-final', { status: st32 }); completed = true; break; }
      // 忙等（Frida 里不能用 sleep 阻塞事件循环太久，这里用短循环）
      var t = Date.now(); while (Date.now() - t < 500) {}
    }
    // 读结果（slot 10）
    try {
      var fg = new NativeFunction(slotOf(op, 10), 'int', ['pointer','pointer'], 'win64');
      var og = Memory.alloc(8); og.writePointer(ptr(0));
      var hrg = fg(op, og);
      var res = og.readPointer();
      var info = { event:'result', hr: hrg & 0xffffffff, ptr: res.toString() };
      if (hrg >= 0 && !res.isNull()) {
        info.cls = rcls(res);
        // AIFeatureReadyResult 的 get_State / get_Status 之类，试 slot 6/7
        for (var k = 6; k <= 9; k++) {
          try {
            var fk = new NativeFunction(slotOf(res, k), 'int', ['pointer','pointer'], 'win64');
            var okp = Memory.alloc(8); okp.writePointer(ptr(0));
            var hrk = fk(res, okp);
            if (hrk >= 0) info['slot' + k] = okp.readPointer().toString() + ' / i32=' + okp.readU32();
          } catch (e) {}
        }
      }
      report('result', info);
    } catch (e) { report('error', { stage:'getresults', msg:String(e) }); }

    report('after', { count: componentCount(), completed: completed });
  } catch (e) { report('error', { stage:'work', msg:String(e) }); }
}

API.RoInitialize(1);
Interceptor.attach(combase.getExportByName('RoGetActivationFactory'), {
  onEnter: function (args) {
    this.outPtr = args[2]; this.cls = null;
    try { var len=Memory.alloc(4); len.writeU32(0); var buf=API.RawBuffer(args[0], len);
          var n=len.readU32(); if(n>0&&n<200) this.cls=buf.readUtf16String(n); } catch(e){}
  },
  onLeave: function (retval) {
    if (this.cls !== TARGET || retval.toInt32() < 0) return;
    report('caught', { cls: this.cls });
    try { var fac = this.outPtr.readPointer(); setTimeout(function(){ doWork(fac); }, 50); } catch(e){}
  }
});
report('info', { msg: '等待 ' + TARGET });
"""


def on_message(msg, data):
    if msg.get("type") != "send":
        if msg.get("type") == "error":
            print("  [script error]", msg.get("description"))
        return
    p = msg["payload"]; e = p.get("event")
    if e == "caught": print(f"\n  *** 捕获 {p['cls']}")
    elif e == "before": print(f"  >>> 调用前 已安装组件数 = {p['count']}")
    elif e == "ready": print(f"  >>> GetReadyState = {p['state']}   (hr=0x{p['hr']:08x})")
    elif e == "ensure": print(f"  >>> EnsureReadyAsync hr=0x{p['hr']:08x}  op={p.get('cls')}")
    elif e == "status": print(f"      status[{p['i']}] = {p['status']}")
    elif e == "status-final": print(f"  >>> 异步完成, 最终 status = {p['status']}  (0=Started 1=Completed 2=Canceled 3=Error)")
    elif e == "result":
        print(f"  >>> 结果对象 hr=0x{p['hr']:08x} ptr={p['ptr']}")
        if p.get("cls"): print(f"      cls = {p['cls']}")
        for k, v in p.items():
            if k.startswith("slot"): print(f"      {k} = {v}")
    elif e == "after": print(f"  >>> 调用后 已安装组件数 = {p['count']}   (completed={p['completed']})")
    elif e == "info": print("  ", p.get("msg"))
    elif e == "error": print(f"  [err:{p.get('stage')}] {p.get('msg')}")


def main():
    if PID is None:
        print("AI Dev Gallery 未运行"); return 1
    secs = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    print(f"==> 附加 pid={PID}，监听 {secs}s")
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
