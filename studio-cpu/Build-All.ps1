param([string]$VcToolsRoot,[string]$OpenVinoRoot=(Join-Path $PSScriptRoot 'vendor\openvino'))
$ErrorActionPreference='Stop'
if(-not $VcToolsRoot){
 $vswhere=Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
 if(-not(Test-Path -LiteralPath $vswhere)){throw 'Install MSVC x64 Build Tools and Windows SDK 10.0.26100.0, or pass -VcToolsRoot.'}
 $installation=& $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
 if(-not $installation){throw 'No MSVC x64 installation found'}
 $version=(Get-Content -LiteralPath (Join-Path $installation 'VC\Auxiliary\Build\Microsoft.VCToolsVersion.default.txt') -Raw).Trim()
 $VcToolsRoot=Join-Path $installation ('VC\Tools\MSVC\'+$version)
}
New-Item -ItemType Directory -Path (Join-Path $PSScriptRoot 'payload'),(Join-Path $PSScriptRoot 'tools') -Force | Out-Null
& (Join-Path $PSScriptRoot 'source\Build.ps1') -OpenVinoRoot $OpenVinoRoot -VcToolsRoot $VcToolsRoot
$cl=Join-Path $VcToolsRoot 'bin\Hostx64\x64\cl.exe'
Push-Location $PSScriptRoot
try{
 foreach($name in @('CameraDurationProbe','SoftwareMepNode','StudioSoftwareHost')){
  & $cl /nologo /std:c++17 /EHsc /O2 /MT /DNOMINMAX ('device-host\'+$name+'.cpp') ('/Fe:device-host\'+$name+'.exe')
  if($LASTEXITCODE){throw ('Build failed: '+$name)}
 }
 Copy-Item -LiteralPath 'device-host\CameraDurationProbe.exe','device-host\SoftwareMepNode.exe' -Destination payload -Force
 & (Join-Path $PSScriptRoot 'payload\python\python.exe') -I (Join-Path $PSScriptRoot 'tools\regenerate-tool-manifest.py')
 if($LASTEXITCODE){throw 'Tool manifest generation failed'}
}finally{Pop-Location}
'Build complete. No services installed. Next run Prepare.ps1 to compile models on this CPU.'
