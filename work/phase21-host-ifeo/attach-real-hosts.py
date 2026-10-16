"""Bounded elevated observer; attach only to children in this probe's own logs."""
import argparse,ctypes as C,hashlib,json,os,pathlib,time
ap=argparse.ArgumentParser();ap.add_argument('--label',required=True);ap.add_argument('--duration-seconds',type=int,default=60);a=ap.parse_args()
assert 30 <= a.duration_seconds <= 1800
assert a.label.replace('-','').isalnum()
root=pathlib.Path(__file__).resolve().parent
stage=pathlib.Path(r'C:\ProgramData\CodexAIResearch')/('host-startup-'+a.label)
logs=stage/'logs';temp=stage/'agent-temp';temp.mkdir(exist_ok=True)
os.environ['TEMP']=str(temp);os.environ['TMP']=str(temp)
import frida
for path,digest in [
 (r'C:\Program Files\WindowsApps\WindowsWorkload.WinMLShared.5.2_1.2608.951.0_x64__8wekyb3d8bbwe\cacheapi.dll','671de69b81da93bd2ce3e5cd6048a9a398f68dda7ef62112461dd01a43c6a8cd'),
 (r'C:\Program Files\WindowsApps\WindowsWorkload.ScrRegDetection.Lnl.1_1.2608.951.0_x64__8wekyb3d8bbwe\srdapi.dll','fe2049fb2da34080fed109661b940b1612a47bbbfee6c2649fb3ac1f536ba440')]:
 # Verify each actual file before any version-specific interception.
 actual=hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()
 if actual!=digest:raise RuntimeError('DLL hash changed: '+path+' '+actual)
stream=(root/(a.label+'-host-hooks.jsonl')).open('w',encoding='utf-8')
def log(event,**data):stream.write(json.dumps(dict(time=time.time(),event=event,**data),ensure_ascii=False)+'\n');stream.flush()
attached={};attempted=set();deadline=time.monotonic()+a.duration_seconds
try:
 log('controller_ready',stage=str(stage));(root/(a.label+'-hooks-ready.signal')).write_text('ready')
 while time.monotonic()<deadline and not (root/(a.label+'-stop.signal')).exists():
  pids=set()
  if logs.exists():
   for file in logs.glob('wrapper-*.jsonl'):
    for line in file.read_text(encoding='utf-8-sig').splitlines():
     try:r=json.loads(line)
     except ValueError:continue
     if r.get('event')=='startup_wait_agent':pids.add(r['data']['pid'])
  for pid in pids-attempted:
   attempted.add(pid)
   try:
    session=frida.attach(pid)
    script=session.create_script((root/'host-cpu-hook.js').read_text(encoding='utf-8'))
    script.on('message',lambda m,d,p=pid:log('message',pid=p,message=m));script.load()
    attached[pid]=(session,script)
    (logs/('host-'+str(pid)+'-agent-ready.signal')).write_text('hook loaded')
    log('host_attached',pid=pid)
   except Exception as e:log('attach_failed',pid=pid,error=repr(e))
  time.sleep(.08)
finally:
 for pid,(session,script) in attached.items():
  try:script.exports_sync.cleanup();session.detach();log('detached',pid=pid)
  except Exception as e:log('detach_result',pid=pid,error=repr(e))
 stream.close()
