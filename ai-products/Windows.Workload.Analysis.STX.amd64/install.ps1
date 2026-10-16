# Portable single-product entry: planning by default; -Install opts into native Install.
param([Parameter(Mandatory=$true)][string]$RunName,[switch]$Install,[string]$PythonPath='python.exe',[string]$PowerShellPath)
$ErrorActionPreference='Stop'
$repo=Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$launcher=Join-Path $repo 'native-install\tools\run_install.py'
$product='Windows.Workload.Analysis.STX.amd64'
$arguments=@($RunName,$PSScriptRoot,($product+'.rum.json.cab'),$product)
if($Install){$arguments+='--install'}else{$arguments+='--plan-only'}
if($PowerShellPath){$arguments+=@('--pwsh',$PowerShellPath)}
& $PythonPath -u $launcher @arguments
if($LASTEXITCODE){throw ('Product operation failed: '+$LASTEXITCODE)}
