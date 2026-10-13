# check-recall.ps1 - ASCII only
$ErrorActionPreference = 'Continue'

Write-Output "=== 1. state distribution of all features ==="
$feat = @(Get-WindowsOptionalFeature -Online -EA SilentlyContinue)
$feat | Group-Object State | Sort-Object Count -Descending | ForEach-Object {
    Write-Output ("  {0,-32} {1,4}" -f $_.Name, $_.Count)
}

Write-Output ""
Write-Output "=== 2. Recall feature detail ==="
$r = Get-WindowsOptionalFeature -Online -FeatureName Recall -EA SilentlyContinue
if ($r) {
    $r | Format-List * | Out-String | Write-Output
} else { Write-Output "  (not returned)" }

Write-Output ""
Write-Output "=== 3. features in DisabledWithPayloadRemoved (all) ==="
$feat | Where-Object { $_.State -eq 'DisabledWithPayloadRemoved' } |
    Select-Object -ExpandProperty FeatureName | Sort-Object | ForEach-Object { "  " + $_ }

Write-Output ""
Write-Output "=== 4. CBS .mum files matching Recall / AI ==="
$mum = @(Get-ChildItem 'C:\Windows\servicing\Packages' -Filter '*.mum' -EA SilentlyContinue |
         Where-Object { $_.Name -match 'Recall|AIComponent|Workload|Intelligence|MachineLearning' })
Write-Output ("  matching: " + $mum.Count)
$mum | Select-Object -First 30 | ForEach-Object { "  " + $_.Name }

Write-Output ""
Write-Output "=== 5. WinSxS components matching Recall / AIComponent ==="
$sxs = @(Get-ChildItem 'C:\Windows\WinSxS' -Directory -EA SilentlyContinue |
         Where-Object { $_.Name -match 'recall|aicomponent|workload|intelligence' })
Write-Output ("  matching: " + $sxs.Count)
$sxs | Select-Object -First 30 | ForEach-Object { "  " + $_.Name }
Write-Output "DONE"
