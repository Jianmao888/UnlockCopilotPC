#!/usr/bin/env python3
"""
hook_npudetect2.py - catch NPUDetect.dll being loaded, then hook its exports,
while the AI API call is triggered so the NPU detection actually happens.
"""
import json
import sys
import time

import frida

TR_CLASS = "Microsoft.Windows.AI.Imaging.TextRecognizer"
TR_IID = "3788c2fd-e496-53ab-85a7-e54a135824e9"

EXPORTS = ["npudetect_detect_npu", "npudetect_detect_npugeneration",
           "npudetect_get_driverversion", "npudetect_get_version"]

JS = r"""
'use strict';
function report(e, d){ send(Object.assign({event:e}, d||{})); }
var EXPORTS = __EXPORTS__;
var hooked = {};

function hookModule(m) {
  if (hooked[m.base.toString()]) return;
  hooked[m.base.toString()] = true;
  report('info', { msg: 'NPUDetect LOADED: ' + m.path + '  base=0x' + m.base + ' size=' + m.size });
  var n = {};
  EXPORTS.forEach(function(name){
    var addr = null;
    try { addr = m.getExportByName(name); } catch(e) { addr = null; }
    if (!addr) { report('info', { msg: '  no export ' + name }); return; }
    n[name] = 0;
    Interceptor.attach(addr, {
      onEnter: function(args){
        this.t = Date.now();
        this.args = [args[0], args[1], args[2], args[3]];
        this.seq = n[name]++;
      },
      onLeave: function(retval){
        report('call', {
          fn: name, seq: this.seq,
          retval: retval.toString(), ret_i32: retval.toInt32(),
          args: this.args.map(function(a){ return a.toString(); }),
          ms: Date.now() - this.t
        });
      }
    });
    report('info', { msg: '  hooked ' + name + ' @ ' + addr });
  });
}

// scan existing modules
Process.enumerateModules().forEach(function(m){
  if (/NPUDetect\.dll$/i.test(m.name)) hookModule(m);
});
report('info', { msg: 'initial scan done; NPUDetect already loaded = ' + Object.keys(hooked).length });

// hook LdrLoadDll to catch later loads
try {
  var ntdll = Process.getModuleByName('ntdll.dll');
  var ldr = ntdll.getExportByName('LdrLoadDll');
  Interceptor.attach(ldr, {
    onEnter: function(args){
      try {
        var us = args[2];
        var len = us.readU16();
        var buf = us.add(Process.pointerSize === 8 ? 8 : 4).readPointer();
        var name = buf.readUtf16String(len / 2);
        if (/NPUDetect/i.test(name)) {
          report('info', { msg: 'LdrLoadDll -> ' + name });
          this.want = name;
        }
      } catch(e) {}
    },
    onLeave: function(retval){
      if (!this.want) return;
      // module may now be present
      Process.enumerateModules().forEach(function(m){
        if (/NPUDetect\.dll$/i.test(m.name)) hookModule(m);
      });
    }
  });
  report('info', { msg: 'hooked LdrLoadDll' });
} catch(e) { report('info', { msg: 'LdrLoadDll hook failed: ' + e }); }

// also hook LoadLibraryExW as fallback
try {
  var k32 = Process.getModuleByName('kernel32.dll');
  var lle = k32.getExportByName('LoadLibraryExW');
  Interceptor.attach(lle, {
    onEnter: function(args){
      try {
        var s = args[0].readUtf16String();
        if (s && /NPUDetect/i.test(s)) { report('info', { msg: 'LoadLibraryExW -> ' + s }); this.want = true; }
      } catch(e) {}
    },
    onLeave: function(retval){
      if (!this.want) return;
      Process.enumerateModules().forEach(function(m){
        if (/NPUDetect\.dll$/i.test(m.name)) hookModule(m);
      });
    }
  });
} catch(e) {}

// ---------- now trigger the AI call ----------
var combase = Process.getModuleByName('combase.dll');
var API = {
  RoInitialize: new NativeFunction(combase.getExportByName('RoInitialize'), 'int', ['int'], 'win64'),
  CreateString: new NativeFunction(combase.getExportByName('WindowsCreateString'), 'int', ['pointer','uint','pointer'], 'win64'),
  DeleteString: new NativeFunction(combase.getExportByName('WindowsDeleteString'), 'int', ['pointer'], 'win64'),
  GetFactory:   new NativeFunction(combase.getExportByName('RoGetActivationFactory'), 'int', ['pointer','pointer','pointer'], 'win64')
};
function uuidBytes(s){var h=s.replace(/-/g,'');var b=[];for(var i=0;i<16;i++)b.push(parseInt(h.substr(i*2,2),16));
  return [b[3],b[2],b[1],b[0],b[5],b[4],b[7],b[6],b[8],b[9],b[10],b[11],b[12],b[13],b[14],b[15]];}
function slotOf(p,n){var vt=p.readPointer();return vt.add(n*Process.pointerSize).readPointer();}

function activate(cn, iidHex) {
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

setTimeout(function(){
  API.RoInitialize(1);
  var f = activate(__TR__, null);
  if (!f) { report('info',{msg:'TextRecognizer 激活失败'}); report('done',{}); return; }
  var q = new NativeFunction(f.readPointer().readPointer(),'int',['pointer','pointer','pointer'],'win64');
  var im = Memory.alloc(16); im.writeByteArray(uuidBytes(__TRIID__));
  var o = Memory.alloc(8); o.writePointer(ptr(0));
  if (q(f, im, o) !== 0) { report('info',{msg:'QI 失败'}); report('done',{}); return; }
  var iface = o.readPointer();
  var f6 = new NativeFunction(slotOf(iface,6),'int',['pointer','pointer'],'win64');
  var ob = Memory.alloc(4); ob.writeU32(0xffffffff);
  var hr = f6(iface, ob);
  report('ready', { hr: hr & 0xffffffff, state: ob.readU32() });
  // then EnsureReadyAsync to provoke the workload path
  var f7 = new NativeFunction(slotOf(iface,7),'int',['pointer','pointer'],'win64');
  var o7 = Memory.alloc(8); o7.writePointer(ptr(0));
  var hr7 = f7(iface, o7);
  report('ensure', { hr: hr7 & 0xffffffff });
  setTimeout(function(){
    Process.enumerateModules().forEach(function(m){
      if (/NPUDetect\.dll$/i.test(m.name)) hookModule(m);
    });
    report('info', { msg: 'final check done' });
    report('done', {});
  }, 12000);
}, 1500);
"""


