param([Parameter(Mandatory=$true)][string]$OpenVinoRoot,[Parameter(Mandatory=$true)][string]$VcToolsRoot,[string]$SdkRoot=(Join-Path ${env:ProgramFiles(x86)} 'Windows Kits\10'))
$ErrorActionPreference='Stop'
$taskVc=$VcToolsRoot
$taskSdk=$SdkRoot
$env:INCLUDE="$taskVc\include;$taskSdk\Include\10.0.26100.0\ucrt;$taskSdk\Include\10.0.26100.0\um;$taskSdk\Include\10.0.26100.0\shared"
$env:LIB="$taskVc\lib\x64;$taskSdk\Lib\10.0.26100.0\ucrt\x64;$taskSdk\Lib\10.0.26100.0\um\x64"
$taskRelease=Split-Path $PSScriptRoot
Push-Location $taskRelease
try{
 & "$taskVc\bin\Hostx64\x64\cl.exe" /nologo /std:c++17 /EHsc /W4 /O2 /MT source\StudioCpuService.cpp /Fe:payload\StudioCpuService.exe;if($LASTEXITCODE){throw 'Compilation failed'}
 $taskOv=$OpenVinoRoot
 New-Item -ItemType Directory -Path tools -Force | Out-Null
 & "$taskVc\bin\Hostx64\x64\cl.exe" /nologo /std:c++17 /EHsc /W4 /O2 /MD /I "$taskOv\include" source\ModelBuilder.cpp /Fe:tools\ModelBuilder.exe /link /LIBPATH:"$taskOv\libs" openvino.lib
 if($LASTEXITCODE){throw 'Model builder compilation failed'}
 foreach($taskFile in @('openvino.dll','openvino_ir_frontend.dll','tbb12.dll')){Copy-Item -LiteralPath (Join-Path "$taskOv\libs" $taskFile) -Destination tools -Force}
}finally{Pop-Location}
