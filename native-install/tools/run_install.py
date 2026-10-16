"""Validate or plan one pinned product; --install explicitly requests native Install.

Adapted from the verified phase12 launcher. Differences:
  * run name, source directory, expected RUM and product scope are arguments
  * uses the interpreter this file is run with (frida already installed)

Usage (elevated):
    python run_install.py attempt-analysis1 <sourceDir> <expectedRumName> <productScope> --plan-only
    python run_install.py attempt-analysis2 <sourceDir> <expectedRumName> <productScope> --install
"""
import ctypes
import argparse
import datetime
import json
import os
import pathlib
import shutil
import subprocess
import sys

root = pathlib.Path(__file__).resolve().parent
parser = argparse.ArgumentParser(description='Validate pinned product files, then plan or explicitly install one product')
parser.add_argument('name')
parser.add_argument('source', type=pathlib.Path)
parser.add_argument('expected_rum')
parser.add_argument('scope')
parser.add_argument('--pwsh', default=os.environ.get('UNLOCK_COPILOT_PWSH') or shutil.which('pwsh.exe'))
mode = parser.add_mutually_exclusive_group()
mode.add_argument('--install', action='store_true')
mode.add_argument('--plan-only', action='store_true')
parser.add_argument('--validate-only', action='store_true', help='Files only: no elevation, Frida attachment, or DLL execution')
args = parser.parse_args()
name, source, expected_rum, scope = args.name, str(args.source.resolve()), args.expected_rum, args.scope
if expected_rum != scope + '.rum.json.cab':
    parser.error('RUM name must match the complete product scope, including .amd64')
sys.path.insert(0, str(root.parents[1]))
from tools.product_layout import validate_content
try:
    validation = validate_content(source, scope)
except (OSError, ValueError, KeyError) as error:
    raise SystemExit('Content validation failed; no native code loaded: ' + str(error))
if args.validate_only:
    print(json.dumps(validation))
    raise SystemExit(0)
if not args.pwsh or not pathlib.Path(args.pwsh).is_file():
    parser.error('Install PowerShell 7 on PATH, set UNLOCK_COPILOT_PWSH, or pass --pwsh')

if not name.startswith("attempt") or not name[7:].replace("-", "").isalnum():
    raise SystemExit("Unexpected run name")
if not ctypes.windll.shell32.IsUserAnAdmin():
    raise SystemExit("Run this installation launcher elevated")
import frida
signal = root / (name + "-ready.signal")
if signal.exists() or (root / (name + ".events.txt")).exists():
    raise SystemExit("Choose a fresh run name")

pwsh = args.pwsh
out = (root / (name + "-stdout.txt")).open("wb")
err = (root / (name + "-stderr.txt")).open("wb")
child = subprocess.Popen(
    [pwsh, "-NoProfile", "-MTA", "-File", str(root / "Invoke-Install.ps1"),
     "-RunName", name, "-Source", source, "-ExpectedRum", expected_rum] + (["-InstallProduct"] if args.install else []),
    stdin=subprocess.DEVNULL, stdout=out, stderr=err,
    creationflags=subprocess.CREATE_NO_WINDOW,
)
(root / (name + "-process.json")).write_text(json.dumps(dict(
    pid=child.pid,
    startedUtc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    authorizedOperation="single-product Install" if args.install else "planning only", scope=scope,
    source=source)), encoding="utf-8")

session = None
exit_code = 1
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
            exit_code = code
            print(json.dumps(dict(pid=child.pid, exitCode=code, run=name)), flush=True)
        except subprocess.TimeoutExpired:
            exit_code = 2
            print(json.dumps(dict(pid=child.pid, status="still running; not terminated during installation", run=name)), flush=True)
finally:
    if session:
        try:
            session.detach()
        except frida.InvalidOperationError:
            pass
    out.close()
    err.close()
raise SystemExit(exit_code)