def on_msg(label, msg, data):
    if msg.get("type") != "send":
        if msg.get("type") == "error":
            print(f"  [{label}] script error: {msg.get('description')}")
        return
    p = msg["payload"]
    e = p.get("event")
    if e == "info":
        print(f"  [{label}] {p.get('msg')}")
    elif e == "call":
        print(f"  [{label}] **** CALL {p['fn']}  seq={p['seq']}  ret={p['retval']} (i32={p['ret_i32']})  "
              f"args={p['args']}  {p['ms']}ms")
    elif e == "ready":
        print(f"  [{label}] GetReadyState = {p['state']}")
    elif e == "ensure":
        print(f"  [{label}] EnsureReadyAsync hr=0x{p['hr']:08x}")
    elif e == "done":
        print(f"  [{label}] --- finished ---")


def main():
    dev = frida.get_local_device()
    import subprocess
    ps = ("Get-Process svchost -EA SilentlyContinue | ForEach-Object { $p=$_; try { foreach($m in $p.Modules){ "
          "if($m.ModuleName -match 'wsaifabrichost'){ Write-Output ($p.Id) } } } catch {} }")
    out = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                         capture_output=True, text=True, encoding="utf-8", errors="replace")
    fab = [int(x) for x in (out.stdout or "").split() if x.strip().isdigit()]
    gal = [p.pid for p in dev.enumerate_processes() if "aid" in p.name.lower() or "gallery" in p.name.lower()]
    targets = [("WSAIFabricSvc", p) for p in fab] + [("AIDevGallery", p) for p in gal]
    print("targets:", targets)
    if not targets:
        return 1

    # only trigger the AI call in the gallery process (it has package identity)
    js_common = JS.replace("__EXPORTS__", json.dumps(EXPORTS))

    sessions = []
    for label, pid in targets:
        trigger = (label == "AIDevGallery")
        js = js_common.replace("__TR__", json.dumps(TR_CLASS)).replace("__TRIID__", json.dumps(TR_IID))
        if not trigger:
            # for the service, strip the trigger block: replace the setTimeout body with a no-op
            js = js.replace("setTimeout(function(){\n  API.RoInitialize(1);", "setTimeout(function(){ report('info',{msg:'no trigger in this process'}); return;\n  API.RoInitialize(1);")
        try:
            s = frida.attach(pid)
            sc = s.create_script(js)
            sc.on("message", lambda m, d, L=label: on_msg(L, m, d))
            sc.load()
            sessions.append((label, pid, s))
            print(f"attached {label} pid={pid} (trigger={trigger})")
        except Exception as e:
            print(f"attach {label}/{pid} failed: {e}")

    time.sleep(35)
    for label, pid, s in sessions:
        try:
            s.detach()
        except Exception:
            pass
    print("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
