#!/usr/bin/env python3
"""
trace_ensure.py — hook WinRT 激活，观察 EnsureReadyAsync 期间内部调用了什么

思路：EnsureReadyAsync 挂起说明它在等某个异步源。它一定在内部激活了
      某些组件（WU 客户端 / PackageManager / Workload 层 / StateRepository）。
      把这些激活记录出来，就能拼出调用链。
"""
import json
import sys
import time

import frida

TR_CLASS = "Microsoft.Windows.AI.Imaging.TextRecognizer"
TR_IID = "3788c2fd-e496-53ab-85a7-e54a135824e9"

PID = None
for p in frida.get_local_device().enumerate_processes():
    n = p.name.lower()
    if "aid" in n or "gallery" in n:
        PID = p.pid
        break

JS = r"""
'use strict';
var combase = Process.getModuleByName('combase.dll');
var API = {
  RoInitialize: new NativeFunction(combase.getExportByName('RoInitialize'), 'int', ['int'], 'win64'),
  CreateString: new NativeFunction(combase.getExportByName('WindowsCreateString'), 'int', ['pointer','uint','pointer'], 'win64'),
  DeleteString: new NativeFunction(combase.getExportByName('WindowsDeleteString'), 'int', ['pointer'], 'win64'),
  RawBuffer:    new NativeFunction(combase.getExportByName('WindowsGetStringRawBuffer'), 'pointer', ['pointer','pointer'], 'win64'),
  GetFactory:   new NativeFunction(combase.getExportByName('RoGetActivationFactory'), 'int', ['pointer','pointer','pointer'], 'win64')
};
function report(e,d){ send(Object.assign({event:e}, d||{})); }
function uuidBytes(s){var h=s.replace(/-/g,'');var b=[];for(var i=0;i<16;i++)b.push(parseInt(h.substr(i*2,2),16));
  return [b[3],b[2],b[1],b[0],b[5],b[4],b[7],b[6],b[8],b[9],b[10],b[11],b[12],b[13],b[14],b[15]];}
function slotOf(p,n){var vt=p.readPointer();return vt.add(n*Process.pointerSize).readPointer();}
function rcls(p){try{var fn=new NativeFunction(slotOf(p,4),'int',['pointer','pointer'],'win64');
  var h=Memory.alloc(8);h.writePointer(ptr(0));if(fn(p,h)<0||h.readPointer().isNull())return null;
  var len=Memory.alloc(4);len.writeU32(0);var b=API.RawBuffer(h.readPointer(),len);
  var s=b.readUtf16String(len.readU32());API.DeleteString(h.readPointer());return s;}catch(e){return null;}}
function hstrFrom(p, n){
  try{var fn=new NativeFunction(slotOf(p,n),'int',['pointer','pointer'],'win64');
    var o=Memory.alloc(8);o.writePointer(ptr(0)); if(fn(p,o)!==0)return null;
    var h=o.readPointer(); if(h.isNull())return null;
    var len=Memory.alloc(4);len.writeU32(0); var b=API.RawBuffer(h,len);
    var s=b.readUtf16String(len.readU32()); API.DeleteString(h); return s;}catch(e){return null;}}
function hs2s(h){ try{ if(h.isNull())return null; var len=Memory.alloc(4);len.writeU32(0);
  var b=API.RawBuffer(h,len); return b.readUtf16String(len.readU32()); }catch(e){ return null; } }

// ---------- 1) hook RoGetActivationFactory ----------
var ACTIVATIONS = [];
var logging = false;
var RGB = combase.getExportByName('RoGetActivationFactory');
Interceptor.attach(RGB, {
  onEnter: function(args){
    if (!logging) return;
    try { var s = hs2s(args[0]); if (s) ACTIVATIONS.push({kind:'GetActivationFactory', name:s}); } catch(e){}
  },
  onLeave: function(retval){}
});
var RAI = combase.getExportByName('RoActivateInstance');
Interceptor.attach(RAI, {
  onEnter: function(args){
    if (!logging) return;
    try { var s = hs2s(args[0]); if (s) ACTIVATIONS.push({kind:'ActivateInstance', name:s}); } catch(e){}
  }
});

function activate(cn, iidHex) {
  var h = Memory.alloc(8); h.writePointer(ptr(0));
  var s = Memory.allocUtf16String(cn);
  if (API.CreateString(s, cn.length, h) < 0) return null;
  var ib = iidHex ? uuidBytes(iidHex) : [0x35,0,0,0,0,0,0,0,0xc0,0,0,0,0,0,0,0x46];
  var im = Memory.alloc(16); im.writeByteArray(ib);
  var o = Memory.alloc(8); o.writePointer(ptr(0));
  var hr = API.GetFactory(h.readPointer(), im, o);
  API.DeleteString(h.readPointer());
  if (hr < 0) { report('activate-fail', {cls: cn, hr: hr & 0xffffffff}); return null; }
  return o.readPointer();
}

API.RoInitialize(1);

var f = activate(__TR__, null);
if (!f) { report('info',{msg:'TextRecognizer 激活失败'}); report('done',{}); }
else {
  report('info',{msg:'TextRecognizer factory OK'});
  // QI statics
  var qfn = new NativeFunction(f.readPointer().readPointer(),'int',['pointer','pointer','pointer'],'win64');
  var im2 = Memory.alloc(16); im2.writeByteArray(uuidBytes(__TRIID__));
  var o2 = Memory.alloc(8); o2.writePointer(ptr(0));
  var hrq = qfn(f, im2, o2);
  if (hrq !== 0) { report('info',{msg:'QI statics 失败'}); report('done',{}); }
  else {
    var iface = o2.readPointer();
    var f6 = new NativeFunction(slotOf(iface,6),'int',['pointer','pointer'],'win64');
    var o6 = Memory.alloc(4); o6.writeU32(0xffffffff);
    var hr6 = f6(iface, o6);
    report('ready', { hr: hr6 & 0xffffffff, state: o6.readU32() });

    // ---- 开始记录激活 ----
    ACTIVATIONS.length = 0;
    logging = true;

    var f7 = new NativeFunction(slotOf(iface,7),'int',['pointer','pointer'],'win64');
    var o7 = Memory.alloc(8); o7.writePointer(ptr(0));
    var hr7 = f7(iface, o7);
    var op = o7.readPointer();
    report('ensure-call', { hr: hr7 & 0xffffffff });

    var ticks = 0, MAXT = 300;   // 30s
    var reported = 0;
    function tick() {
      ticks++;
      if (!op.isNull()) {
        try {
          var g7 = new NativeFunction(slotOf(op,7),'int',['pointer','pointer'],'win64');
          var os = Memory.alloc(4); os.writeU32(0xffffffff);
          var hrS = g7(op, os);
          var st = os.readU32();
          if (hrS === 0 && st !== 0) { report('async-end',{status:st}); logging=false; flush(); return; }
        } catch(e){}
      }
      // 每 3 秒把新出现的激活报一次
      if (ticks % 30 === 0) {
        report('activations', { tick: ticks, list: ACTIVATIONS.slice(reported) });
        reported = ACTIVATIONS.length;
        report('progress', { tick: ticks });
      }
      if (ticks >= MAXT) { logging=false; report('timeout',{ticks:ticks}); flush(); return; }
      setTimeout(tick, 100);
    }
    function flush() {
      report('activations', { tick: ticks, list: ACTIVATIONS.slice(reported) });
      report('done', {});
    }
    tick();
  }
}
"""


