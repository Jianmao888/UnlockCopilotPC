"""Restore four small EPContext metadata shells, not compiled model weights."""
import base64
import hashlib
import json
import pathlib

root = pathlib.Path(__file__).resolve().parent
target = root / 'templates'
target.mkdir(exist_ok=True)
for row in json.loads((root / 'context-templates.json').read_text(encoding='utf-8')):
    if pathlib.PurePath(row['name']).name != row['name'] or not row['name'].endswith('.onnx'):
        raise ValueError('Unexpected template filename')
    data = base64.b64decode(row['base64'], validate=True)
    if len(data) != row['bytes'] or hashlib.sha256(data).hexdigest() != row['sha256']:
        raise ValueError('Template digest mismatch')
    (target / row['name']).write_bytes(data)
print('Restored four verified metadata templates')
