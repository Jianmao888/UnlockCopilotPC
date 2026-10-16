import json,pathlib,struct,sys
base=pathlib.Path(__file__).parent
prefix=sys.argv[1] if len(sys.argv)>1 else 'msu'
resources=json.loads((base/(prefix+'-wim-resources.json')).read_text(encoding='utf-8'))
by_hash={e['sha1']:e for e in resources}
metadata_file=next(base.glob(prefix+'-wim-metadata-*.bin'))
data=metadata_file.read_bytes()
sec_len,sec_count=struct.unpack_from('<II',data,0)
root=(sec_len+7)&~7
entries=[]
seen=set()
def walk(offset,prefix=''):
    if offset in seen: return
    seen.add(offset)
    p=offset
    while p+8<=len(data):
        length=struct.unpack_from('<Q',data,p)[0]
        if length==0:break
        if length<102 or p+length>len(data):raise ValueError(f'invalid dentry {p} {length}')
        attr,sec,sub=struct.unpack_from('<IIQ',data,p+8)
        sha1=data[p+64:p+84].hex()
        streams,short_len,name_len=struct.unpack_from('<HHH',data,p+96)
        name=data[p+102:p+102+name_len].decode('utf-16-le')
        full=(prefix+'/'+name).strip('/')
        entry=dict(name=full,attributes=attr,metadata_offset=p,subdir_offset=sub,sha1=sha1)
        if sha1 in by_hash:entry.update(by_hash[sha1])
        entries.append(entry)
        if sub:walk(sub,full)
        if streams:raise ValueError('unexpected alternate streams')
        p+=length
walk(root)
(base/(prefix+'-payloads.json')).write_text(json.dumps(entries,indent=2),encoding='utf-8')
print('metadata bytes',len(data),'security_count',sec_count,'entries',len(entries))
for e in entries:
    print(e['name'],e.get('original_size'),e.get('offset'),e.get('flags'))
