import datetime,hashlib,json,pathlib,sys,threading
import frida
r=pathlib.Path(__file__).resolve().parent
pid=int(sys.argv[1]);label=sys.argv[2]
mode=sys.argv[3] if len(sys.argv)>3 else 'resource'
if mode not in ('resource','session-family'):raise SystemExit('Unsupported broker experiment')
if not label.replace('-','').isalnum():raise SystemExit('Invalid label')
if hashlib.sha256(pathlib.Path('C:/Windows/System32/WSAIFabricHost.dll').read_bytes()).hexdigest()!='ea8f782b722161a15c2cc5bcff1407d4844aa972af4bb7bf45b5c0751e486170':raise SystemExit('Broker DLL changed')
output=r/(label+'.jsonl')
if output.exists():raise SystemExit('Choose a fresh label')
with output.open('w',encoding='utf-8') as log:
 def record(m,data=None):
  log.write(json.dumps({'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),**m})+'\n');log.flush()
  if m.get('payload',{}).get('event')=='broker-route-ready':(r/(label+'-ready.signal')).write_text('ready',encoding='ascii')
 session=frida.attach(pid)
 try:
  source='broker-session-family-experiment.js' if mode=='session-family' else 'broker-route-experiment.js'
  script=session.create_script((r/source).read_text(encoding='utf-8'));script.on('message',record);script.load()
  stop=r/(label+'-stop.signal');timer=threading.Event()
  for _ in range(180):
   if stop.exists():break
   timer.wait(.25)
 finally:session.detach()
print(json.dumps({'result':str(output),'detached':True}))
