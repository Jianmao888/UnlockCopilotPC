#!/usr/bin/env python3
"""
observe_acquire.py — ① 观察 EnsureReadyAsync 期间系统是否尝试获取模型包

三个独立信号：
  A. 应用进程内所有 RoGetActivationFactory 的类名（重点关注 AI / WU / 包管理）
  B. 进程内新加载的模块（wuapi / wuaueng / Workloads / Deployment）
  C. 注册表 HKLM\\...\\WindowsAI\\LastConfiguration 的 AttemptedInstallCount 变化

不主动调用任何 API —— 让 AI Dev Gallery 自己走流程（点击 OCR 示例）。

用法: python observe_acquire.py [seconds]
"""
import sys
import time

import frida

PID = None
for p in frida.get_local_device().enumerate_processes():
    if "aid" in p.name.lower() or "gallery" in p.name.lower():
        PID = p.pid
        break

JS = r"""
'use strict';
var combase = Process.getModuleByName('combase.dll');
var RawBuffer = new NativeFunction(combase.getExportByName('WindowsGetStringRawBuffer'),
    'pointer', ['pointer','pointer'], 'win64');
function report(e,d){ send(Object.assign({event:e}, d||{})); }

var WATCH = ['AI', 'Vision', 'SemanticSearch', 'Workload', 'Workloads',
             'PackageManager', 'Deployment', 'Update', 'InstallService',
             'Capabilit', 'Model', 'Session'];
var seen = {};

Interceptor.attach(combase.getExportByName('RoGetActivationFactory'), {
  onEnter: function (args) {
    try {
      var len = Memory.alloc(4); len.writeU32(0);
      var b = RawBuffer(args[0], len);
      var n = len.readU32();
      if (n <= 0 || n > 200) return;
      var cn = b.readUtf16String(n);
      var hit = false;
      for (var i = 0; i < WATCH.length; i++) if (cn.indexOf(WATCH[i]) >= 0) { hit = true; break; }
      if (!hit) return;
      if (seen[cn]) { if (seen[cn] === 1) report('act-repeat', { cls: cn }); seen[cn]++; return; }
      seen[cn] = 1;
      report('act', { cls: cn });
    } catch (e) {}
  }
});

// 记录新加载的模块
try {
  Process.attachModuleObserver({
    onAdded: function (m) {
      var n = m.name.toLowerCase();
      if (n.indexOf('wu') === 0 || n.indexOf('workload') >= 0 || n.indexOf('deploy') >= 0 ||
          n.indexOf('models') >= 0 || n.indexOf('session') >= 0 || n.indexOf('appx') >= 0 ||
          n.indexOf('package') >= 0 || n.indexOf('install') >= 0) {
        report('module', { name: m.name });
      }
    }
  });
} catch (e) {}
report('info', { msg: 'observer armed' });
"""


def on_message(msg, data):
    if msg.get("type") != "send":
        if msg.get("type") == "error":
            print("  [script error]", msg.get("description"))
        return
    p = msg["payload"]; e = p.get("event")
    if e == "info":
        print("  ", p.get("msg"))
    elif e == "act":
        print(f"  [activate] {p['cls']}")
    elif e == "act-repeat":
        print(f"  [activate×] {p['cls']}")
    elif e == "module":
        print(f"  [module+]  {p['name']}")


def snapshot(tag):
    import subprocess
    ps = ("$p=Get-ItemProperty 'HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\WindowsAI\\LastConfiguration' "
          "-ErrorAction SilentlyContinue; "
          "'" + tag + " HardwareCompatibility=' + $p.HardwareCompatibility + "
          "'  AttemptedInstallCount=' + $p.AttemptedInstallCount + "
          "'  LastOperationKind=' + $p.LastOperationKind")
    r = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                       capture_output=True, text=True)
    print("  " + (r.stdout.strip() or "(读取失败)"))


def pkg_count():
    import subprocess
    ps = ("@(Get-AppxPackage -ErrorAction SilentlyContinue | "
          "Where-Object { $_.Name -match 'WindowsWorkload' }).Count")
    r = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                       capture_output=True, text=True)
    print("  WindowsWorkload 包数量 = " + (r.stdout.strip() or "?"))


def main():
    if PID is None:
        print("AI Dev Gallery 未运行"); return 1
    secs = int(sys.argv[1]) if len(sys.argv) > 1 else 180

    print("=== 基线（Hook 之前）===")
    snapshot("BEFORE")
    pkg_count()

    session = frida.attach(PID)
    script = session.create_script(JS)
    script.on("message", on_message)
    script.load()
    print(f"\n==> 观察中（{secs}s）—— 请在 AI Dev Gallery 里点击 'AI APIs' → 'Text Recognition (OCR)'")

    time.sleep(secs)
    session.detach()

    print("\n=== 之后（Hook 结束）===")
    snapshot("AFTER")
    pkg_count()
    return 0


if __name__ == "__main__":
    sys.exit(main())
