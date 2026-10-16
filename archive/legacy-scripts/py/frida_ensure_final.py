#!/usr/bin/env python3
"""
frida_ensure_final.py — 正确等待 EnsureReadyAsync 完成，并观察是否发生下载

上一版的 bug：用 while(Date.now()...) 忙等，把 Frida 的 JS 线程堵死，
异步回调无法执行，所以从没观察到最终状态。

本版改用 setTimeout 做非阻塞轮询。

AIFeatureReadyState: 0=Ready 1=NotReady 2=NotSupportedOnCurrentSystem
                     3=DisabledByUser 4=CapabilityMissing
                     5=NotCompatibleWithSystemHardware 6=OSUpdateNeeded

用法: python frida_ensure_final.py [seconds]
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

TR_CLASS = "Microsoft.Windows.AI.Imaging.TextRecognizer"
TR_IID = "3788c2fd-e496-53ab-85a7-e54a135824e9"
STATE_NAMES = {0: "Ready", 1: "NotReady", 2: "NotSupportedOnCurrentSystem",
               3: "DisabledByUser", 4: "CapabilityMissing",
               5: "NotCompatibleWithSystemHardware", 6: "OSUpdateNeeded"}

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
  if (API.GetFactory(h.readPointer(), im, o) < 0) { API.DeleteString(h.readPointer()); return null; }
  API.DeleteString(h.readPointer());
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
    var fs = new NativeFunction(slotOf(ov.readPointer(), 7), 'int', ['pointer','pointer'], 'win64');
    var sz = Memory.alloc(4); sz.writeU32(0);
    if (fs(ov.readPointer(), sz) < 0) return -1;
    return sz.readU32();
  } catch (e) { return -2; }
}

var TARGET = __CLASS__, IID = __IID__;
var started = false;

function waitOp(op, tag, cb) {
  var n = 0;
  function poll() {
    var st = -1;
    try {
      var fs = new NativeFunction(slotOf(op, 11), 'int', ['pointer','pointer'], 'win64');
      var sp = Memory.alloc(4); sp.writeU32(0);
      if (fs(op, sp) >= 0) st = sp.readU32();
    } catch (e) { report('error', {stage:tag+'.status', msg:String(e)}); return; }
    if (n % 10 === 0) report('status', { tag: tag, n: n, status: st });
    if (st === 0 && n < 240) { n++; setTimeout(poll, 500); return; }
    report('final-status', { tag: tag, status: st, seconds: n * 0.5 });
    try {
      var fg = new NativeFunction(slotOf(op, 10), 'int', ['pointer','pointer'], 'win64');
      var og = Memory.alloc(8); og.writePointer(ptr(0));
      var hrg = fg(op, og);
      var res = og.readPointer();
      var info = { event:'result', tag: tag, hr: hrg & 0xffffffff, ptr: res.toString() };
      if (hrg >= 0 && !res.isNull()) {
        info.cls = rcls(res);
        for (var k = 6; k <= 9; k++) {
          try {
            var fk = new NativeFunction(slotOf(res, k), 'int', ['pointer','pointer'], 'win64');
            var okp = Memory.alloc(16); okp.writeByteArray([0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]);
            var hrk = fk(res, okp);
            if (hrk >= 0) info['res_slot'+k] = 'i32=' + okp.readU32() + ' ptr=' + okp.readPointer().toString();
          } catch (e) {}
        }
      }
      report('result', info);
    } catch (e) { report('error', {stage:tag+'.results', msg:String(e)}); }
    if (cb) cb();
  }
  setTimeout(poll, 500);
}

function doWork(factory) {
  if (started) return; started = true;
  try {
    report('before', { count: componentCount() });
    var qi = new NativeFunction(factory.readPointer().readPointer(), 'int', ['pointer','pointer','pointer'], 'win64');
    var im = Memory.alloc(16); im.writeByteArray(uuidBytes(IID));
    var o = Memory.alloc(8); o.writePointer(ptr(0));
    var hr = qi(factory, im, o);
    if (hr !== 0) { report('error', {stage:'qi', msg:'0x'+(hr>>>0).toString(16)}); return; }
    var iface = o.readPointer();

    var f6 = new NativeFunction(slotOf(iface, 6), 'int', ['pointer','pointer'], 'win64');
    var o6 = Memory.alloc(16); o6.writeByteArray([0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]);
    var hr6 = f6(iface, o6);
    report('ready', { state: o6.readU32(), hr: hr6 & 0xffffffff });

    var f7 = new NativeFunction(slotOf(iface, 7), 'int', ['pointer','pointer'], 'win64');
    var o7 = Memory.alloc(8); o7.writePointer(ptr(0));
    var hr7 = f7(iface, o7);
    var op = o7.readPointer();
    report('ensure', { hr: hr7 & 0xffffffff, cls: op.isNull()?null:rcls(op) });
    if (hr7 < 0 || op.isNull()) return;

    waitOp(op, 'EnsureReady', function () {
      report('after', { count: componentCount() });
    });
  } catch (e) { report('error', {stage:'work', msg:String(e)}); }
}

API.RoInitialize(1);
Interceptor.attach(combase.getExportByName('RoGetActivationFactory'), {
  onEnter: function (args) {
    this.outPtr = args[2]; this.cls = null;
    try { var len=Memory.alloc(4); len.writeU32(0); var b=API.RawBuffer(args[0],len);
          var n=len.readU32(); if(n>0&&n<200) this.cls=b.readUtf16String(n); } catch(e){}
  },
  onLeave: function (retval) {
    if (this.cls !== TARGET || retval.toInt32() < 0) return;
    report('caught', { cls: this.cls });
    try { var fac=this.outPtr.readPointer(); setTimeout(function(){ doWork(fac); }, 50); } catch(e){}
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
    elif e == "ready":
        st = p["state"]
        print(f"  >>> GetReadyState = {st}  ({STATE_NAMES.get(st,'?')})")
    elif e == "ensure": print(f"  >>> EnsureReadyAsync hr=0x{p['hr']:08x}\n      返回 = {p.get('cls')}")
    elif e == "status":
        if p["n"] % 20 == 0: print(f"      [status] {p['tag']} n={p['n']} -> {p['status']}")
    elif e == "final-status":
        print(f"  >>> 异步完成: status={p['status']}  用时 {p['seconds']}s  (1=Completed 3=Error)")
    elif e == "result":
        print(f"  >>> 结果 hr=0x{p['hr']:08x}  cls={p.get('cls')}")
        for k, v in p.items():
            if k.startswith("res_slot"): print(f"      {k} = {v}")
    elif e == "after": print(f"  >>> 调用后 已安装组件数 = {p['count']}")
    elif e == "info": print("  ", p.get("msg"))
    elif e == "error": print(f"  [err:{p.get('stage')}] {p.get('msg')}")


def main():
    if PID is None:
        print("AI Dev Gallery 未运行"); return 1
    secs = int(sys.argv[1]) if len(sys.argv) > 1 else 240
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
