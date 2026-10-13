#!/usr/bin/env python3
"""doc_example_test.py — 验证方法文档第十一节的示例代码可运行"""
import hashlib, io, json, pathlib, struct, urllib.request, zipfile
import xml.etree.ElementTree as ET

SRC = pathlib.Path(r"C:\Users\jianm\OneDrive\文档\ChatGPT\2026-10-12\qing\outputs\Windows-AI-包获取核验\提取工具")
items = json.loads((SRC / "uup-msu-files.json").read_text(encoding="utf-8-sig"))
src = max(items, key=lambda x: int(x["Size"]))
URL = src["Url"]
SIZE = int(src["Size"])
print(f"MSU: {src['Name']}  {SIZE} 字节\n")


def get_range(off, n):
    req = urllib.request.Request(URL, headers={'Range': f'bytes={off}-{off+n-1}'})
    with urllib.request.urlopen(req, timeout=60) as r:
        assert r.status == 206, r.status
        return r.read()


def desc(buf, pos):
    raw, off, orig = struct.unpack_from('<QQQ', buf, pos)
    return raw & ((1 << 56) - 1), raw >> 56, off, orig


hdr = get_range(0, 262144)
assert hdr[:8] == b'MSWIM\0\0\0'
t_size, _, t_off, _ = desc(hdr, 48)
print(f"WIM 头 OK  资源表: offset={t_off} size={t_size}")

table = get_range(t_off, t_size)
res = []
for p in range(0, len(table), 50):
    raw, off, orig = struct.unpack_from('<QQQ', table, p)
    res.append({'size': raw & ((1 << 56) - 1), 'flags': raw >> 56,
                'offset': off, 'sha1': table[p+30:p+50].hex()})
print(f"资源项: {len(res)}")

by_hash = {e['sha1']: e for e in res}
files = {}
for e in res:
    if not (e['flags'] & 2):
        continue
    meta = get_range(e['offset'], e['size'])
    assert hashlib.sha1(meta).hexdigest() == e['sha1']
    root = (struct.unpack_from('<I', meta, 0)[0] + 7) & ~7
    def walk(off, pre=''):
        p = off
        while p + 8 <= len(meta):
            ln = struct.unpack_from('<Q', meta, p)[0]
            if ln == 0 or ln < 102 or p + ln > len(meta):
                break
            sha1 = meta[p+64:p+84].hex()
            nm_len = struct.unpack_from('<H', meta, p+100)[0]
            name = meta[p+102:p+102+nm_len].decode('utf-16-le')
            full = (pre + '/' + name).strip('/')
            if sha1 in by_hash:
                files[full] = by_hash[sha1]
            sub = struct.unpack_from('<Q', meta, p+16)[0]
            if sub:
                walk(sub, full)
            p += ln
    walk(root)

print(f"共 {len(files)} 个命名载荷")
msix = [n for n in files if n.lower().endswith('.msix')]
print(f"其中 .msix: {len(msix)}")
for n in sorted(msix)[:6]:
    print(f"  {files[n]['size']/1e6:9.2f} MB  {n}")

target = sorted(msix, key=lambda n: files[n]['size'])[0]
e = files[target]
data = get_range(e['offset'], e['size'])
assert hashlib.sha1(data).hexdigest() == e['sha1'], "SHA1 不匹配"
print(f"\n取到 {target}  {len(data)} 字节  SHA1 ✓")

with zipfile.ZipFile(io.BytesIO(data)) as z:
    root = ET.fromstring(z.read('AppxManifest.xml'))
    ident = next(n for n in root if n.tag.endswith('Identity')).attrib
    print('Identity:', ident)
print("\n✅ 文档示例代码验证通过")
