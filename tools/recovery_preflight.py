"""Read-only target compatibility report. Never loads target DLLs or opens camera."""
import argparse
import hashlib
import json
import os
import pathlib
import platform

CTD = {
    r'C:\Windows\SystemApps\MicrosoftWindows.Client.CoreAI_cw5n1h2txyewy\ClickToDo.exe': '6f709cb5e0b3506dcda250ae3ee27d67f25153a7f8db33f6173c7a3c4c889961',
    r'C:\Windows\SystemApps\MicrosoftWindows.Client.CoreAI_cw5n1h2txyewy\DiscoveryOverlay.dll': '0196208387b97bcd0ef59b3cc7782af941cc53e258ddaa6644fee6eb0fc6d37d',
    r'C:\Windows\SystemApps\Microsoft.WindowsAppRuntime.CBS_8wekyb3d8bbwe\Microsoft.Windows.Workloads.dll': '19d6f9fb8cdf32caa522d887bd2023a1a03886ade0d09cc0ce7dead85e6850c4',
    r'C:\Windows\System32\WSAIFabricHost.dll': 'dbe0d2a3a7f314f8764deef43354af19dd73ffd660d086a792ce37e4f7ca7717',
    r'C:\Windows\explorer.exe': '34ac55b23b6d840cc9fa8304c0149b8bb026d817b39610728092878d634a61eb',
    r'C:\Program Files\WindowsApps\WindowsWorkload.Manager.1_1.2511.1196.0_x64__8wekyb3d8bbwe\WorkloadsSessionHost.exe': '14ba0122022b54681cbf8f90ecc5566e48aabeb98537b5fd1b1befedbc68c6d8',
    r'C:\Program Files\WindowsApps\WindowsWorkload.WinMLShared.5.2_1.2608.951.0_x64__8wekyb3d8bbwe\cacheapi.dll': '671de69b81da93bd2ce3e5cd6048a9a398f68dda7ef62112461dd01a43c6a8cd',
    r'C:\Program Files\WindowsApps\WindowsWorkload.ScrRegDetection.Lnl.1_1.2608.951.0_x64__8wekyb3d8bbwe\srdapi.dll': 'fe2049fb2da34080fed109661b940b1612a47bbbfee6c2649fb3ac1f536ba440',
}
ORIGINAL_FABRIC = 'ea8f782b722161a15c2cc5bcff1407d4844aa972af4bb7bf45b5c0751e486170'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=pathlib.Path)
    args = parser.parse_args()
    rows = []
    for name, expected in CTD.items():
        path = pathlib.Path(name)
        row = dict(path=name, expected=expected)
        try:
            with path.open('rb') as stream:
                actual = hashlib.file_digest(stream, 'sha256').hexdigest()
            row.update(actual=actual, matches=actual == expected)
            if name.endswith('WSAIFabricHost.dll') and actual == ORIGINAL_FABRIC:
                row['reason'] = 'Matching original: LNL routing patch is absent, not a newly unknown binary'
        except OSError as error:
            row.update(matches=False, error=str(error))
        rows.append(row)
    report = dict(platform=platform.platform(), architecture=os.environ.get('PROCESSOR_ARCHITECTURE'),
                  clickToDoPinnedFilesMatch=all(r['matches'] for r in rows), files=rows,
                  note='A matching file set is necessary, not proof of products, device readiness or UI success',
                  systemChanges=False)
    encoded = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(encoded, encoding='utf-8')
    print(encoded)
    return 0 if report['clickToDoPinnedFilesMatch'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
