"""Hash only our three locally compiled device-host utilities, never driver DLLs."""
import hashlib
import json
import pathlib

root = pathlib.Path(__file__).resolve().parents[1] / 'device-host'
rows = []
for name in ['CameraDurationProbe.exe', 'SoftwareMepNode.exe', 'StudioSoftwareHost.exe']:
    rows.append(dict(Name=name, SHA256=hashlib.sha256((root / name).read_bytes()).hexdigest().upper()))
(root / 'binaries.json').write_text(json.dumps(rows, indent=2), encoding='utf-8')
print('Wrote hashes for three locally compiled device-host utilities')
