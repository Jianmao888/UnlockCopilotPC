"""Launch one authorized single-product install with observation and a narrow root-open access reduction.

Adapted from the verified phase12 launcher. Differences:
  * run name, source directory, expected RUM and product scope are arguments
  * uses the interpreter this file is run with (frida already installed)

Usage (elevated):
    python run_install.py attempt-analysis1 <sourceDir> <expectedRumName> <productScope>
"""
import ctypes
import datetime
import json
import pathlib
import subprocess
import sys

import frida

root = pathlib.Path(__file__).resolve().parent
if len(sys.argv) < 5:
    raise SystemExit("usage: run_install.py <attemptName> <sourceDir> <expectedRum> <productScope>")
name = sys.argv[1]
source = sys.argv[2]
expected_rum = sys.argv[3]
scope = sys.argv[4]

if not name.startswith("attempt") or not name[7:].replace("-", "").isalnum():
    raise SystemExit("Unexpected run name")
if not ctypes.windll.shell32.IsUserAnAdmin():
    raise SystemExit("Run this installation launcher elevated")
signal = root / (name + "-ready.signal")
if signal.exists() or (root / (name + ".events.txt")).exists():
    raise SystemExit("Choose a fresh run name")

pwsh = r"C:\Users\jianm\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\powershell\pwsh.exe"
out = (root / (name + "-stdout.txt")).open("wb")
err = (root / (name + "-stderr.txt")).open("wb")
child = subprocess.Popen(
    [pwsh, "-NoProfile", "-MTA", "-File", str(root / "Invoke-Install.ps1"),
     "-RunName", name, "-Source", source, "-ExpectedRum", expected_rum, "-InstallProduct"],
    stdin=subprocess.DEVNULL, stdout=out, stderr=err,
    creationflags=subprocess.CREATE_NO_WINDOW,
)
(root / (name + "-process.json")).write_text(json.dumps(dict(
    pid=child.pid,
    startedUtc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    authorizedOperation="single-product Install", scope=scope,
    source=source)), encoding="utf-8")

session = None
try:
    session = frida.attach(child.pid)
    with (root / (name + "-api-trace.jsonl")).open("w", encoding="utf-8") as log:
        def record(message, data):
            log.write(json.dumps(message, ensure_ascii=True) + "\n")
            log.flush()
        script = session.create_script((root / "install-observer.js").read_text(encoding="utf-8"))
        script.on("message", record)
        script.load()
        signal.write_text("observer ready", encoding="ascii")
        try:
            code = child.wait(timeout=900)
            print(json.dumps(dict(pid=child.pid, exitCode=code, run=name)), flush=True)
        except subprocess.TimeoutExpired:
            print(json.dumps(dict(pid=child.pid, status="still running; not terminated during installation", run=name)), flush=True)
finally:
    if session:
        try:
            session.detach()
        except frida.InvalidOperationError:
            pass
    out.close()
    err.close()
