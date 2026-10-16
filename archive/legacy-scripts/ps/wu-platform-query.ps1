# wu-platform-query.ps1 - ASCII only
# Bounded WU query sweep: platform-specific product names, a few criteria only.
# Total searches: 3 products x 3 criteria x 2 services = 18, each capped by a job timeout.
$ErrorActionPreference = 'Continue'

$SVC = [ordered]@{
  'fe2cr' = '9482f4b4-e343-43b6-b170-9a65bc822c77'
  'fe3cr' = '8b24b027-1dee-babb-9a95-3517dfb9c552'
}

$PRODUCTS = @(
  'Windows.Workload.ContentExtraction.amd64',      # baseline: what the system asks for
  'Windows.Workload.ContentExtraction.LNL.amd64',  # platform-specific (we have these packages)
  'Windows.Workload.ContentExtraction.365.amd64'
)

$CRITERIA = @(
  "(Product='%P%')",
  "(Product='%P%' and IsInstalled=0)",
  "(Product='%P%' and IsInstalled=1)"
)

$rows = @()
$idx = 0
foreach ($sn in $SVC.Keys) {
  $sid = $SVC[$sn]
  foreach ($p in $PRODUCTS) {
    foreach ($ct in $CRITERIA) {
      $idx++
      $crit = $ct.Replace('%P%', $p)
      $line = ("[{0,2}] {1} | {2}" -f $idx, $sn, $crit)
      Write-Output $line

      # run each search in a job with a hard 25s cap
      $job = Start-Job -ArgumentList $sn, $sid, $crit -ScriptBlock {
        param($sn, $sid, $crit)
        try {
          $session = New-Object -ComObject Microsoft.Update.Session
          $searcher = $session.CreateUpdateSearcher()
          $searcher.ServerSelection = 3
          $searcher.ServiceID = $sid
          $r = $searcher.Search($crit)
          $titles = @()
          for ($i = 0; $i -lt $r.Updates.Count; $i++) { $titles += $r.Updates.Item($i).Title }
          [pscustomobject]@{ ok=$true; rc=$r.ResultCode; count=$r.Updates.Count; titles=($titles -join ' ;; ') }
        } catch {
          [pscustomobject]@{ ok=$false; rc='EXC'; count=-1; titles=$_.Exception.Message.Split([Environment]::NewLine)[0] }
        }
      }
      $done = Wait-Job $job -Timeout 25
      if (-not $done) {
        Stop-Job $job -EA SilentlyContinue
        Write-Output "        TIMEOUT (25s)"
        $rows += [pscustomobject]@{ svc=$sn; product=$p; criteria=$crit; rc='TIMEOUT'; count=-1; titles='' }
      } else {
        $r = Receive-Job $job -EA SilentlyContinue
        Remove-Job $job -Force -EA SilentlyContinue
        if ($r) {
          Write-Output ("        rc={0} count={1}" -f $r.rc, $r.count)
          if ($r.count -gt 0) { Write-Output ("        >>> " + $r.titles.Substring(0,[Math]::Min(300,$r.titles.Length))) }
          $rows += [pscustomobject]@{ svc=$sn; product=$p; criteria=$crit; rc=$r.rc; count=$r.count; titles=$r.titles }
        } else {
          $rows += [pscustomobject]@{ svc=$sn; product=$p; criteria=$crit; rc='NODATA'; count=-1; titles='' }
        }
      }
    }
  }
}

Write-Output ""
Write-Output "############ SUMMARY ############"
$rows | Format-Table svc, product, rc, count -AutoSize
$hit = @($rows | Where-Object { $_.count -gt 0 })
Write-Output ("non-zero results: " + $hit.Count)
$rows | ConvertTo-Json -Depth 4 | Out-File 'C:\Users\jianm\Code\DeepseekHarness\wu-platform-query.json' -Encoding utf8
Write-Output "DONE"
