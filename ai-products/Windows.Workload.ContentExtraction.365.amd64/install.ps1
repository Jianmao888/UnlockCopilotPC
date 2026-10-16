# Windows.Workload.ContentExtraction.365.amd64 -- prepare-only package; run ELEVATED, one install at a time
param([Parameter(Mandatory=$true)][string]$RunName)
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
& 'C:\Users\jianm\AppData\Local\Programs\Python\Python312\python.exe' -u `
   'C:\Users\jianm\Code\DeepseekHarness\native-install\tools\run_install.py' `
   $RunName $here 'Windows.Workload.ContentExtraction.365.amd64.rum.json.cab' 'Windows.Workload.ContentExtraction.365'
