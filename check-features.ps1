# check-features.ps1 - ASCII only
$ErrorActionPreference = 'Continue'

Write-Output "=== 1. all enabled features with 'AI' / 'Recall' / 'Copilot' in the name ==="
$feat = @(Get-WindowsOptionalFeature -Online -EA SilentlyContinue)
Write-Output ("  total features: " + $feat.Count)
$hit = @($feat | Where-Object { $_.FeatureName -match 'Recall|Copilot|AI|Intelligence|MachineLearning|ONNX|Workload' })
Write-Output ("  matched: " + $hit.Count)
$hit | Select-Object FeatureName, State | Sort-Object FeatureName | Format-Table -AutoSize

Write-Output ""
Write-Output "=== 2. full feature list (names only, sorted) ==="
$feat | Select-Object -ExpandProperty FeatureName | Sort-Object | ForEach-Object { "  " + $_ }

Write-Output ""
Write-Output "=== 3. look for Recall / AI in the CBS package store ==="
$cbs = @()
$cbs += @(Get-ChildItem 'C:\Windows\servicing\Packages' -Filter '*.mum' -EA SilentlyContinue |
          Where-Object { $_.Name -match 'Recall|Copilot|AIComponent|Workload|MachineLearning|ONNX|Intelligence' })
Write-Output ("  matching .mum files: " + $cbs.Count)
$cbs | Select-Object -First 40 | ForEach-Object { "  " + $_.Name }

Write-Output ""
Write-Output "=== 4. WinSxS components matching ==="
$sxs = @(Get-ChildItem 'C:\Windows\WinSxS' -Directory -EA SilentlyContinue |
         Where-Object { $_.Name -match 'recall|copilot|aicomponent|workload|machinelearning|onnx' })
Write-Output ("  matching WinSxS dirs: " + $sxs.Count)
$sxs | Select-Object -First 30 | ForEach-Object { "  " + $_.Name }
Write-Output "DONE"
