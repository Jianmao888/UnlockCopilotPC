# deploy-365-workloads.ps1 - ASCII only
# 1) install every MSIX needed by the three satisfiable 365 workloads
# 2) build a minimal workloads.json containing only those workloads
$ErrorActionPreference = 'Continue'

$pkgRoots = @('C:\Users\jianm\Code\DeepseekHarness\ai-packages',
              'C:\Users\jianm\Downloads\Windows-AI-包',
              'C:\Users\jianm\Code\DeepseekHarness\ai-packages-legacy')
$base = 'C:\Windows\SystemApps\Microsoft.AIFabric.CBS.1.6_8wekyb3d8bbwe'
$gen  = Join-Path $base 'workloads.json'
$backup = Join-Path $base 'workloads.json.orig-backup'

# --- required families (three complete 365 workloads) ---
$required = @(
  'WindowsWorkload.Data.Analysis.365.1',
  'WindowsWorkload.Data.ContentExtraction.365.1',
  'WindowsWorkload.Data.ImageSearch.365.1',
  'WindowsWorkload.ImageSearch.365.3',
  'WindowsWorkload.ImageTextSearch.365.3',
  'WindowsWorkload.Manager.1',
  'WindowsWorkload.PSOnnxRuntime.365.3.7',
  'WindowsWorkload.PSTokenizer.365.2.7',
  'WindowsWorkload.PSTokenizerShared.365.3.7',
  'WindowsWorkload.QueryProcessor.365.1',
  'WindowsWorkload.ScrRegDetection.365.1',
  'WindowsWorkload.SemanticText.365.1',
  'WindowsWorkload.SessionManager.1',
  'WindowsWorkload.TextRecognition.365.1'
)

Write-Output "=== locate MSIX for each required family ==="
$toInstall = @()
foreach ($fam in $required) {
    $found = $null
    foreach ($r in $pkgRoots) {
        if (-not (Test-Path $r)) { continue }
        $cands = @(Get-ChildItem $r -Recurse -Filter ($fam + '_*.msix') -EA SilentlyContinue |
                   Sort-Object Length -Descending)
        if ($cands.Count -gt 0) { $found = $cands[0]; break }
    }
    if ($found) {
        $toInstall += $found
        Write-Output ("  ok   " + $fam + "  <- " + $found.Name)
    } else {
        Write-Output ("  MISS " + $fam)
    }
}

Write-Output ""
Write-Output "=== install (Add-AppxPackage -ForceApplicationShutdown) ==="
foreach ($f in $toInstall) {
    try {
        Add-AppxPackage -Path $f.FullName -ForceApplicationShutdown -ErrorAction Stop
        Write-Output ("  installed " + $f.Name)
    } catch {
        Write-Output ("  FAILED    " + $f.Name + " : " + $_.Exception.Message.Split([Environment]::NewLine)[0])
    }
}

Write-Output ""
Write-Output "=== build minimal workloads.json (only satisfiable workloads) ==="
$buildPy = @'
import json, os, sys
base = r"C:\Windows\SystemApps\Microsoft.AIFabric.CBS.1.6_8wekyb3d8bbwe"
v = json.load(open(os.path.join(base,"workloads.365.json"), encoding="utf-8-sig"))
keep = {"Windows.Workload.Analysis.365","Windows.Workload.ContentExtraction.365","Windows.Workload.ImageSearch.365"}
wl = [w for w in v["Workloads"] if w.get("Id") in keep]
# keep ApiInfos whose Workload is in keep
ai = [a for a in v.get("ApiInfos",[]) if a.get("Workload") in keep]
# Packages: union of families referenced by kept workloads + kept ApiInfos SessionPackage
fams = set()
for w in wl:
    for p in w.get("Packages",[]):
        fams.add(p["FamilyName"])
for a in ai:
    sp = a.get("SessionPackage")
    if sp: fams.add(sp)
# carry over Version from original Packages list
vermap = {}
for p in v.get("Packages",[]):
    vermap.setdefault(p["FamilyName"], p.get("Version"))
pkgs = []
for f in sorted(fams):
    e = {"FamilyName": f}
    if vermap.get(f): e["Version"] = vermap[f]
    pkgs.append(e)
out = {"Packages": pkgs, "Workloads": wl, "ApiInfos": ai}
dst = os.path.join(base, "workloads.json")
open(dst,"w",encoding="utf-8").write(json.dumps(out, indent=2))
print(f"  wrote {dst}")
print(f"  Packages={len(pkgs)} Workloads={len(wl)} ApiInfos={len(ai)}")
for w in wl: print("    workload: " + w["Id"])
for a in ai: print("    api: " + str(a.get("ApiClassName")))
'@
$buildPy | Out-File -Encoding utf8 "$env:TEMP\build_min.py"
if (-not (Test-Path $backup)) { Copy-Item $gen $backup -Force; Write-Output "  original backed up" }
& takeown.exe /f "$base" /r /d Y 2>&1 | Out-Null
& icacls.exe "$gen" /grant "*S-1-5-32-544:F" 2>&1 | Out-Null
python "$env:TEMP\build_min.py"

Write-Output ""
Write-Output "=== restart WSAIFabricSvc ==="
try { Restart-Service WSAIFabricSvc -Force -ErrorAction Stop; Write-Output "  restarted" } catch { Write-Output ("  " + $_.Exception.Message) }
Start-Sleep -Seconds 15
Get-Service WSAIFabricSvc | ForEach-Object { "  " + $_.Name + " = " + $_.Status }
Write-Output "DONE"
