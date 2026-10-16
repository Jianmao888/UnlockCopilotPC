#!/usr/bin/env python3
"""
capture_wu.py — spawn 一个执行 WU 搜索的 PowerShell，并在其进程内 hook WinHTTP 抓 SOAP

背景：
  WU 日志显示 <<PROCESS>>: pwsh.exe —— WU 代理在发起搜索的进程内运行。
  所以 hook 该进程的 WinHttpSendRequest 就能拿到明文 SOAP。
"""
import json
import os
import sys
import time

import frida

HERE = os.path.dirname(os.path.abspath(__file__))
TRIGGER = os.path.join(HERE, "trigger_wu_search.ps1")
OUTDIR = os.path.join(HERE, "capture-wu")
os.makedirs(OUTDIR, exist_ok=True)

KW = ["SoftwareDistribution", "SyncUpdates", "ProductsParameters", "DeviceAttributes",
      "GetCookie", "ClientWebService", "CallerAttributes", "FilterAppCategoryIds",
      "TreatAppCategoryIdsAsInstalled", "SyncProductsParameters", "<Products"]

JS = r"""
'use strict';
var seq = 0, installed = false;
var KW = __KW__;
function report(e, d) { send(Object.assign({ event: e }, d || {})); }

function hook() {
  if (installed) return;
  var m;
  try { m = Process.getModuleByName('winhttp.dll'); } catch (e) { return; }
  installed = true;
  report('module-found', { base: m.base.toString() });

  var targets = [['WinHttpSendRequest', 3, 4], ['WinHttpWriteData', 1, 2]];
  for (var i = 0; i < targets.length; i++) {
    (function (name, bi, li) {
      var a;
      try { a = m.getExportByName(name); } catch (e) { return; }
      Interceptor.attach(a, {
        onEnter: function (args) {
          try {
            var len = args[li].toInt32();
            var p = args[bi];
            if (name === 'WinHttpSendRequest') {
              report('sendreq', { headers_len: args[2].toInt32(), opt_len: len, opt_null: p.isNull() });
            }
            if (len <= 0 || len > 8 * 1024 * 1024) return;
            if (p.isNull()) return;
            var text = p.readUtf8String(len);
            if (!text) return;
            var hit = false;
            for (var k = 0; k < KW.length; k++) { if (text.indexOf(KW[k]) >= 0) { hit = true; break; } }
            if (!hit) { report('other', { api: name, bytes: len, preview: text.slice(0, 140) }); return; }
            seq++;
            var fn = 'soap-' + ('000' + seq).slice(-3) + '.xml';
            var f = new File(__OUTDIR__ + '\\\\' + fn, 'w');
            f.write(text); f.close();
            report('capture', { api: name, seq: seq, bytes: len, file: fn, preview: text.slice(0, 220) });
          } catch (e) { report('error', { stage: name, message: String(e) }); }
        }
      });
      report('hook-installed', { api: name });
    })(targets[i][0], targets[i][1], targets[i][2]);
  }

  var t2 = [['WinHttpConnect', 1], ['WinHttpOpenRequest', 2]];
  for (var j = 0; j < t2.length; j++) {
    (function (n, idx) {
      try {
        Interceptor.attach(m.getExportByName(n), {
          onEnter: function (args) {
            try {
              var s = args[idx].isNull() ? '' : args[idx].readUtf16String();
              report(n === 'WinHttpConnect' ? 'connect' : 'open-request', { value: s });
            } catch (e) {}
          }
        });
      } catch (e) {}
    })(t2[j][0], t2[j][1]);
  }
}

hook();
try {
  Process.attachModuleObserver({ onAdded: function (m) { if (m.name.toLowerCase() === 'winhttp.dll') hook(); } });
  report('ready', {});
} catch (e) { report('error', { stage: 'observer', message: String(e) }); }
rpc.exports = { count: function () { return seq; } };
"""


def on_message(msg, data):
    if msg.get("type") != "send":
        if msg.get("type") == "error":
            print("  [script error]", msg.get("description"))
        return
    p = msg["payload"]; e = p.get("event")
    if e == "capture":
        print(f"  *** 捕获 #{p['seq']} [{p['api']}] {p['bytes']}B -> {p['file']}")
        print(f"      {p['preview']}")
    elif e == "hook-installed":
        print(f"  [hook] {p['api']}")
    elif e in ("connect", "open-request"):
        print(f"  [{e}] {p.get('value')}")
    elif e == "sendreq":
        print(f"  [sendreq] headers={p['headers_len']} opt_len={p['opt_len']}")
    elif e == "other":
        print(f"  [other] {p['api']} {p['bytes']}B: {p.get('preview','')[:110]}")
    elif e == "error":
        print(f"  [err:{p.get('stage')}] {p.get('message')}")
    elif e == "module-found":
        print(f"  [module] winhttp @ {p['base']}")


def main():
    ps = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32",
                      "WindowsPowerShell", "v1.0", "powershell.exe")
    argv = [ps, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", TRIGGER]
    print(f"==> spawn: {' '.join(argv)}")
    pid = frida.spawn(argv)
    session = frida.attach(pid)
    js = (JS.replace("__OUTDIR__", json.dumps(OUTDIR))
           .replace("__KW__", json.dumps(KW)))
    script = session.create_script(js)
    script.on("message", on_message)
    script.load()
    print(f"==> hook 就绪 (pid={pid})，恢复进程\n")
    frida.resume(pid)
    deadline = time.time() + 150
    while time.time() < deadline:
        time.sleep(2)
    try:
        print(f"\n==> 共捕获 {script.exports_sync.count()}")
    except Exception:
        pass
    try: session.detach()
    except Exception: pass
    files = sorted(f for f in os.listdir(OUTDIR) if f.startswith("soap-"))
    print(f"==> 文件 {len(files)} 个")
    return 0


if __name__ == "__main__":
    sys.exit(main())
