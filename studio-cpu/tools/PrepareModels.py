import pathlib,sys,subprocess,json,hashlib
r=pathlib.Path(sys.argv[1]).resolve();legacy=pathlib.Path(sys.argv[2]).resolve();out=r/'prepared-model-blobs';out.mkdir(exist_ok=True)
sys.path.insert(0,str(r/'tools'))
from context_wire import repack
result=subprocess.run([str(r/'tools'/'ModelBuilder.exe'),str(legacy),str(out),str(r/'payload'/'cpu-runtime')],timeout=120)
if result.returncode:raise SystemExit(result.returncode)
rows=[]
for name in ['face101','matting109','pose113','light132']:
 blob=(out/(name+'-cpu.blob')).read_bytes();template=(r/'tools'/'templates'/(name+'.onnx')).read_bytes();model=repack(template,blob);dest=r/'payload'/'cpu-runtime'/(name+'-cpu-context.onnx');dest.write_bytes(model)
 rows.append(dict(model=name,bytes=len(model),sha256=hashlib.sha256(model).hexdigest()))
manifest=[dict(path=str(p.relative_to(r/'payload')).replace('\\','/'),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in sorted((r/'payload').rglob('*')) if p.is_file() and '__pycache__' not in str(p)]
(r/'payload-sha256.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
(r/'model-build-results.json').write_text(json.dumps(rows,indent=2),encoding='utf-8');print(json.dumps(rows,indent=2))
