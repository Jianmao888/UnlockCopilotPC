"""Extract two original CABs and assemble pinned installer inputs. Never installs."""
import argparse
import hashlib
import json
import pathlib
import shutil
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from product_layout import REPO, digest, engine_files, verify_rum

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--desktop-cab', required=True, type=pathlib.Path)
parser.add_argument('--aggregate-cab', required=True, type=pathlib.Path)
parser.add_argument('--output', required=True, type=pathlib.Path)
parser.add_argument('--sevenzip', default=shutil.which('7z.exe'))
args = parser.parse_args()
if not args.sevenzip:
    parser.error('Install 7-Zip on PATH or pass --sevenzip')
output = args.output.resolve()
if output.exists():
    parser.error('Output must be a new directory')
index = json.loads((REPO / 'tools/acquire/msu-payloads.json').read_text(encoding='utf-8'))
for source, name in [(args.desktop_cab, 'DesktopDeployment.cab'), (args.aggregate_cab, 'onepackage.AggregatedMetadata.cab')]:
    row = next(r for r in index if r.get('name') == name)
    with source.open('rb') as stream:
        sha = hashlib.file_digest(stream, 'sha1').hexdigest()
    if source.stat().st_size != row['size'] or sha != row['sha1']:
        parser.error('Original CAB does not match the pinned resource: ' + name)
output.mkdir(parents=True)
for source, name in [(args.desktop_cab, 'desktop-expanded'), (args.aggregate_cab, 'aggregate-expanded')]:
    subprocess.run([args.sevenzip, 'x', str(source.resolve()), '-o' + str(output / name), '-y'],
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, timeout=60)
nested = list((output / 'desktop-expanded').rglob('Deployment.cab'))
if len(nested) != 1:
    raise RuntimeError('Expected one nested Deployment.cab inside DesktopDeployment.cab')
subprocess.run([args.sevenzip, 'x', str(nested[0]), '-o' + str(output / 'desktop-expanded' / 'deployment'), '-y'],
               stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, timeout=60)
engine = output / 'engine'
engine.mkdir()
inventory = json.loads((REPO / 'evidence/installer-engine-files.json').read_text(encoding='utf-8'))
for row in inventory:
    if not row['name'].endswith('.dll'):
        continue
    candidates = [p for p in (output / 'desktop-expanded').rglob('*')
                  if p.is_file() and p.name.lower() == row['name'].lower() and p.stat().st_size == row['bytes']]
    match = next((p for p in candidates if digest(p) == row['sha256']), None)
    if match is None:
        raise RuntimeError('Pinned deployment DLL not in this CAB: ' + row['name'])
    shutil.copy2(match, engine / row['name'])
for name in ['device_information.json', 'hardware.installer.json', 'msix.installer.json']:
    shutil.copy2(REPO / 'evidence' / 'installer-config' / name, engine / name)
engine_files(engine)
rums = output / 'rums'
rums.mkdir()
for product in json.loads((REPO / 'evidence/rum-cab-sha256.json').read_text(encoding='utf-8')):
    matches = list((output / 'aggregate-expanded').rglob(product + '.rum.json.cab'))
    if len(matches) != 1:
        raise RuntimeError('Expected one original RUM CAB for ' + product)
    verify_rum(matches[0], product)
    shutil.copy2(matches[0], rums / matches[0].name)
print(json.dumps(dict(engine=str(engine), rums=str(rums), installCalled=False), indent=2))
