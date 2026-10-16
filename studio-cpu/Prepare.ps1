param([string]$DriverZip,[string]$DriverDirectory,[string]$LegacyResourceDll)
$ErrorActionPreference='Stop';$ProgressPreference='SilentlyContinue';[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12
if(-not [Environment]::Is64BitProcess -or $env:PROCESSOR_ARCHITECTURE -ne 'AMD64'){throw 'Use 64-bit PowerShell on Windows x64'}
$taskRoot=$PSScriptRoot;$taskDownloads=Join-Path $taskRoot 'downloads';New-Item -ItemType Directory -Path $taskDownloads -Force | Out-Null
function Fetch([string]$Url,[string]$Path,[string]$Base64Sha256){
 $taskDigest=[BitConverter]::ToString([Convert]::FromBase64String($Base64Sha256)).Replace('-','')
 if(-not(Test-Path -LiteralPath $Path) -or (Get-FileHash -LiteralPath $Path).Hash -ne $taskDigest){Write-Host ('Downloading '+$Url);Invoke-WebRequest -UseBasicParsing -Uri $Url -OutFile ($Path+'.partial');if((Get-FileHash -LiteralPath ($Path+'.partial')).Hash -ne $taskDigest){throw 'Download digest mismatch'};Move-Item -LiteralPath ($Path+'.partial') -Destination $Path -Force}
}
function Expand-Cab([string]$Cab,[string]$Destination){New-Item -ItemType Directory -Path $Destination -Force | Out-Null;& expand.exe '-F:*' $Cab $Destination | Out-Null;if($LASTEXITCODE){throw 'CAB extraction failed'}}
if($DriverZip -and $DriverDirectory){throw 'Choose DriverZip or DriverDirectory'}
if($DriverZip){$DriverDirectory=Join-Path $taskDownloads 'provided-drivers';Expand-Archive -LiteralPath (Resolve-Path -LiteralPath $DriverZip).Path -DestinationPath $DriverDirectory -Force}
if(-not $DriverDirectory){
 $DriverDirectory=Join-Path $taskDownloads 'current-drivers';$taskMain=Join-Path $taskDownloads 'mep-3.0.8.cab';$taskCamera=Join-Path $taskDownloads 'camera-3.0.8.cab'
 Fetch 'https://catalog.s.download.windowsupdate.com/d/msdownload/update/driver/drvs/2026/03/e60d5ea8-94e4-43e2-bb4f-1c308736cf5c_5999bc20132c43d300fbffd5e2ea89adc0eca831.cab' $taskMain '1COdGFRGcEkIkzF6OTk88FlHggg2dqmszDg06hnLNXU='
 Fetch 'https://catalog.s.download.windowsupdate.com/c/msdownload/update/driver/drvs/2026/03/aa4c0371-a2ae-4454-92ca-aea0a370d89d_608e83b2a68325d28603f3b69e61ec60fca80504.cab' $taskCamera 's+RtX2sJIt79Nv+MYUmqYbBJKWDz7VhKA+imcGfcDBI='
 Expand-Cab $taskMain (Join-Path $DriverDirectory 'engine');Expand-Cab $taskCamera (Join-Path $DriverDirectory 'camera')
}
$DriverDirectory=(Resolve-Path -LiteralPath $DriverDirectory).Path
$taskChecks=@{'PerceptionCore.dll'='374F9DDCF450B063F98F81B7ACDDD1C94F8977A525B4D82504E7779B44AAD4F9';'PerceptionCoreResources.dll'='9C988E751D0AEBB85FC75DCE3F252AC32DA23C408AC6BF73773D8431B64ECCAA';'ps-onnxruntime.dll'='2BEE89D82184EDEEB2E7EA6DEA43E44D5759D27D2298B39BFCF42C0A5232E9E8';'WindowsEffectsCameraMediaSource.dll'='54D842610391F15602E5C68C4AF3A2D9A1372F2344800EEB30A767567386BC66'}
foreach($taskName in $taskChecks.Keys){$taskCandidates=@(Get-ChildItem -LiteralPath $DriverDirectory -Recurse -File -Filter $taskName | Where-Object {(Get-FileHash -LiteralPath $_.FullName).Hash -eq $taskChecks[$taskName]});if($taskCandidates.Count -ne 1){throw ('Exactly one matching original binary required: '+$taskName)}}
if(-not $LegacyResourceDll){$taskLegacy=Join-Path $taskDownloads 'mep-1.0.41.cab';Fetch 'https://catalog.s.download.windowsupdate.com/d/msdownload/update/driver/drvs/2025/07/fe45b46b-0058-4b63-83ab-95099f0f888d_53f47aa95d2434992bf401d324413b64a99b64b7.cab' $taskLegacy 'wZAzVJ6bfVIMXlkVop35mny2CZBKn5UeDoecHyRNOKs=';Expand-Cab $taskLegacy (Join-Path $taskDownloads 'legacy');$LegacyResourceDll=Join-Path $taskDownloads 'legacy\PerceptionCoreResources.dll'}
$LegacyResourceDll=(Resolve-Path -LiteralPath $LegacyResourceDll).Path
if((Get-AuthenticodeSignature -LiteralPath $LegacyResourceDll).Status -ne 'Valid'){throw 'Legacy resource DLL signature invalid'}
& (Join-Path $taskRoot 'payload\python\python.exe') -I (Join-Path $taskRoot 'tools\PrepareModels.py') $taskRoot $LegacyResourceDll
if($LASTEXITCODE){throw 'CPU model compilation or numerical smoke test failed'}
$taskCpu=@(Get-CimInstance Win32_Processor | Select-Object Name,ProcessorId,AddressWidth)
[pscustomobject]@{driverDirectory=$DriverDirectory;legacyResourceDll=$LegacyResourceDll;cpu=$taskCpu;prepared=(Get-Date).ToString('o');architecture=$env:PROCESSOR_ARCHITECTURE} | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $taskRoot 'prepared.json') -Encoding utf8
'Prepared. Close camera applications, then run Setup.ps1 as administrator.'
