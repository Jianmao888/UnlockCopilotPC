"""Temporary PLM debugger for the CoreAI Click to Do activation.

Windows starts this helper with -p PID -tid TID while the packaged app's
initial thread is suspended. The helper arms a process-local Frida hook and
then resumes that thread. It exits after the target process exits or 5 minutes.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import datetime as dt
import json
from pathlib import Path
import sys
import time

import frida

ROOT = Path(__file__).resolve().parent.parent / "phase19-clicktodo"
PROBE_DIR = ROOT.parent / "phase24-manual-test" / "runtime"
HOOK_FILE = ROOT.parent / "phase2-hook" / "capability-hook.js"
SUPPORT_HOOK_FILE = ROOT / "clicktodo-support-result-hook.js"
TARGET_NAME = "clicktodo.exe"
MAX_SECONDS = 1800

kernel = ctypes.WinDLL("kernel32", use_last_error=True)
kernel.OpenThread.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel.OpenThread.restype = wintypes.HANDLE
kernel.ResumeThread.argtypes = [wintypes.HANDLE]
kernel.ResumeThread.restype = wintypes.DWORD
kernel.CloseHandle.argtypes = [wintypes.HANDLE]
kernel.CloseHandle.restype = wintypes.BOOL
kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel.OpenProcess.restype = wintypes.HANDLE
kernel.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD,
                                               wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
kernel.QueryFullProcessImageNameW.restype = wintypes.BOOL
kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
kernel.WaitForSingleObject.restype = wintypes.DWORD


def log_line(path: Path, event: str, **data) -> None:
    record = {"time": dt.datetime.now().astimezone().isoformat(), "event": event, **data}
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def image_path(pid: int) -> str:
    process = kernel.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not process:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        size = wintypes.DWORD(32768)
        output = ctypes.create_unicode_buffer(size.value)
        if not kernel.QueryFullProcessImageNameW(process, 0, output, ctypes.byref(size)):
            raise ctypes.WinError(ctypes.get_last_error())
        return output.value
    finally:
        kernel.CloseHandle(process)


def resume_thread(tid: int, path: Path) -> None:
    thread = kernel.OpenThread(0x0002, False, tid)  # THREAD_SUSPEND_RESUME
    if not thread:
        log_line(path, "resume-open-failed", tid=tid, win32=ctypes.get_last_error())
        return
    try:
        prior = kernel.ResumeThread(thread)
        if prior == 0xFFFFFFFF:
            log_line(path, "resume-failed", tid=tid, win32=ctypes.get_last_error())
        else:
            log_line(path, "thread-resumed", tid=tid, previousSuspendCount=prior)
    finally:
        kernel.CloseHandle(thread)


def main() -> int:
    PROBE_DIR.mkdir(parents=True, exist_ok=True)
    log = PROBE_DIR / "startup-hook.jsonl"
    args = sys.argv[1:]
    try:
        pid = int(args[args.index("-p") + 1])
        tid = int(args[args.index("-tid") + 1])
    except (ValueError, IndexError):
        log_line(log, "bad-arguments", args=args)
        return 2

    process = None
    session = None
    scripts = []
    resumed = False
    try:
        image = image_path(pid)
        log_line(log, "debugger-start", pid=pid, tid=tid, image=image)
        if Path(image).name.lower() != TARGET_NAME:
            log_line(log, "skip-non-clicktodo", image=image)
            return 0

        process = kernel.OpenProcess(0x00100000 | 0x1000, False, pid)  # SYNCHRONIZE | QUERY_LIMITED
        if not process:
            raise ctypes.WinError(ctypes.get_last_error())

        session = frida.get_local_device().attach(pid)
        source = HOOK_FILE.read_text(encoding="utf-8")
        source = source.replace("/*__CONFIG_JSON__*/ {}", json.dumps({
            "featureOverrides": {"1": True},
            "copilotPlusOverride": None,
            "enterpriseGateOverride": True,
        }))
        for script_path, script_name in [
            (HOOK_FILE, "clicktodo-startup-capability-hook"),
            (SUPPORT_HOOK_FILE, "clicktodo-support-result-hook"),
            (ROOT.parent / "phase23-client-crash" / "optional-source-only.js", "optional-source-only"),
        ]:
            script = session.create_script(script_path.read_text(encoding="utf-8"), name=script_name)
            script.on("message", lambda message, data: log_line(log, "frida-message", message=message))
            script.load()
            scripts.append(script)
            log_line(log, "hook-loaded", pid=pid, script=script_name, fridaVersion=frida.__version__)
        resume_thread(tid, log)
        resumed = True

        deadline = time.monotonic() + MAX_SECONDS
        while time.monotonic() < deadline:
            status = kernel.WaitForSingleObject(process, 250)
            if status == 0:  # WAIT_OBJECT_0
                log_line(log, "target-exited", pid=pid)
                time.sleep(1)  # allow final Frida messages to reach the log callback
                return 0
            if status not in (0x102,):  # WAIT_TIMEOUT
                log_line(log, "wait-failed", pid=pid, status=status)
                return 1
        log_line(log, "watchdog-expired", pid=pid, maxSeconds=MAX_SECONDS)
        return 0
    except Exception as error:
        log_line(log, "debugger-error", pid=pid, errorType=type(error).__name__, error=str(error))
        return 1
    finally:
        if not resumed:
            resume_thread(tid, log)
        for script in scripts:
            try:
                script.exports_sync.cleanup()
            except Exception:
                pass
        if session is not None:
            try:
                session.detach()
            except Exception:
                pass
        if process:
            kernel.CloseHandle(process)


if __name__ == "__main__":
    raise SystemExit(main())
