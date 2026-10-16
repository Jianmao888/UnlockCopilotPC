"""Rebuild tracked sources in a new directory from explicitly supplied archives.

Never installs services/products, patches system files, injects, or opens camera.
This is not a clean-OS VM test: the installed compiler/SDK and Windows are shared.
"""
import argparse
import hashlib
import json
import pathlib
import shutil
import subprocess
import sys
import time
import zipfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--destination', required=True, type=pathlib.Path)
parser.add_argument('--runtime-cache', required=True, type=pathlib.Path)
parser.add_argument('--driver-cabs', required=True, type=pathlib.Path)
parser.add_argument('--pwsh', default=shutil.which('pwsh.exe'))
parser.add_argument('--include-staged', action='store_true', help='Maintainer audit: use current Git index instead of HEAD')
parser.add_argument('--engine', type=pathlib.Path)
parser.add_argument('--rum-directory', type=pathlib.Path)
parser.add_argument('--payload-directory', type=pathlib.Path)
args = parser.parse_args()
if not args.pwsh:
    parser.error('Pass --pwsh or install PowerShell 7 on PATH')
repository = pathlib.Path(__file__).resolve().parents[1]
destination = args.destination.resolve()
archive = destination.with_name(destination.name + '.source.zip')
if destination.exists() or archive.exists() or destination.is_relative_to(repository):
    parser.error('Use a new destination outside the repository')
tree = subprocess.check_output(['git', 'write-tree'] if args.include_staged else ['git', 'rev-parse', 'HEAD'],
                               cwd=repository, text=True).strip()
subprocess.run(['git', 'archive', '--format=zip', '--output=' + str(archive), tree], cwd=repository, check=True)
destination.mkdir(parents=True)
with zipfile.ZipFile(archive) as package:
    package.extractall(destination)
logs = destination / 'audit-logs'
logs.mkdir()
report = dict(startedUtc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), gitSource=tree,
              freshTrackedSourceDirectory=True, cleanOperatingSystem=False,
              noSystemInstallHookPatchOrCamera=True, steps=[])


def run(label, command, timeout=240, success=0):
    try:
        result = subprocess.run([str(x) for x in command], cwd=destination,
                                capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired as error:
        (logs / (label + '.stdout.txt')).write_bytes(error.stdout or b'')
        (logs / (label + '.stderr.txt')).write_bytes(error.stderr or b'')
        report['steps'].append(dict(name=label, timedOut=True, timeoutSeconds=timeout))
        raise
    (logs / (label + '.stdout.txt')).write_bytes(result.stdout)
    (logs / (label + '.stderr.txt')).write_bytes(result.stderr)
    report['steps'].append(dict(name=label, exitCode=result.returncode, expected=success))
    print(label, result.returncode, flush=True)
    if result.returncode != success:
        raise RuntimeError('Audit step failed; inspect audit-logs/' + label)
    return result


try:
    run('runtime', [sys.executable, 'studio-cpu/Prepare-Runtime.py', '--offline', '--cache', args.runtime_cache.resolve()])
    run('studio-build', [args.pwsh, '-NoProfile', '-File', 'studio-cpu/Build-All.ps1'])
    cab_dir = destination / 'studio-cpu' / 'downloads'
    cab_dir.mkdir(exist_ok=True)
    for name in ['mep-3.0.8.cab', 'camera-3.0.8.cab', 'mep-1.0.41.cab']:
        shutil.copy2(args.driver_cabs.resolve() / name, cab_dir / name)
    run('studio-prepare', [args.pwsh, '-NoProfile', '-File', 'studio-cpu/Prepare.ps1'])
    stdout = (logs / 'studio-prepare.stdout.txt').read_text(encoding='utf-8', errors='replace')
    for name in ['face101', 'matting109', 'pose113', 'light132']:
        if f'model={name} cpu_inference=passed' not in stdout:
            raise RuntimeError('Missing actual CPU inference confirmation: ' + name)
    embedded = destination / 'studio-cpu' / 'payload' / 'python' / 'python.exe'
    compiler = pathlib.Path(r'C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe')
    run('host-build', [compiler, '/nologo', '/platform:x64', '/target:exe', '/reference:System.Web.Extensions.dll',
                       '/out:' + str(destination / 'work' / 'phase21-host-ifeo' / 'HostStartupDebugger.exe'),
                       destination / 'work' / 'phase21-host-ifeo' / 'HostStartupDebugger.cs'])
    run('launcher-build', [embedded, 'work/phase25-packaged-launcher/build.py', args.pwsh])
    launcher = destination / 'outputs' / 'ClickToDo-实验启动器' / 'ClickToDoLauncher.exe'
    run('launcher-selfcheck', [launcher, '--selfcheck'])
    selfcheck = json.loads((launcher.parent / 'selfcheck.json').read_text(encoding='utf-8-sig'))
    if not all(selfcheck.get(key) for key in ['ManifestValid', 'NoHookStarted', 'PowerShellExists', 'PythonWindowlessExists']):
        raise RuntimeError('Launcher selfcheck incomplete')
    # Parse the generated scripts too: a source parser alone cannot catch builder errors.
    parse_command = "$bad=@();Get-ChildItem -LiteralPath 'outputs','studio-cpu' -Recurse -Filter '*.ps1'|ForEach-Object {$t=$null;$e=$null;[void][Management.Automation.Language.Parser]::ParseFile($_.FullName,[ref]$t,[ref]$e);$bad+=$e};if($bad){throw ($bad|Out-String)}"
    run('generated-powershell-parse', [args.pwsh, '-NoProfile', '-Command', parse_command])
    run('native-result-tests', [args.pwsh, '-NoProfile', '-File', 'tests/Test-DeploymentResult.ps1'])
    if all([args.engine, args.rum_directory, args.payload_directory]):
        product = 'Windows.Workload.ContentExtraction.LNL.amd64'
        content = destination / 'prepared-products' / product
        run('product-layout', [embedded, 'tools/prepare-product.py', '--product', product, '--output', content,
                               '--engine', args.engine.resolve(), '--rum', args.rum_directory.resolve() / (product + '.rum.json.cab'),
                               '--payload-dir', args.payload_directory.resolve()])
        run('install-files-only', [embedded, 'native-install/tools/run_install.py', 'attempt-cold-files', content,
                                   product + '.rum.json.cab', product, '--validate-only'])
        target = next(content.glob('WindowsWorkload.Data.ContentExtraction.*.msix'))
        original = target.read_bytes()
        try:
            changed = bytearray(original)
            changed[-1] ^= 1
            target.write_bytes(changed)
            run('reject-corrupt-payload', [embedded, 'tools/prepare-product.py', '--product', product, '--validate', content], success=1)
        finally:
            target.write_bytes(original)
        run('restored-product-valid', [embedded, 'tools/prepare-product.py', '--product', product, '--validate', content])
        report['productFileRebuildPassed'] = True
    report.update(passed=True, actualCpuModelsInferred=4,
                  note='File/runtime rebuild only; no fresh-system installation or UI/reboot acceptance')
finally:
    report['finishedUtc'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    (destination / 'cold-rebuild-result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print('Cold file rebuild passed:', destination, flush=True)
