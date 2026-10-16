#!/usr/bin/env python3
"""
hook_wu_svc.py — 附加到 Windows Update 服务进程，hook WinHttpSendRequest 抓 SOAP

需要管理员权限（目标进程是 SYSTEM）。
用法：
  python hook_wu_svc.py [PID]
若不给 PID，自动查找承载 wuauserv 的 svchost。
"""
import json
import os
import sys
import time

import frida

HERE = os.path.dirname(os.path.abspath(__file__))
OUTDIR = os.path.join(HERE, "capture-svc")
os.makedirs(OUTDIR, exist_ok=True)

KEYWORDS = ["SoftwareDistribution", "SyncUpdates", "ProductsParameters",
            "DeviceAttributes", "GetCookie", "ClientWebService", "CallerAttributes"]

JS = r"""
'use strict';
var seq = 0;
var installed = false;
var KW = ["SoftwareDistribution", "SyncUpdates", "ProductsParameters",
          "DeviceAttributes", "GetCookie", "ClientWebService", "CallerAttributes",
          "TreatAppCategoryIdsAsInstalled", "<Products", "FilterAppCategoryIds"];

function report(e, d) { send(Object.assign({ event: e }, d || {})); }

function hook() {
  if (installed) return;
  var m;
  try { m = Process.getModuleByName('winhttp.dll'); } catch (e) { return; }
  installed = true;
  report('module-found', { name: 'winhttp.dll', base: m.base.toString() });

  var targets = [['WinHttpSendRequest', 3, 4], ['WinHttpWriteData', 1, 2]];
  for (var i = 0; i < targets.length; i++) {
    var name = targets[i][0], bi = targets[i][1], li = targets[i][2];
    var a;
    try { a = m.getExportByName(name); } catch (e) { continue; }
    Interceptor.attach(a, {
      onEnter: function (args) {
        try {
          var len = args[li].toInt32();
          var p = args[bi];
          if (name === 'WinHttpSendRequest') {
            report('sendreq', {
              headers_len: args[2].toInt32(),
              opt_len: len,
              opt_null: p.isNull()
            });
          } else {
            report('writedata', { len: len, null: p.isNull() });
          }
          if (len <= 0 || len > 8 * 1024 * 1024) return;
          if (p.isNull()) return;
          var text = p.readUtf8String(len);
          if (!text) { report('empty-body', { api: name, len: len }); return; }
          var hit = false;
          for (var k = 0; k < KW.length; k++) { if (text.indexOf(KW[k]) >= 0) { hit = true; break; } }
          if (!hit) { report('other', { api: name, bytes: len, preview: text.slice(0, 150) }); return; }
          seq++;
          var fn = 'soap-' + ('000' + seq).slice(-3) + '.xml';
          var f = new File(__OUTDIR__ + '\\\\' + fn, 'w');
          f.write(text); f.close();
          report('capture', { api: name, seq: seq, bytes: len, file: fn, preview: text.slice(0, 200) });
        } catch (e) { report('error', { stage: name, message: String(e) }); }
      }
    });
    report('hook-installed', { api: name });
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
  Process.attachModuleObserver({
    onAdded: function (m) { if (m.name.toLowerCase() === 'winhttp.dll') hook(); }
  });
} catch (e) { report('error', { stage: 'observer', message: String(e) }); }

rpc.exports = { count: function () { return seq; } };
"""


def find_pid():
    import subprocess
    out = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         "(Get-CimInstance Win32_Service -Filter \"Name='wuauserv'\").ProcessId"],
        capture_output=True, text=True)
    for line in out.stdout.splitlines():
        line = line.strip()
        if line.isdigit():
            return int(line)
    return None


def on_message(msg, data):
    if msg.get("type") != "send":
        if msg.get("type") == "error":
            print("  [script error]", msg.get("description"))
        return
    p = msg["payload"]
    e = p.get("event")
    if e == "capture":
        print(f"  *** 捕获 #{p['seq']} [{p['api']}] {p['bytes']}B -> {p['file']}")
        print(f"      {p['preview']}")
    elif e == "hook-installed":
        print(f"  [hook] {p['api']}")
    elif e == "module-found":
        print(f"  [module] {p['name']} @ {p['base']}")
    elif e == "other":
        print(f"  [other] {p['api']} {p['bytes']}B: {p.get('preview','')[:90]}")
    elif e == "sendreq":
        print(f"  [sendreq] headers={p['headers_len']} opt_len={p['opt_len']} opt_null={p['opt_null']}")
    elif e == "writedata":
        print(f"  [writedata] len={p['len']} null={p['null']}")
    elif e == "empty-body":
        print(f"  [empty-body] {p['api']} len={p['len']}")
    elif e in ("connect", "open-request"):
        print(f"  [{e}] {p.get('value')}")
    elif e == "error":
        print(f"  [err:{p.get('stage')}] {p.get('message')}")


def main():
    explicit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    session = None
    pid = None
    for attempt in range(1, 31):
        pid = explicit if explicit else find_pid()
        if not pid:
            print(f"  [{attempt}] 找不到 wuauserv，2 秒后重试")
            time.sleep(2)
            continue
        try:
            print(f"  [{attempt}] 尝试附加到 PID {pid} ...")
            session = frida.attach(pid)
            print(f"  [{attempt}] 附加成功")
            break
        except Exception as e:
            print(f"  [{attempt}] 附加失败: {str(e)[:120]}")
            time.sleep(3)
    if session is None:
        print("多次附加均失败")
        return 1

    js = JS.replace("__OUTDIR__", json.dumps(OUTDIR))
    script = session.create_script(js)
    script.on("message", on_message)
    script.load()
    print(f"==> hook 就绪 (PID {pid})，监听 180 秒")
    deadline = time.time() + 180
    while time.time() < deadline:
        time.sleep(2)
    try:
        n = script.exports_sync.count()
        print(f"==> 共捕获 {n} 个 SOAP")
    except Exception:
        pass
    session.detach()
    return 0


if __name__ == "__main__":
    sys.exit(main())
