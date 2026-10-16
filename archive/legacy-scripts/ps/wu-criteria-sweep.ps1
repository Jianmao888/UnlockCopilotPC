# wu-criteria-sweep.ps1 - ASCII only
# For the platform-specific product names, sweep several search criteria.
$ErrorActionPreference = 'Continue'

$SVC = @{
  'fe2cr' = '9482f4b4-e343-43b6-b170-9a65bc822c77'
  'fe3cr' = '8b24b027-1dee-babb-9a95-3517dfb9c552'
}

$PRODUCTS = @(
  'Windows.Workload.ContentExtraction.LNL.amd64',
  'Windows.Workload.ContentExtraction.365.amd64',
  'Windows.Workload.Analysis.365.amd64',
  'Windows.Workload.ImageSearch.365.amd64',
  'Windows.Workload.ContentExtraction.amd64',
  'Client.OS.rs2.amd64'
)

function Crit($p) { return @(
  "(Product='$p')",
  "(Product='$p' and IsInstalled=0)",
  "(Product='$p' and IsInstalled=1)",
  "(Product='$p' and DeploymentAction=*)",
  "(Product='$p' and IsInstalled=0 and DeploymentAction=*)",
  "(Product='$p' and IsInstalled=1 and DeploymentAction=*)",
  "(Product='$p' and Type='Software')",
  "(Product='$p' and IsAssigned=1)",
  "(Product='$p' and BrowseOnly=1)",
  "(Product='$p' and IsPresent=1)"
) }

$rows = @()
foreach ($sn in $SVC.Keys) {
  $sid = $SVC[$sn]
  Write-Output ""
  Write-Output ("######## " + $sn + "  " + $sid)
  foreach ($p in $PRODUCTS) {
    Write-Output ("   --- " + $p)
    foreach ($c in (Crit $p)) {
      try {
        $session = New-Object -ComObject Microsoft.Update.Session
        $searcher = $session.CreateUpdateSearcher()
        $searcher.ServerSelection = 3
        $searcher.ServiceID = $sid
        $r = $searcher.Search($c)
        $cnt = $r.Updates.Count
        $titles = @()
        for ($i = 0; $i -lt $cnt; $i++) { $titles += $r.Updates.Item($i).Title }
        $rows += [pscustomobject]@{ svc=$sn; product=$p; criteria=$c; rc=$r.ResultCode; count=$cnt; titles=($titles -join ' ;; ') }
        $mark = if ($cnt -gt 0) { "  <<<<<< FOUND" } else { "" }
        Write-Output ("        rc={0} count={1}{2}" -f $r.ResultCode, $cnt, $mark)
        if ($cnt -gt 0) { Write-Output ("        " + ($titles -join ' | ')) }
      } catch {
        $rows += [pscustomobject]@{ svc=$sn; product=$p; criteria=$c; rc='EXC'; count=-1; titles=$_.Exception.Message.Split([Environment]::NewLine)[0] }
        Write-Output ("        EXC " + $_.Exception.Message.Split([Environment]::NewLine)[0])
      }
    }
  }
}

Write-Output ""
Write-Output "######## SUMMARY: any non-zero counts ########"
$hit = @($rows | Where-Object { $_.count -gt 0 })
if ($hit.Count -eq 0) { Write-Output "  (none)" } else { $hit | Format-Table svc,product,criteria,rc,count -AutoSize }
$rows | ConvertTo-Json -Depth 4 | Out-File 'C:\Users\jianm\Code\DeepseekHarness\wu-criteria-sweep.json' -Encoding utf8
Write-Output "saved wu-criteria-sweep.json"
Write-Output "DONE"
