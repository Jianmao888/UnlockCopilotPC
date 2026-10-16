#!/usr/bin/env python3
"""
ensure_ready_probe.py — 正确 await EnsureReadyAsync 并读取 AIFeatureReadyResult

官方用法：
    var st = TextRecognizer.GetReadyState();
    if (st == NotReady) {
        var r = await TextRecognizer.EnsureReadyAsync();
        if (r.Status != Success) throw r.ExtendedError;      // ← 我们要这个
    }

IAsyncOperationWithProgress<TResult,TProgress> 扁平 vtable：
    6 get_Id | 7 get_Status | 8 get_ErrorCode | 9 Cancel | 10 Close
    11 put_Completed | 12 get_Completed | 13 GetResults
    14 put_Progress | 15 get_Progress
"""
import json
import sys
import time

import frida

TR_CLASS = "Microsoft.Windows.AI.Imaging.TextRecognizer"
TR_IID = "3788c2fd-e496-53ab-85a7-e54a135824e9"
IID_ASYNCINFO = "00000036-0000-0000-c000-000000000046"

STATE = {0: "Ready", 1: "NotReady", 2: "NotSupportedOnCurrentSystem",
         3: "DisabledByUser", 4: "CapabilityMissing",
         5: "NotCompatibleWithSystemHardware", 6: "OSUpdateNeeded"}
ASYNC = {0: "Started", 1: "Completed", 2: "Canceled", 3: "Error"}

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
function qi(p, iidHex){
  var fn = new NativeFunction(p.readPointer().readPointer(),'int',['pointer','pointer','pointer'],'win64');
  var im = Memory.alloc(16); im.writeByteArray(uuidBytes(iidHex));
  var o = Memory.alloc(8); o.writePointer(ptr(0));
  var hr = fn(p, im, o);
  return (hr === 0) ? o.readPointer() : null;
}
function rcls(p){try{var fn=new NativeFunction(slotOf(p,4),'int',['pointer','pointer'],'win64');
  var h=Memory.alloc(8);h.writePointer(ptr(0));if(fn(p,h)<0||h.readPointer().isNull())return null;
  var len=Memory.alloc(4);len.writeU32(0);var b=API.RawBuffer(h.readPointer(),len);
  var s=b.readUtf16String(len.readU32());API.DeleteString(h.readPointer());return s;}catch(e){return null;}}
function hstrFrom(p, n){
  try{
    var fn = new NativeFunction(slotOf(p,n),'int',['pointer','pointer'],'win64');
    var o = Memory.alloc(8); o.writePointer(ptr(0));
    if (fn(p,o) !== 0) return null;
    var h = o.readPointer(); if (h.isNull()) return null;
    var len = Memory.alloc(4); len.writeU32(0);
    var b = API.RawBuffer(h,len);
    var s = b.readUtf16String(len.readU32());
    API.DeleteString(h);
    return s;
  }catch(e){return null;}
}
function u32From(p,n){try{var fn=new NativeFunction(slotOf(p,n),'int',['pointer','pointer'],'win64');
  var o=Memory.alloc(4);o.writeU32(0);if(fn(p,o)!==0)return null;return o.readU32();}catch(e){return null;}}
function u8From(p,n){try{var fn=new NativeFunction(slotOf(p,n),'int',['pointer','pointer'],'win64');
  var o=Memory.alloc(2);o.writeU16(0);if(fn(p,o)!==0)return null;return o.readU8();}catch(e){return null;}}