def on_message(msg, data):
    if msg.get("type") != "send":
        if msg.get("type") == "error":
            print("  [script error]", msg.get("description"))
        return
    p = msg["payload"]; e = p.get("event")
    if e == "ready":
        print(f"  >>> GetReadyState   = {p['state']}")
    elif e == "ensure-call":
        print(f"  >>> EnsureReadyAsync hr=0x{p['hr']:08x}   开始记录内部激活...")
    elif e == "activations":
        lst = p.get("list") or []
        if not lst:
            print(f"      [{p['tick']*0.1:.0f}s] （无新激活）")
        for a in lst:
            print(f"      [{p['tick']*0.1:5.1f}s]  {a['kind']:22} {a['name']}")
    elif e == "async-end":
        print(f"  !!! 异步结束 status={p['status']}")
    elif e == "timeout":
        print(f"  !!! 30s 超时，仍未完成")
    elif e == "info":
        print("  ", p.get("msg"))
    elif e == "done":
        print("  ==> 结束")


def main():
    if PID is None:
        print("AI Dev Gallery 未运行")
        return 1
    js = (JS.replace("__TR__", json.dumps(TR_CLASS))
           .replace("__TRIID__", json.dumps(TR_IID)))
    print(f"==> 附加 pid={PID}")
    session = frida.attach(PID)
    script = session.create_script(js)
    script.on("message", on_message)
    script.load()
    time.sleep(45)
    session.detach()
    print("==> 完成")
    return 0


if __name__ == "__main__":
    sys.exit(main())
