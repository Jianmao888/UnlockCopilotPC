# wu-query-products.ps1 - ASCII only
# Run the SAME WU search criteria that EnsureReadyAsync uses, but vary the product name.
# Baseline: (Product='Windows.Workload.ContentExtraction.amd64' and IsInstalled=0 and DeploymentAction=*)
$ErrorActionPreference = 'Continue'

# WU service IDs observed in the ETW trace
$SERVICES = @{
  'fe2cr_MicrosoftUpdate' = '9482f4b4-e343-43b6-b170-9a65bc822c77'
  'fe3cr_ThirdParty'      = '8b24b027-1dee-babb-9a95-3517dfb9c552'
}

$PRODUCTS = @(
  # the exact name the system asks for
  'Windows.Workload.ContentExtraction.amd64',
  # platform variants that we actually possess packages for
  'Windows.Workload.ContentExtraction.LNL.amd64',
  'Windows.Workload.ContentExtraction.365.amd64',
  'Windows.Workload.ContentExtraction.Lnl.amd64',
  # other workload families (generic vs platform) for comparison
  'Windows.Workload.Analysis.amd64',
  'Windows.Workload.Analysis.365.amd64',
  'Windows.Workload.ImageSearch.365.amd64',
  # control: obviously fake
  'ZZZ.NotAReal.Product.amd64',
  # control: a real OS product we know exists
  'Client.OS.rs2.amd64'
)

function Try-Search($svcName, $svcId, $product) {
    $crit = "(Product='$product' and IsInstalled=0 and DeploymentAction=*)"
    $res = [ordered]@{ service = $svcName; product = $product; criteria = $crit }
    try {
        $session = New-Object -ComObject Microsoft.Update.Session
        $searcher = $session.CreateUpdateSearcher()
        if ($svcId) { $searcher.ServerSelection = 3; $searcher.ServiceID = $svcId }
        $r = $searcher.Search($crit)
        $res['resultCode'] = $r.ResultCode
        $res['count'] = $r.Updates.Count
        $names = @()
        for ($i = 0; $i -lt $r.Updates.Count; $i++) {
            $u = $r.Updates.Item($i)
            $names += ($u.Title + " [id=" + $u.Identity.UpdateID + " rev=" + $u.Identity.RevisionNumber + "]")
        }
        $res['titles'] = ($names -join ' ;; ')
        $res['hr'] = '0x00000000'
    } catch {
        $res['resultCode'] = 'EXC'
        $res['count'] = -1
        $res['titles'] = ''
        $res['hr'] = $_.Exception.Message.Split([Environment]::NewLine)[0]
    }
    return [pscustomobject]$res
}

$all = @()
foreach ($s in $SERVICES.Keys) {
    Write-Output ""
    Write-Output ("################ service = " + $s + "  {" + $SERVICES[$s] + "}")
    foreach ($p in $PRODUCTS) {
        $r = Try-Search $s $SERVICES[$s] $p
        $all += $r
        Write-Output ("  count={0,4}  hr={1}" -f $r.count, $r.hr)
        Write-Output ("        product = " + $p)
        if ($r.titles) { Write-Output ("        titles  = " + $r.titles.Substring(0, [Math]::Min(300, $r.titles.Length))) }
    }
}

Write-Output ""
Write-Output "################ 汇总 ################"
$all | Format-Table service, product, count, resultCode -AutoSize
$all | ConvertTo-Json -Depth 4 | Out-File 'C:\Users\jianm\Code\DeepseekHarness\wu-query-products.json' -Encoding utf8
Write-Output "saved wu-query-products.json"
Write-Output "DONE"
