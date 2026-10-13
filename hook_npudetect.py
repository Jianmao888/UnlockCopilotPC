#!/usr/bin/env python3
"""
hook_npudetect.py - OBSERVE npudetect_* calls in the AI workload processes.
No modification yet: just log who is called, with what args, and what it returns.
Targets: WSAIFabricSvc (svchost with wsaifabrichost.dll) and any packaged app.
"""
import sys
import time

import frida

EXPORTS = [
    "npudetect_detect_npu",
    "npudetect_detect_npugeneration",
    "npudetect_get_driverversion",
    "npudetect_get_version",
]

JS = r"""
'use strict';
function report(e, d){ send(Object.assign({event:e}, d||{})); }

var targets = [];
Process.enumerateModules().forEach(function(m){
  if (/NPUDetect\.dll$/i.test(m.name)) targets.push(m);
});
report('info', { msg: 'process=' + Process.mainModule.name + ' pid=' + Process.id +
                      ' NPUDetect modules=' + targets.length });

targets.forEach(function(m){
  report('info', { msg: 'NPUDetect base=0x' + m.base + ' size=' + m.size + ' path=' + m.path });
  __EXPORTS__.forEach(function(name){
    var addr = null;
    try { addr = m.getExportByName(name); } catch(e) { addr = null; }
    if (!addr) { report('info', { msg: '  no export ' + name }); return; }
    var n = 0;
    Interceptor.attach(addr, {
      onEnter: function(args){
        this.t = Date.now();
        this.a0 = args[0]; this.a1 = args[1]; this.a2 = args[2]; this.a3 = args[3];
        this.cnt = (n++);
      },
      onLeave: function(retval){
        var dt = Date.now() - this.t;
        report('call', {
          fn: name,
          seq: this.cnt,
          retval: retval.toString(),
          ret_i32: retval.toInt32(),
          a0: this.a0.toString(), a1: this.a1.toString(),
          a2: this.a2.toString(), a3: this.a3.toString(),
          ms: dt
        });
      }
    });
    report('info', { msg: '  hooked ' + name + ' @ ' + addr });
  });
});
report('done', {});
"""


def find_target_pids():
    """Find svchost hosting WSAIFabricSvc, plus any packaged app."""
    pids = []
    dev = frida.get_local_device()
    # WSAIFabricSvc host
    try:
        for p in dev.enumerate_processes():
            if p.name.lower() == "svchost.exe":
                pids.append(("svchost?", p.pid, p.name))
    except Exception as e:
        print("enumerate failed:", e)
    return pids


def main():
    dev = frida.get_local_device()
    # first: find svchost that has wsaifabrichost.dll loaded
    import subprocess
    ps = (
        "Get-Process svchost -EA SilentlyContinue | ForEach-Object { "
        "$p=$_; try { foreach($m in $p.Modules){ if($m.ModuleName -match 'wsaifabrichost'){ "
        "Write-Output ($p.Id) } } } catch {} }"
    )
    out = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                         capture_output=True, text=True, encoding="utf-8", errors="replace")
    fab_pids = [int(x) for x in (out.stdout or "").split() if x.strip().isdigit()]
    print("WSAIFabricSvc host pids:", fab_pids)

    # plus AI Dev Gallery
    gal = [p.pid for p in dev.enumerate_processes() if "aid" in p.name.lower() or "gallery" in p.name.lower()]
    print("AI Dev Gallery pids:", gal)

    all_targets = []
    for pid in fab_pids:
        all_targets.append(("WSAIFabricSvc", pid))
    for pid in gal:
        all_targets.append(("AIDevGallery", pid))

    if not all_targets:
        print("no targets found")
        return 1

    js = JS.replace("__EXPORTS__", str(EXPORTS).replace("'", '"'))
    sessions = []
    for label, pid in all_targets:
        try:
            s = frida.attach(pid)
            sc = s.create_script(js)
            sc.on("message", lambda m, d, L=label: on_msg(L, m, d))
            sc.load()
            sessions.append((label, pid, s))
            print(f"attached {label} pid={pid}")
        except Exception as e:
            print(f"attach {label} pid={pid} failed: {e}")

    time.sleep(40)
    for label, pid, s in sessions:
        try:
            s.detach()
        except Exception:
            pass
    print("done")
    return 0


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
        print(f"  [{label}] CALL {p['fn']}  seq={p['seq']}  ret={p['retval']} (i32={p['ret_i32']})  "
              f"args=[{p['a0']}, {p['a1']}, {p['a2']}, {p['a3']}]  {p['ms']}ms")
    elif e == "done":
        print(f"  [{label}] --- script finished ---")


if __name__ == "__main__":
    sys.exit(main())