function i32From(p,n){try{var fn=new NativeFunction(slotOf(p,n),'int',['pointer','pointer'],'win64');
  var o=Memory.alloc(4);o.writeS32(0);if(fn(p,o)!==0)return null;return o.readS32();}catch(e){return null;}}

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
  report('info',{msg:'TextRecognizer factory OK  class=' + rcls(f)});
  var iface = qi(f, __TRIID__);
  if (!iface) { report('info',{msg:'QI ITextRecognizerStatics 失败'}); report('done',{}); }
  else {
    // ---- GetReadyState (slot 6) ----
    var f6 = new NativeFunction(slotOf(iface,6),'int',['pointer','pointer'],'win64');
    var o6 = Memory.alloc(4); o6.writeU32(0xffffffff);
    var hr6 = f6(iface, o6);
    report('ready', { hr: hr6 & 0xffffffff, state: o6.readU32() });

    // ---- EnsureReadyAsync (slot 7) ----
    var f7 = new NativeFunction(slotOf(iface,7),'int',['pointer','pointer'],'win64');
    var o7 = Memory.alloc(8); o7.writePointer(ptr(0));
    var hr7 = f7(iface, o7);
    var op = o7.readPointer();
    report('ensure-call', { hr: hr7 & 0xffffffff, cls: op.isNull()?null:rcls(op) });
    if (hr7 !== 0 || op.isNull()) { report('done',{}); }
    else {
      var ticks = 0;
      var MAXT = 900;   // 900 * 100ms = 90s
      function tick() {
        ticks++;
        var g7 = new NativeFunction(slotOf(op,7),'int',['pointer','pointer'],'win64');
        var os = Memory.alloc(4); os.writeU32(0xffffffff);
        var hrS = g7(op, os);
        var st = os.readU32();
        if (hrS === 0 && st === 1) { finish(); return; }
        if (hrS === 0 && (st === 2 || st === 3)) { report('async-end',{status:st}); finish(); return; }
        if (ticks >= MAXT) { report('async-timeout',{ticks:ticks,last:st}); finish(); return; }
        if (ticks % 20 === 0) report('async-progress',{ticks:ticks,status:st});
        setTimeout(tick, 100);
      }
      function finish() {
        // GetResults (slot 13)
        try {
          var g13 = new NativeFunction(slotOf(op,13),'int',['pointer','pointer'],'win64');
          var orr = Memory.alloc(8); orr.writePointer(ptr(0));
          var hrG = g13(op, orr);
          var res = orr.readPointer();
          report('results', { hr: hrG & 0xffffffff, cls: res.isNull()?null:rcls(res) });
          if (!res.isNull()) {
            var dump = {};
            for (var s = 6; s <= 14; s++) {
              var a = hstrFrom(res, s); if (a !== null) dump['hstr_'+s] = a;
              var b = u32From(res, s);  if (b !== null) dump['u32_'+s]  = b;
              var c = u8From(res, s);   if (c !== null) dump['u8_'+s]   = c;
              var d = i32From(res, s);  if (d !== null) dump['i32_'+s]  = d;
            }
            report('result-dump', { dump: dump });
          }
        } catch (e) { report('info',{msg:'GetResults 异常 '+String(e)}); }
        // 复查 ready state
        try {
          var o6b = Memory.alloc(4); o6b.writeU32(0xffffffff);
          var hr6b = f6(iface, o6b);
          report('ready-after', { hr: hr6b & 0xffffffff, state: o6b.readU32() });
        } catch (e) {}
        report('done', {});
      }
      tick();
    }
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
        st = p["state"]
        print(f"  >>> GetReadyState      = {st} ({STATE.get(st,'?')})   hr=0x{p['hr']:08x}")
    elif e == "ready-after":
        st = p["state"]
        print(f"  >>> GetReadyState(后)  = {st} ({STATE.get(st,'?')})   hr=0x{p['hr']:08x}")
    elif e == "ensure-call":
        print(f"  >>> EnsureReadyAsync   hr=0x{p['hr']:08x}  -> {p.get('cls')}")
    elif e == "async-progress":
        print(f"      ...等待中 {p['ticks']*0.1:.0f}s  status={p['status']} ({ASYNC.get(p['status'],'?')})")
    elif e == "async-end":
        print(f"  !!! 异步以非完成状态结束: {p['status']} ({ASYNC.get(p['status'],'?')})")
    elif e == "async-timeout":
        print(f"  !!! 超时（{p['ticks']*0.1:.0f}s），最后状态={p['last']}")
    elif e == "results":
        print(f"  >>> GetResults         hr=0x{p['hr']:08x}  -> {p.get('cls')}")
    elif e == "result-dump":
        d = p["dump"]
        print("  >>> AIFeatureReadyResult 成员逐槽探测:")
        for k in sorted(d.keys()):
            v = d[k]
            note = ""
            if k.startswith("hstr_"):
                note = "  ← 文本"
            if k in ("u32_6", "i32_6", "u32_7", "i32_7"):
                note = "  ← 可能是 Status/Error"
            print(f"        {k:10} = {v!r}{note}")
    elif e == "activate-fail":
        print(f"  !!! 激活失败 {p['cls']} hr=0x{p['hr']:08x}")
    elif e == "info":
        print("  ", p.get("msg"))


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
    # 等待 done 或超时
    deadline = time.time() + 120
    while time.time() < deadline:
        time.sleep(2)
    session.detach()
    print("==> 完成")
    return 0


if __name__ == "__main__":
    sys.exit(main())
