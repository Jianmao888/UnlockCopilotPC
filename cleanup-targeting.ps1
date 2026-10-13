# cleanup-targeting.ps1 - remove the two experimental product registration keys
$base = 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Update\TargetingInfo\DynamicInstalled'
$out = @()
$id = [Security.Principal.WindowsIdentity]::GetCurrent()
$out += "Running as: $($id.Name)"
$out += "IsAdmin: $((New-Object Security.Principal.WindowsPrincipal($id)).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator))"
$out += "Base path: $base"
$out += "Base exists: $(Test-Path $base)"
foreach ($n in 'Windows.Workload.ContentExtraction.amd64', 'Windows.Workload.Analysis.amd64') {
    $p = Join-Path $base $n
    try {
        if (Test-Path $p) {
            Remove-ItemProperty -Path $p -Name 'TestWrite' -Force -ErrorAction SilentlyContinue
            Remove-Item -LiteralPath $p -Recurse -Force -ErrorAction Stop
            $out += "REMOVED: $n"
        } else {
            $out += "ABSENT : $n"
        }
    } catch {
        $out += "FAILED : $n -> $($_.Exception.Message)"
    }
}
$out += "--- DynamicInstalled now contains ---"
$out += (Get-ChildItem $base -ErrorAction SilentlyContinue | Select-Object -ExpandProperty PSChildName)
$out -join "`n"
