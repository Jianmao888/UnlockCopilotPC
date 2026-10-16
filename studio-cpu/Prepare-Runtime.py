"""Prepare isolated runtime/build inputs only. No services, camera or injection.

Use --offline with a cache containing the three runtime-lock.json archives.
Only Python standard library is needed to run this bootstrapper on Windows x64.
"""
import argparse
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import urllib.request
import zipfile


def sha256(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def extract(source, destination):
    destination.mkdir(parents=True, exist_ok=True)
    boundary = destination.resolve()
    with zipfile.ZipFile(source) as archive:
        for member in archive.infolist():
            relative = pathlib.PurePosixPath(member.filename)
            if relative.is_absolute() or '..' in relative.parts or '\\' in member.filename or ':' in member.filename:
                raise ValueError('Unexpected archive path')
            if not (destination / member.filename).resolve().is_relative_to(boundary):
                raise ValueError('Archive member outside destination')
        archive.extractall(destination)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache', type=pathlib.Path)
    parser.add_argument('--offline', action='store_true')
    args = parser.parse_args()
    if os.name != 'nt' or os.environ.get('PROCESSOR_ARCHITECTURE') != 'AMD64':
        parser.error('Run with x64 Python on Windows x64')
    root = pathlib.Path(__file__).resolve().parent
    cache = args.cache.resolve() if args.cache else root / 'downloads' / 'runtime'
    cache.mkdir(parents=True, exist_ok=True)
    rows = json.loads((root / 'runtime-lock.json').read_text(encoding='utf-8-sig'))
    paths = {}
    for row in rows:
        path = cache / row['file']
        valid = path.is_file() and path.stat().st_size == row['bytes'] and sha256(path) == row['sha256']
        if not valid:
            if args.offline:
                raise RuntimeError('Missing or invalid offline archive: ' + str(path))
            partial = path.with_name(path.name + '.partial')
            with urllib.request.urlopen(row['url'], timeout=60) as response, partial.open('wb') as output:
                count = 0
                while chunk := response.read(1024 * 1024):
                    count += len(chunk)
                    if count > row['bytes']:
                        raise ValueError('Download exceeds locked size')
                    output.write(chunk)
            if partial.stat().st_size != row['bytes'] or sha256(partial) != row['sha256']:
                raise ValueError('Downloaded archive does not match lock: ' + row['file'])
            partial.replace(path)
        paths[row['role']] = path
        print('verified', row['file'], flush=True)
    python = root / 'payload' / 'python'
    extract(paths['python'], python)
    extract(paths['frida'], python / 'Lib' / 'site-packages')
    (python / 'python312._pth').write_text('python312.zip\n.\nLib\\site-packages\nimport site\n', encoding='utf-8')
    vendor = root / 'vendor'
    extract(paths['openvino'], vendor)
    ov = vendor / 'openvino'
    libs = ov / 'libs'
    if not (ov / 'include' / 'openvino' / 'openvino.hpp').is_file() or not (libs / 'openvino.lib').is_file():
        raise RuntimeError('Locked wheel did not supply required C++ SDK')
    cpu = root / 'payload' / 'cpu-runtime'
    tools = root / 'tools'
    cpu.mkdir(parents=True, exist_ok=True)
    runtime_files = ['openvino_intel_cpu_plugin.dll', 'openvino_ir_frontend.dll', 'tbb12.dll', 'tbbmalloc.dll', 'tbbbind_2_5.dll']
    for name in runtime_files:
        shutil.copy2(libs / name, cpu / name)
    # Do not place the CPU plugin beside ModelBuilder/openvino.dll: Core would
    # auto-register it before our explicit registration from cpu-runtime.
    for name in ['openvino.dll', *[n for n in runtime_files if n != 'openvino_intel_cpu_plugin.dll']]:
        shutil.copy2(libs / name, tools / name)
    # ModelBuilder is built /MD; its adjacent VC runtime must be available.
    vc_files = ['msvcp140.dll', 'vcruntime140.dll', 'vcruntime140_1.dll']
    for name in vc_files:
        source = pathlib.Path(os.environ['WINDIR']) / 'System32' / name
        if not source.is_file():
            raise RuntimeError('Install Microsoft VC++ x64 redistributable first; missing ' + name)
        shutil.copy2(source, tools / name)
    subprocess.run([str(python / 'python.exe'), '-I', '-c',
                    'import frida; assert frida.__version__ == "17.23.3"; print("isolated_frida=passed")'], check=True)
    subprocess.run([str(python / 'python.exe'), '-I', str(tools / 'restore-context-templates.py')], check=True)
    print('runtime_preparation=passed; no system changes; next run Build-All.ps1')


if __name__ == '__main__':
    main()
