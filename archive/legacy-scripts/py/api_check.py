#!/usr/bin/env python3
"""
api_check.py — 检验"Windows AI API 能不能用"

在 AI Dev Gallery 进程内（借用其包身份）：
  1. 激活 Microsoft.Windows.AI.Imaging.TextRecognizer
  2. QI 到 ITextRecognizerStatics
  3. 调 GetReadyState  →  AIFeatureReadyState
  4. 调 EnsureReadyAsync 看是否返回操作
同时激活 AICapabilities 看能力判断。

用法: python api_check.py
"""
import json
import sys
import time

import frida

TR_CLASS = "Microsoft.Windows.AI.Imaging.TextRecognizer"
TR_IID = "3788c2fd-e496-53ab-85a7-e54a135824e9"
SM_CLASS = "Microsoft.Windows.AI.Imaging.ImageScaler"
CAPS = "Microsoft.Windows.AI.AICapabilities"
CAPS_IID = "37968861-98ee-599c-aa38-aa79866d6ddc"

STATE = {0: "Ready", 1: "NotReady", 2: "NotSupportedOnCurrentSystem",
         3: "DisabledByUser", 4: "CapabilityMissing",
         5: "NotCompatibleWithSystemHardware", 6: "OSUpdateNeeded"}

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
function report(e,d){ send(Object.assign({event:e}, d||{})); }
function uuidBytes(s){var h=s.replace(/-/g,'');var b=[];for(var i=0;i<16;i++)b.push(parseInt(h.substr(i*2,2),16));
  return [b[3],b[2],b[1],b[0],b[5],b[4],b[7],b[6],b[8],b[9],b[10],b[11],b[12],b[13],b[14],b[15]];}
function slotOf(p,n){var vt=p.readPointer();return vt.add(n*Process.pointerSize).readPointer();}
function rcls(p){try{var fn=new NativeFunction(slotOf(p,4),'int',['pointer','pointer'],'win64');
  var h=Memory.alloc(8);h.writePointer(ptr(0));if(fn(p,h)<0||h.readPointer().isNull())return null;
  var len=Memory.alloc(4);len.writeU32(0);var b=API.RawBuffer(h.readPointer(),len);
  var s=b.readUtf16String(len.readU32());API.DeleteString(h.readPointer());return s;}catch(e){return null;}}

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

// 1) TextRecognizer.GetReadyState
var f = activate(__TR__, null);
if (!f) { report('info',{msg:'TextRecognizer 激活失败'}); }
else {
  report('info',{msg:'TextRecognizer factory OK'});
  var qi = new NativeFunction(f.readPointer().readPointer(),'int',['pointer','pointer','pointer'],'win64');
  var im = Memory.alloc(16); im.writeByteArray(uuidBytes(__TRIID__));
  var o = Memory.alloc(8); o.writePointer(ptr(0));
  var hr = qi(f, im, o);
  if (hr !== 0) report('info',{msg:'QI ITextRecognizerStatics 失败 0x'+(hr>>>0).toString(16)});
  else {
    var iface = o.readPointer();
    var f6 = new NativeFunction(slotOf(iface,6),'int',['pointer','pointer'],'win64');
    var o6 = Memory.alloc(16); o6.writeByteArray([0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]);
    var hr6 = f6(iface, o6);
    report('ready', { hr: hr6 & 0xffffffff, state: o6.readU32() });
    // EnsureReadyAsync
    try {
      var f7 = new NativeFunction(slotOf(iface,7),'int',['pointer','pointer'],'win64');
      var o7 = Memory.alloc(8); o7.writePointer(ptr(0));
      var hr7 = f7(iface, o7);
      var op = o7.readPointer();
      report('ensure', { hr: hr7 & 0xffffffff, cls: op.isNull()?null:rcls(op) });
    } catch (e) { report('info',{msg:'EnsureReady 异常 '+String(e)}); }
  }
}

// 2) AICapabilities.HasAICapability
var fc = activate(__CAPS__, null);
if (fc) {
  var qc = new NativeFunction(fc.readPointer().readPointer(),'int',['pointer','pointer','pointer'],'win64');
  var imc = Memory.alloc(16); imc.writeByteArray(uuidBytes(__CAPSIID__));
  var oc = Memory.alloc(8); oc.writePointer(ptr(0));
  if (qc(fc, imc, oc) === 0) {
    var ci = oc.readPointer();
    var f6c = new NativeFunction(slotOf(ci,6),'int',['pointer','int','pointer'],'win64');
    for (var k = 0; k < 6; k++) {
      var ob = Memory.alloc(4); ob.writeU8(0);
      var hrc = f6c(ci, k, ob);
      report('caps', { cat: k, hr: hrc & 0xffffffff, val: ob.readU8() });
    }
  } else report('info',{msg:'QI IAICapabilitiesStatics 失败'});
} else report('info',{msg:'AICapabilities 激活失败'});

// 3) ImageScaler.GetReadyState
var fs = activate(__SM__, null);
if (fs) {
  try {
    var f6s = new NativeFunction(slotOf(fs,6),'int',['pointer','pointer'],'win64');
    var o6s = Memory.alloc(16); o6s.writeByteArray([0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]);
    var hr6s = f6s(fs, o6s);
    report('ready2', { hr: hr6s & 0xffffffff, state: o6s.readU32() });
  } catch (e) { report('info',{msg:'ImageScaler 探测异常 '+String(e)}); }
}
report('done', {});
"""


def on_message(msg, data):
    if msg.get("type") != "send":
        if msg.get("type") == "error":
            print("  [script error]", msg.get("description"))
        return
    p = msg["payload"]; e = p.get("event")
    if e == "ready":
        st = p["state"]
        print(f"  >>> TextRecognizer.GetReadyState = {st}  ({STATE.get(st,'?')})   hr=0x{p['hr']:08x}")
    elif e == "ready2":
        st = p["state"]
        print(f"  >>> ImageScaler.GetReadyState    = {st}  ({STATE.get(st,'?')})   hr=0x{p['hr']:08x}")
    elif e == "ensure":
        print(f"  >>> EnsureReadyAsync hr=0x{p['hr']:08x}  -> {p.get('cls')}")
    elif e == "caps":
        print(f"      HasAICapability({p['cat']}) = {bool(p['val'])}  hr=0x{p['hr']:08x}")
    elif e == "activate-fail":
        print(f"  !!! 激活失败 {p['cls']} hr=0x{p['hr']:08x}")
    elif e == "info":
        print("  ", p.get("msg"))


def main():
    if PID is None:
        print("AI Dev Gallery 未运行")
        return 1
    js = (JS.replace("__TR__", json.dumps(TR_CLASS))
           .replace("__TRIID__", json.dumps(TR_IID))
           .replace("__CAPS__", json.dumps(CAPS))
           .replace("__CAPSIID__", json.dumps(CAPS_IID))
           .replace("__SM__", json.dumps(SM_CLASS)))
    print(f"==> 附加 pid={PID}")
    session = frida.attach(PID)
    script = session.create_script(js)
    script.on("message", on_message)
    script.load()
    time.sleep(12)
    session.detach()
    print("==> 完成")
    return 0


if __name__ == "__main__":
    sys.exit(main())
