"""Pure file validation and materialization for the pinned RUM samples.

No AppX APIs, registry, elevation, network, DLL loading or package installation.
Authenticode remains a separate Windows check; hashes/Identity are checked here.
"""
import base64
import hashlib
import json
import pathlib
import shutil
import xml.etree.ElementTree as ET
import zipfile

REPO = pathlib.Path(__file__).resolve().parents[1]


def digest(path):
    with pathlib.Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def filename(value):
    if not value or pathlib.PureWindowsPath(value).name != value or any(c in value for c in ':\\/'):
        raise ValueError('Unsafe payload name: ' + value)
    return value


def definition(product):
    filename(product)
    path = REPO / 'evidence' / 'rum-definitions' / (product + '.rum.json')
    products = json.loads(path.read_text(encoding='utf-8-sig'))['UpdateProduct']
    if len(products) != 1 or products[0]['ProductIdentifier'] + '.' + products[0]['ProductArchitecture'] != product:
        raise ValueError('Unexpected product definition')
    rows = {}
    for entity in products[0]['UpdateEntityCollection']:
        full_names = entity['EntityProperties']['PackageFullName']
        for payload in entity['EntityPayload']['Canonical']:
            name = filename(payload['PayloadName'])
            item = dict(name=name, bytes=int(payload['PayloadSize']),
                        sha256=base64.b64decode(payload['SHA256'], validate=True).hex(),
                        version=payload['PayloadVersion'], fullNames=full_names)
            if name in rows and rows[name] != item:
                raise ValueError('Conflicting canonical payload definitions')
            rows[name] = item
    return list(rows.values())


def verify_msix(path, row):
    path = pathlib.Path(path)
    if path.stat().st_size != row['bytes'] or digest(path) != row['sha256']:
        raise ValueError('Payload hash/size mismatch: ' + path.name)
    with zipfile.ZipFile(path) as package:
        identity = ET.fromstring(package.read('AppxManifest.xml')).find('{*}Identity')
    if identity is None or identity.get('Version') != row['version'] or identity.get('ProcessorArchitecture') != 'x64':
        raise ValueError('MSIX Identity version/architecture mismatch: ' + path.name)
    if not any(full.startswith(identity.get('Name') + '_' + row['version'] + '_x64_') for full in row['fullNames']):
        raise ValueError('MSIX Identity name mismatch: ' + path.name)
    return dict(identity.attrib)


def engine_files(directory):
    directory = pathlib.Path(directory)
    inventory = json.loads((REPO / 'evidence' / 'installer-engine-files.json').read_text(encoding='utf-8'))
    files = []
    for row in inventory:
        if not row['name'].endswith('.dll'):
            continue
        path = directory / row['name']
        if not path.is_file() or path.stat().st_size != row['bytes'] or digest(path) != row['sha256']:
            raise ValueError('Missing or mismatched deployment engine DLL: ' + row['name'])
        files.append(path)
    for name in ['device_information.json', 'hardware.installer.json', 'msix.installer.json']:
        path = directory / name
        expected = REPO / 'evidence' / 'installer-config' / name
        if not path.is_file() or json.loads(path.read_text(encoding='utf-8-sig')) != json.loads(expected.read_text(encoding='utf-8-sig')):
            raise ValueError('Deployment configuration differs: ' + name)
        files.append(path)
    return files


def verify_rum(path, product):
    row = json.loads((REPO / 'evidence' / 'rum-cab-sha256.json').read_text(encoding='utf-8'))[product]
    path = pathlib.Path(path)
    if path.name != product + '.rum.json.cab' or path.stat().st_size != row['bytes'] or digest(path) != row['sha256']:
        raise ValueError('Original RUM CAB differs from pinned sample: ' + str(path))


def validate_content(directory, product):
    directory = pathlib.Path(directory).resolve(strict=True)
    metadata = directory / 'metadata'
    rums = list(metadata.glob('*.rum.json.cab'))
    if len(rums) != 1:
        raise ValueError('Exactly one product RUM CAB is required')
    verify_rum(rums[0], product)
    engines = engine_files(metadata)
    rows = definition(product)
    for row in rows:
        verify_msix(directory / row['name'], row)
    return dict(product=product, source=str(directory), payloads=len(rows), engineFiles=len(engines),
                contentValidated=True, signatureCheckStillRequired=True, installCalled=False)


def materialize(directory, product, engine, rum, payload_directories):
    directory = pathlib.Path(directory).resolve()
    if directory.exists():
        raise ValueError('Output must be a new directory; never overwrite existing product contents')
    engines = engine_files(engine)
    verify_rum(rum, product)
    rows = definition(product)
    inputs = []
    for row in rows:
        choices = [pathlib.Path(folder) / row['name'] for folder in payload_directories]
        selected = next((p for p in choices if p.is_file() and p.stat().st_size == row['bytes'] and digest(p) == row['sha256']), None)
        if selected is None:
            raise ValueError('No exact canonical payload found: ' + row['name'])
        verify_msix(selected, row)
        inputs.append(selected)
    # No output directory is created until all inputs validate.
    metadata = directory / 'metadata'
    metadata.mkdir(parents=True)
    for path in engines:
        shutil.copy2(path, metadata / path.name)
    shutil.copy2(rum, metadata / pathlib.Path(rum).name)
    for path in inputs:
        shutil.copy2(path, directory / path.name)
    result = validate_content(directory, product)
    (directory / 'content-validation.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    return result
