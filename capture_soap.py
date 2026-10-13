#!/usr/bin/env python3
"""
capture_soap.py — 用 Frida 在进程内抓取 InstallService.dll 发出的 SOAP 请求

原理：
  InstallService.dll 是 in-process 激活的 WinRT 类，且导入 WinHTTP。
  SOAP 请求体通过 WinHttpSendRequest 的 lpOptional 参数发出（明文，TLS 之前）。
  因此 hook WinHttpSendRequest 即可拿到完整 XML —— 不需要证书、不需要管理员。

用法：
  python capture_soap.py
退出后：捕获内容写入 soap-*.xml / soap-capture.jsonl
"""
import json
import os
import sys
import time

import frida

HERE = os.path.dirname(os.path.abspath(__file__))
TRIGGER = os.path.join(HERE, "trigger_store_search.ps1")
OUTDIR = os.path.join(HERE, "capture")
os.makedirs(OUTDIR, exist_ok=True)

JS = r"""
'use strict';

const KEYWORDS = ['SoftwareDistribution', 'SyncUpdates', 'ProductsParameters',
                  'DeviceAttributes', 'GetCookie', 'ClientWebService'];
const captures = [];
let seq = 0;

function report(event, data) { send(Object.assign({ event: event }, data || {})); }

function bodyPreview(s) {
  return s.replace(/\s+/g, ' ').slice(0, 160);
}

// ---- WinHttpSendRequest: 请求体在 args[3]/args[4] ----
let hooked = false;

function hookWinHttp() {
  if (hooked) return;
  let winhttp;
  try { winhttp = Process.getModuleByName('winhttp.dll'); }
  catch (e) { return; }   // 尚未加载
  hooked = true;

  const targets = [
    ['WinHttpSendRequest', 3, 4],
    ['WinHttpWriteData', 1, 2],
  ];

  for (const [name, bufIdx, lenIdx] of targets) {
    let addr;
    try { addr = winhttp.getExportByName(name); } catch (e) { continue; }
    Interceptor.attach(addr, {
      onEnter(args) {
        try {
          const len = args[lenIdx].toInt32();
          if (len <= 0 || len > 8 * 1024 * 1024) {
            report('send-empty', { api: name, len: len });
            return;
          }
          const p = args[bufIdx];
          if (p.isNull()) return;
          let text = p.readUtf8String(len);
          if (!text) return;
          const hit = KEYWORDS.some(k => text.includes(k));
          if (!hit) {
            report('send-other', { api: name, bytes: len, preview: bodyPreview(text) });
            return;
          }
          seq++;
          const fn = 'soap-' + String(seq).padStart(3, '0') + '.xml';
          const path = __OUTDIR__ + '\\\\' + fn;
          const f = new File(path, 'w');
          f.write(text); f.close();
          report('capture', {
            api: name, seq: seq, bytes: len, file: fn,
            preview: bodyPreview(text)
          });
        } catch (e) {
          report('error', { stage: name, message: String(e) });
        }
      }
    });
    report('hook-installed', { api: name });
  }

  // 记录 URL，便于知道哪个请求是 WU 的
  try {
    Interceptor.attach(winhttp.getExportByName('WinHttpOpenRequest'), {
      onEnter(args) {
        try {
          const path = args[2].isNull() ? '' : args[2].readUtf16String();
          report('open-request', { path: path });
        } catch (e) {}
      }
    });
  } catch (e) {}

  try {
    Interceptor.attach(winhttp.getExportByName('WinHttpConnect'), {
      onEnter(args) {
        try {
          const host = args[1].isNull() ? '' : args[1].readUtf16String();
          report('connect', { host: host, port: args[2].toInt32() });
        } catch (e) {}
      }
    });
  } catch (e) {}
}

// WWS (Windows Web Services) hook —— 先占位
function hookWws() { report('hook-installed', { api: 'webservices.dll(placeholder)' }); }

hookWinHttp();
// 观察模块加载：确认 SOAP 栈到底在哪里
try {
  Process.attachModuleObserver({
    onAdded(module) {
      const n = module.name.toLowerCase();
      report('module', { name: module.name });
      if (n === 'winhttp.dll') hookWinHttp();
      if (n === 'webservices.dll') hookWws();
    }
  });
  report('ready', { note: 'module observer armed' });
} catch (e) {
  report('error', { stage: 'module-observer', message: String(e) });
}

rpc.exports = { count: () => seq };
"""


def on_message(msg, data):
    if msg.get("type") == "send":
        p = msg["payload"]
        ev = p.get("event")
        if ev == "capture":
            print(f"  *** 捕获 #{p['seq']}  [{p['api']}] {p['bytes']} 字节 -> {p['file']}")
            print(f"      {p['preview']}")
        elif ev == "hook-installed":
            print(f"  [hook] {p['api']} 已安装")
        elif ev == "module":
            print(f"  [module] {p.get('name')} {p.get('note','')}")
        elif ev == "send-other":
            print(f"  [send] {p['api']} {p['bytes']}B: {p.get('preview','')[:100]}")
        elif ev == "send-empty":
            print(f"  [send] {p['api']} len={p['len']}")
        elif ev in ("connect", "open-request"):
            print(f"  [{ev}] {p.get('host','')}{p.get('path','')}")
        elif ev == "error":
            print(f"  [err:{p.get('stage')}] {p.get('message')}")
    elif msg.get("type") == "error":
        print("  [script error]", msg.get("description"))


def main():
    if not os.path.exists(TRIGGER):
        print("找不到 trigger_store_search.ps1")
        return 1

    ps = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32",
                      "WindowsPowerShell", "v1.0", "powershell.exe")
    if not os.path.exists(ps):
        ps = "powershell.exe"

    argv = [ps, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", TRIGGER]
    print(f"==> 启动: {' '.join(argv)}")
    print("==> 以暂停状态启动，先装 hook 再恢复\n")

    pid = frida.spawn(argv)
    session = frida.attach(pid)
    js = JS.replace("__OUTDIR__", json.dumps(OUTDIR))
    script = session.create_script(js)
    script.on("message", on_message)
    script.load()
    print(f"==> hook 就绪 (pid={pid})，恢复进程\n")

    frida.resume(pid)

    # 等待触发器跑完
    deadline = time.time() + 180
    while time.time() < deadline:
        time.sleep(1)
        try:
            n = script.exports_sync.count()
        except Exception:
            break
        if n:
            pass

    try:
        session.detach()
    except Exception:
        pass

    files = sorted(f for f in os.listdir(OUTDIR) if f.startswith("soap-"))
    print(f"\n==> 捕获到 {len(files)} 个请求体，保存在 {OUTDIR}")
    for f in files:
        p = os.path.join(OUTDIR, f)
        size = os.path.getsize(p)
        print(f"    {f}  ({size} 字节)")
        if size > 0:
            with open(p, encoding="utf-8", errors="replace") as fh:
                head = fh.read(600).replace("\n", " ")
            print(f"        {head[:400]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
