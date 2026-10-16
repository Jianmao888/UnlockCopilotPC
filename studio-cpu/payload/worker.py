import ctypes as C,hashlib,json,os,pathlib,sys,time,threading
root=pathlib.Path(sys.argv[1]).resolve();os.chdir(root)
temp=root/'agent-temp';temp.mkdir(exist_ok=True);os.environ['TEMP']=str(temp);os.environ['TMP']=str(temp)
import frida
profile=json.loads((root/'profile.json').read_text(encoding='utf-8-sig'))
status=root/'status.json';stop=root/'worker.stop';logpath=root/'bridge.jsonl';lock=threading.RLock();attached_pid=None;session=None;script=None;last_error=None;counts={};errors=0
def log(event,**data):
 global errors
 with lock:
  if event.endswith('error'):errors+=1
  if logpath.exists() and logpath.stat().st_size>8*1024*1024:
   rotated=root/'bridge.previous.jsonl'
   if rotated.exists():rotated.unlink()
   logpath.replace(rotated)
  with logpath.open('a',encoding='utf-8') as f:f.write(json.dumps(dict(time=time.time(),event=event,**data),ensure_ascii=False)+'\n')
def state(active,reason=None):
 with lock:
  o=dict(worker_pid=os.getpid(),active=active,time=time.time(),service_pid=attached_pid,reason=reason,inference_counts=counts,error_events=errors,automatic_camera_capture=False)
  tmp=root/'status.json.tmp';tmp.write_text(json.dumps(o,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
  for attempt in range(25):
   try:os.replace(tmp,status);return True
   except PermissionError:time.sleep(.02)
  # Diagnostic readers or antivirus can temporarily deny replacement on Windows.
  # Keep the last complete status and retry next heartbeat without killing AI work.
  return False
audit_cache={}
def audit():
 for item in profile['driverFiles']:
  path=pathlib.Path(item['path']);stat=path.stat();identity=(stat.st_size,stat.st_mtime_ns)
  if audit_cache.get(item['path'])==identity:continue
  if hashlib.sha256(path.read_bytes()).hexdigest()!=item['sha256'].lower():raise RuntimeError('Driver changed: '+item['path'])
  audit_cache[item['path']]=identity
def message(m,data):
 if m['type']=='send':
  event=m['payload'];kind=event.pop('event','unknown')
  if kind=='inference':counts[event['model']]=event['count']
  log(kind,**event)
 else:log('agent_error',detail=m)
class SSP(C.Structure):_fields_=[(n,C.c_uint32) for n in ['type','state','accepted','win32','specific','checkpoint','hint','pid','flags']]
a=C.WinDLL('advapi32',use_last_error=True)
a.OpenSCManagerW.argtypes=[C.c_wchar_p,C.c_wchar_p,C.c_uint32];a.OpenSCManagerW.restype=C.c_void_p
a.OpenServiceW.argtypes=[C.c_void_p,C.c_wchar_p,C.c_uint32];a.OpenServiceW.restype=C.c_void_p
a.QueryServiceStatusEx.argtypes=[C.c_void_p,C.c_int,C.c_void_p,C.c_uint32,C.c_void_p];a.QueryServiceStatusEx.restype=C.c_int
a.StartServiceW.argtypes=[C.c_void_p,C.c_uint32,C.c_void_p];a.StartServiceW.restype=C.c_int
a.CloseServiceHandle.argtypes=[C.c_void_p]
scm=a.OpenSCManagerW(None,None,1);service=a.OpenServiceW(scm,'FrameServer',0x14) if scm else None
if not service:raise C.WinError(C.get_last_error())
def detached(reason,*_):
 global attached_pid
 attached_pid=None;log('detached',reason=reason);state(False,reason)
source='const profile='+json.dumps(profile)+';\n'+(root/'runtime-agent.js').read_text(encoding='utf-8')
try:
 audit();last_audit=time.monotonic();last_state=0
 log('worker_started',pid=os.getpid(),frida=frida.__version__)
 while not stop.exists():
  ss=SSP();needed=C.c_uint32()
  if not a.QueryServiceStatusEx(service,0,C.byref(ss),C.sizeof(ss),C.byref(needed)):raise C.WinError(C.get_last_error())
  if ss.state==1:
   if not a.StartServiceW(service,0,None) and C.get_last_error()!=1056:raise C.WinError(C.get_last_error())
  elif ss.state==4 and ss.pid and attached_pid!=ss.pid:
   if session:
    try:session.detach()
    except Exception:pass
   try:
    candidate=frida.attach(ss.pid);candidate.on('detached',detached);agent=candidate.create_script(source);agent.on('message',message);agent.load();health=agent.exports_sync.health()
    if health['pid']!=ss.pid:raise RuntimeError('Service PID changed during attach')
    session=candidate;script=agent;attached_pid=ss.pid;counts.clear();state(True);log('attached',pid=attached_pid);last_error=None
   except Exception as e:
    if repr(e)!=last_error:log('attach_error',error=repr(e));last_error=repr(e)
    state(False,str(e))
    try:candidate.detach()
    except Exception:pass
    time.sleep(.5)
  now=time.monotonic()
  if now-last_audit>=10:audit();last_audit=now
  if now-last_state>=1:
   if attached_pid is not None and script is not None:
    try:counts.update(script.exports_sync.health()['counts'])
    except Exception as e:
     log('health_error',error=repr(e));attached_pid=None
   state(attached_pid is not None,last_error);last_state=now
  time.sleep(.2)
except BaseException as e:
 log('worker_error',error=repr(e));state(False,str(e));raise
finally:
 if session:
  try:session.detach()
  except Exception:pass
 a.CloseServiceHandle(service);a.CloseServiceHandle(scm);state(False,'stopped');log('worker_stopped')
