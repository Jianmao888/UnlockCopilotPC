param(
    [Parameter(Mandatory=$true)][ValidatePattern('^attempt[0-9a-z\-]+$')][string]$RunName,
    [Parameter(Mandatory=$true)][string]$Source,
    [Parameter(Mandatory=$true)][string]$ExpectedRum,
    [switch]$InstallProduct
)
# Adapted from the verified single-product launcher (phase12-native-install).
# Differences: source dir + expected RUM are parameters; the source hash inventory
# check is dropped (a fresh product directory is built for each product).
$ErrorActionPreference = 'Stop'
$env:UALITE_GLOBAL_LOG_FILE_PATH = Join-Path $PSScriptRoot ('ualite-install-' + $RunName + '.log')
$env:UALITE_LOG_LEVEL = 'debug'
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { throw 'Installation requires an elevated process' }

$rums = @(Get-ChildItem -LiteralPath (Join-Path $Source 'metadata') -File -Filter '*.rum.json.cab')
if ($rums.Count -ne 1 -or $rums[0].Name -ne $ExpectedRum) {
    throw ('Unexpected product scope: found ' + ($rums | ForEach-Object { $_.Name } | Out-String))
}

$events = Join-Path $PSScriptRoot ($RunName + '.events.txt')
if (Test-Path -LiteralPath $events) { throw 'Result prefix already exists' }

Add-Type -Path (Join-Path $PSScriptRoot 'InstallRunner.cs')

$signal = Join-Path $PSScriptRoot ($RunName + '-ready.signal')
$limit = [DateTime]::UtcNow.AddSeconds(60)
while (-not (Test-Path -LiteralPath $signal)) {
    if ([DateTime]::UtcNow -ge $limit) { throw 'Observer did not signal readiness; no install called' }
    Start-Sleep -Milliseconds 100
}

$library = Join-Path $Source 'metadata\ualite.dll'
[Environment]::CurrentDirectory = [IO.Path]::GetDirectoryName($library)
$result = [InstallRunner]::Run($library, $Source, $events, $InstallProduct.IsPresent)
$result | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $PSScriptRoot ($RunName + '.json')) -Encoding utf8
$result | Format-Table -AutoSize
. (Join-Path $PSScriptRoot 'Assert-DeploymentResult.ps1')
Assert-DeploymentResult -Events $result -InstallRequested:$InstallProduct
