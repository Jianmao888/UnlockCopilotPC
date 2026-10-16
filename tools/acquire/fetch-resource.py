"""Download one exact resource from the two recorded, uncompressed-WIM samples."""
import argparse
import hashlib
import json
import pathlib
import urllib.request

from download_utils import microsoft_url, safe_filename

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--generation', choices=['new', 'old'], default='new')
parser.add_argument('--list', action='store_true')
parser.add_argument('--name')
parser.add_argument('--out', type=pathlib.Path)
parser.add_argument('--max-mib', type=int, default=512)
args = parser.parse_args()
root = pathlib.Path(__file__).resolve().parent
samples = {
    'new': ('msu-payloads.json', 'fe47c57f-a77f-41e3-9012-00b4187e3462', 'Windows11.0-KB5124010-x64.msu'),
    'old': ('oct-msu-payloads.json', '15127f8d-75c8-4150-98d1-5020aa815a35', 'Windows11.0-KB5066835-x64.msu'),
}
index, build, msu_name = samples[args.generation]
rows = json.loads((root / index).read_text(encoding='utf-8-sig'))
if args.list:
    for row in rows:
        if row.get('name') and row.get('size'):
            print(row['name'], row['size'])
    raise SystemExit(0)
if not args.name or not args.out or args.max_mib <= 0:
    parser.error('Specify --name and --out, or use --list')
name = safe_filename(args.name)
matches = [r for r in rows if r.get('name') == name and r.get('size')]
if len(matches) != 1:
    raise SystemExit('Expected exactly one resource in the recorded sample')
row = matches[0]
size, offset = int(row['size']), int(row['offset'])
if size > args.max_mib * 1024 * 1024:
    raise SystemExit('Resource exceeds explicit transfer cap; review size and use --max-mib if intended')
args.out.mkdir(parents=True, exist_ok=True)
target = args.out / name
if target.exists() and hashlib.sha1(target.read_bytes()).hexdigest() == row['sha1']:
    print('Already matches recorded SHA1:', name)
    raise SystemExit(0)
api = 'https://api.uupdump.net/get.php?id=' + build + '&pack=0&edition=0'
with urllib.request.urlopen(api, timeout=45) as response:
    metadata = json.load(response)
files = metadata.get('response', {}).get('files', {})
item = files.get(msu_name)
if not item:
    raise SystemExit('The current index did not return the recorded MSU; inspect API error/version')
# All byte ranges must belong to the same-sized parent used by this index.
parents = json.loads((root / 'sample-parents.json').read_text(encoding='utf-8'))
parent = next(p for p in parents[args.generation] if p['Name'] == msu_name)
if int(item['size']) != int(parent['Size']):
    raise SystemExit('Parent MSU size differs from recorded resource index')
if parent.get('Sha256') and item.get('sha256') and item['sha256'].lower() != parent['Sha256'].lower():
    raise SystemExit('Parent MSU metadata SHA256 differs from recorded sample')
end = offset + size - 1
url = microsoft_url(item['url'])
request = urllib.request.Request(url, headers={'Range': f'bytes={offset}-{end}', 'User-Agent': 'UnlockCopilotPC-research'})
partial = target.with_name(target.name + '.partial')
digest = hashlib.sha1()
with urllib.request.urlopen(request, timeout=60) as response:
    expected_range = f'bytes {offset}-{end}/{item["size"]}'
    if response.status != 206 or response.headers.get('Content-Range') != expected_range:
        raise RuntimeError('Server did not return the exact requested byte range')
    remaining = size
    with partial.open('wb') as output:
        while remaining:
            chunk = response.read(min(1024 * 1024, remaining))
            if not chunk:
                raise RuntimeError('Short resource response')
            output.write(chunk)
            digest.update(chunk)
            remaining -= len(chunk)
        if response.read(1):
            raise RuntimeError('Extra bytes after expected resource')
if digest.hexdigest() != row['sha1']:
    raise RuntimeError('Recorded resource SHA1 mismatch; partial file retained')
partial.replace(target)
print(json.dumps(dict(file=str(target), bytes=size, sha1=digest.hexdigest(),
                      sha256=hashlib.sha256(target.read_bytes()).hexdigest()), ensure_ascii=False))
