import json, pathlib, struct, urllib.request, sys
from download_utils import microsoft_url

base = pathlib.Path(__file__).parent
files_name = sys.argv[1] if len(sys.argv)>1 else 'uup-msu-files.json'
prefix = sys.argv[2] if len(sys.argv)>2 else 'msu'
files = json.loads((base / files_name).read_text(encoding='utf-8-sig'))
item = max(files, key=lambda e: int(e['Size']))
url = microsoft_url(item['Url'])
req = urllib.request.Request(url, headers={'Range': 'bytes=0-262143'})
with urllib.request.urlopen(req, timeout=40) as response:
    data = response.read(262144)
    status = response.status
    headers = dict(response.headers)
if status != 206 or not headers.get('Content-Range', '').startswith('bytes 0-262143/'):
    raise ValueError('Unexpected HTTP byte-range response')
if len(data) != 262144:raise ValueError('Unexpected prefix byte count')
(base / (prefix+'-prefix.bin')).write_bytes(data)
info = {'file': item['Name'], 'total_size': item['Size'], 'status': status, 'headers': headers, 'prefix_length': len(data), 'magic': data[:8].hex()}
if data[:4] == b'MSCF':
    cabinet_size, files_offset = struct.unpack_from('<I4xI', data, 8)
    folder_count, file_count, flags = struct.unpack_from('<HHH', data, 26)
    info.update(cabinet_size=cabinet_size, files_offset=files_offset, folder_count=folder_count, file_count=file_count, flags=flags)
    p = files_offset
    entries = []
    for _ in range(file_count):
        if p + 16 >= len(data): break
        file_size, folder_offset, folder_index, date, time, attrs = struct.unpack_from('<IIHHHH', data, p)
        end = data.find(b'\0', p + 16)
        if end < 0: break
        name = data[p+16:end].decode('utf-8', 'replace')
        entries.append(dict(name=name, size=file_size, offset=folder_offset, folder_index=folder_index))
        p = end + 1
    info['entries'] = entries
(base / (prefix+'-prefix-info.json')).write_text(json.dumps(info, indent=2), encoding='utf-8')
print(json.dumps(info, indent=2))
