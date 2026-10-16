import pathlib,json,hashlib
r=pathlib.Path(__file__).resolve().parent
def vi(b,p):
 v=0;s=0
 while True:
  x=b[p];p+=1;v|=(x&127)<<s
  if x<128:return v,p
  s+=7
def parse(b):
 p=0;out=[]
 while p<len(b):
  tag,p=vi(b,p);n,t=tag>>3,tag&7
  if t==0:v,p=vi(b,p)
  elif t==2:l,p=vi(b,p);v=b[p:p+l];p+=l
  elif t in (1,5):l=8 if t==1 else 4;v=b[p:p+l];p+=l
  else:raise ValueError(t)
  out.append((n,t,v))
 return out
def encvi(v):
 b=bytearray()
 while v>=128:b.append((v&127)|128);v>>=7
 b.append(v);return bytes(b)
def pack(fs):
 out=bytearray()
 for n,t,v in fs:
  out+=encvi((n<<3)|t)
  if t==0:out+=encvi(v)
  elif t==2:out+=encvi(len(v))+v
  else:out+=v
 return bytes(out)
def attr(b,blob):
 f=parse(b)
 if next((v for n,t,v in f if n==1),None)!=b'ep_cache_context':return b
 return pack([(n,t,blob if n==4 else v) for n,t,v in f])
def node(b,blob):return pack([(n,t,attr(v,blob) if n==5 else v) for n,t,v in parse(b)])
def graph(b,blob):return pack([(n,t,node(v,blob) if n==1 else v) for n,t,v in parse(b)])
def repack(original,blob):return pack([(n,t,graph(v,blob) if n==7 else v) for n,t,v in parse(original)])
if __name__=='__main__':
 for ident,label in [(101,'face101'),(109,'matting109'),(113,'pose113'),(132,'light132')]:
  source=r/'decoded-effect-resources'/(str(ident)+'.onnx');blob=(r/'cpu-models'/(label+'-cpu.blob')).read_bytes();result=repack(source.read_bytes(),blob)
  dest=r/'cpu-models'/(label+'-cpu-context.onnx');dest.write_bytes(result)
  print(json.dumps(dict(path=str(dest),size=len(result),sha256=hashlib.sha256(result).hexdigest())))
