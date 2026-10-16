import hashlib, json, pathlib, struct, urllib.request, sys
from download_utils import microsoft_url

base = pathlib.Path(__file__).parent
files_name = sys.argv[1] if len(sys.argv)>1 else 'uup-msu-files.json'
prefix = sys.argv[2] if len(sys.argv)>2 else 'msu'
files = json.loads((base / files_name).read_text(encoding='utf-8-sig'))
item = max(files, key=lambda e: int(e['Size']))
url = microsoft_url(item['Url'])
header = (base/(prefix+'-prefix.bin')).read_bytes()[:208]
if header[:8]!=b'MSWIM\0\0\0': raise ValueError('not a WIM')

def descriptor(data, pos=0):
    raw, offset, original = struct.unpack_from('<QQQ', data, pos)
    return {'size': raw & ((1<<56)-1), 'flags': raw>>56, 'offset': offset, 'original_size': original}

def get_range(offset, size, name):
    if size > 2_000_000:
        raise ValueError('metadata probe exceeds 2 MB cap')
    req = urllib.request.Request(url, headers={'Range': f'bytes={offset}-{offset+size-1}'})
    with urllib.request.urlopen(req, timeout=40) as response:
        if response.status != 206:
            raise ValueError(f'expected HTTP206, got {response.status}')
        expected = f'bytes {offset}-{offset+size-1}/'
        if not response.headers.get('Content-Range', '').startswith(expected):
            raise ValueError('unexpected Content-Range')
        data = response.read(size+1)
    if len(data) != size: raise ValueError('unexpected byte count')
    (base / name).write_bytes(data)
    return data

table_desc = descriptor(header, 48)
xml_desc = descriptor(header, 72)
table = get_range(table_desc['offset'], table_desc['size'], prefix+'-wim-lookup.bin')
xml = get_range(xml_desc['offset'], xml_desc['size'], prefix+'-wim-image.xml')
entries=[]
for p in range(0,len(table),50):
    e = descriptor(table,p)
    e['part'] = struct.unpack_from('<H',table,p+24)[0]
    e['ref_count'] = struct.unpack_from('<I',table,p+26)[0]
    e['sha1'] = table[p+30:p+50].hex()
    entries.append(e)
for i,e in enumerate(entries):
    if e['flags'] & 2:
        data = get_range(e['offset'],e['size'],f'{prefix}-wim-metadata-{i}.bin')
        e['downloaded_metadata'] = True
        e['sha1_match'] = hashlib.sha1(data).hexdigest()==e['sha1']
(base / (prefix+'-wim-resources.json')).write_text(json.dumps(entries,indent=2),encoding='utf-8')
print(json.dumps({'table':table_desc,'xml':xml_desc,'entry_count':len(entries),'metadata_entries':[e for e in entries if e['flags']&2]},indent=2))
print(xml.decode('utf-16'))
