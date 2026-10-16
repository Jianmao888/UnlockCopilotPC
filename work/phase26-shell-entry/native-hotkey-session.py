"""Coordinate original Explorer/CTD RegisterHotKey ownership for one bounded session."""
import argparse
import ctypes as C
import ctypes.wintypes as W
import hashlib
import json
import pathlib
import time
import uuid

import frida

parser = argparse.ArgumentParser()
parser.add_argument('--label', required=True)
parser.add_argument('--parent-pid', type=int, required=True)
parser.add_argument('--duration-seconds', type=int, required=True)
args = parser.parse_args()
if not args.label.replace('-', '').isalnum() or not 1 <= args.duration_seconds <= 1750:
    raise ValueError('Unexpected bounded session arguments')
root = pathlib.Path(__file__).resolve().parent
stop = root / (args.label + '-native-stop.signal')
ready = root / (args.label + '-native-ready.json')
done = root / (args.label + '-native-done.json')
out = (root / (args.label + '-native.jsonl')).open('x', encoding='utf-8')
u = C.WinDLL('user32', use_last_error=True)
k = C.WinDLL('kernel32', use_last_error=True)
u.FindWindowW.argtypes = [W.LPCWSTR, W.LPCWSTR]
u.FindWindowW.restype = W.HWND
u.GetWindowThreadProcessId.argtypes = [W.HWND, C.POINTER(W.DWORD)]
k.OpenProcess.argtypes = [W.DWORD, W.BOOL, W.DWORD]
k.OpenProcess.restype = W.HANDLE
k.CloseHandle.argtypes = [W.HANDLE]
k.WaitForSingleObject.argtypes = [W.HANDLE, W.DWORD]
k.QueryFullProcessImageNameW.argtypes = [W.HANDLE, W.DWORD, W.LPWSTR, C.POINTER(W.DWORD)]
source = (root / 'native-hotkey-registration.js').read_text(encoding='utf-8')
records, sessions, scripts = {}, {}, {}
sequence = 0
release_attempted = register_attempted = False
restored = False
parent = k.OpenProcess(0x100000, False, args.parent_pid)


def log(event, **data):
    out.write(json.dumps(dict(time=time.time(), event=event, **data)) + '\n')
    out.flush()


def attach(name, cls, hotkey_id, image, expected):
    deadline = time.monotonic() + 8
    hwnd = u.FindWindowW(cls, None)
    while not hwnd and time.monotonic() < deadline and not stop.exists():
        time.sleep(.1)
        hwnd = u.FindWindowW(cls, None)
    if not hwnd:
        raise RuntimeError('Native window absent: ' + name)
    if hashlib.sha256(pathlib.Path(image).read_bytes()).hexdigest() != expected:
        raise RuntimeError('Native target version changed: ' + image)
    pid = W.DWORD()
    u.GetWindowThreadProcessId(hwnd, C.byref(pid))
    process = k.OpenProcess(0x1000, False, pid.value)
    if not process:
        raise RuntimeError('Cannot verify native window image')
    try:
        path, length = C.create_unicode_buffer(32768), W.DWORD(32768)
        if not k.QueryFullProcessImageNameW(process, 0, path, C.byref(length)):
            raise C.WinError(C.get_last_error())
        if pathlib.Path(path.value) != pathlib.Path(image):
            raise RuntimeError('Unexpected native window owner: ' + path.value)
    finally:
        k.CloseHandle(process)
    session = frida.attach(pid.value)
    sessions[name] = session
    config = dict(name=name, pid=pid.value, hwnd=hex(hwnd), hotkeyId=hotkey_id,
                  token=hex(0x43d00000 + (uuid.uuid4().int & 0xffff)))
    script = session.create_script(source.replace('/*__CONFIG__*/ {}', json.dumps(config)))

    def on_message(message, data):
        log('message', name=name, message=message)
        payload = message.get('payload', {})
        if payload.get('event') == 'native-registration-result':
            records[(name, payload['sequence'])] = payload

    script.on('message', on_message)
    script.load()
    scripts[name] = script
    log('attached', **config)


def action(name, operation):
    global sequence
    sequence += 1
    current = sequence
    scripts[name].exports_sync.action(operation, current)
    deadline = time.monotonic() + 4
    while time.monotonic() < deadline:
        result = records.get((name, current))
        if result:
            return result
        time.sleep(.025)
    raise TimeoutError('Native owner thread did not complete operation: ' + name)


def publish(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value), encoding='utf-8')
    temporary.replace(path)


try:
    if not parent:
        raise RuntimeError('Session controller is absent')
    attach('explorer.exe', 'Shell_TrayWnd', 570, r'C:\Windows\explorer.exe',
           '34ac55b23b6d840cc9fa8304c0149b8bb026d817b39610728092878d634a61eb')
    attach('clicktodo.exe', 'ScreenrayOwnerWindow', 42,
           r'C:\Windows\SystemApps\MicrosoftWindows.Client.CoreAI_cw5n1h2txyewy\ClickToDo.exe',
           '6f709cb5e0b3506dcda250ae3ee27d67f25153a7f8db33f6173c7a3c4c889961')
    release_attempted = True
    if not action('explorer.exe', 'unregister')['success']:
        raise RuntimeError('Explorer did not release Search Win+Q')
    register_attempted = True
    if not action('clicktodo.exe', 'register')['success']:
        raise RuntimeError('ClickToDo native Win+Q registration failed')
    publish(ready, dict(Ready=True, Pid=__import__('os').getpid()))
    log('native-session-ready', seconds=args.duration_seconds)
    deadline = time.monotonic() + args.duration_seconds
    while time.monotonic() < deadline and not stop.exists():
        if k.WaitForSingleObject(parent, 0) != 0x102:
            break
        if any(session.is_detached for session in sessions.values()):
            break
        time.sleep(.1)
except Exception as error:
    log('native-session-error', error=str(error))
    if not ready.exists():
        publish(ready, dict(Ready=False, Error=str(error)))
finally:
    if register_attempted:
        try:
            log('client-unregister', result=action('clicktodo.exe', 'unregister'))
        except Exception as error:
            log('client-unregister-error', error=str(error))
    if release_attempted:
        try:
            result = action('explorer.exe', 'register')
            restored = result['success']
            log('search-restored', result=result)
        except Exception as error:
            log('restore-error', error=str(error))
    for name, session in sessions.items():
        try:
            if name in scripts:
                scripts[name].exports_sync.cleanup()
            session.detach()
        except Exception as error:
            log('detach-error', name=name, error=str(error))
    if parent:
        k.CloseHandle(parent)
    publish(done, dict(SearchRestored=restored, ReleaseAttempted=release_attempted))
    out.close()
