import ast,hashlib,json,pathlib,shutil,subprocess,sys
workspace=pathlib.Path(__file__).resolve().parents[2]
source=pathlib.Path(__file__).resolve().parent
out=workspace/'outputs'/'ClickToDo-实验启动器'
out.mkdir(parents=True,exist_ok=True)
selection={
 'phase2-hook':['capability-hook.js'],
 'phase19-clicktodo':['package-debugging.ps1','clicktodo-support-result-hook.js'],
 'phase21-host-ifeo':['Arm-HostStartupProbe.ps1','HostStartupDebugger.exe','attach-real-hosts.py','host-cpu-hook.js','activate-client.py'],
 'phase23-client-crash':['optional-source-only.js'],
 'phase24-manual-test':['Start-ManualHookSession.ps1','Open-ClickToDo.ps1','Stop-ManualHookSession.ps1','manual-client-debugger.py'],
 'phase26-shell-entry':['native-hotkey-session.py','native-hotkey-registration.js']}
for phase,names in selection.items():
    dest=out/'runtime'/phase;dest.mkdir(parents=True,exist_ok=True)
    for name in names:shutil.copy2(workspace/'work'/phase/name,dest/name)
shutil.copy2(source/'Dispatch.ps1',out/'Dispatch.ps1')
pkg=out/'runtime'/'phase19-clicktodo'/'package-debugging.ps1'
s=pkg.read_text(encoding='utf-8-sig')
s=s.replace('[string]$DebuggerPath\n','[string]$DebuggerPath,\n    [string]$PythonPath\n')
s=s.replace("$debugger = Join-Path", "if($PythonPath){$python=(Resolve-Path -LiteralPath $PythonPath).Path}\n$debugger = Join-Path",1)
pkg.write_text(s,encoding='utf-8-sig')
manual=out/'runtime'/'phase24-manual-test'
client=manual/'manual-client-debugger.py'
s=client.read_text(encoding='utf-8-sig')
ast.parse(s);client.write_text(s,encoding='utf-8')
start=manual/'Start-ManualHookSession.ps1'
s=start.read_text(encoding='utf-8-sig')
windowless=str(pathlib.Path(sys.executable).with_name('pythonw.exe')).replace("'", "''")
s=s.replace("$python='C:\\Users\\jianm\\AppData\\Local\\Programs\\Python\\Python312\\python.exe'", "$python='"+windowless+"'\n$launcher=(Resolve-Path -LiteralPath (Join-Path $root '..\\..\\ClickToDoLauncher.exe')).Path")
a=s.index(" $arm=Join-Path $hostRoot 'Arm-HostStartupProbe.ps1'")
b=s.index(' $deadline=[datetime]::UtcNow.AddSeconds(15)',a)
s=s[:a]+" $controller=Start-Process -FilePath $launcher -Verb RunAs -ArgumentList @('--admin',$label,($DurationSeconds+20)) -WindowStyle Hidden -PassThru\n"+s[b:]
a=s.index(" $hook=Join-Path $hostRoot 'attach-real-hosts.py'")
b=s.index(' $hookReady=Join-Path',a)
s=s[:a]+s[b:]
s=s.replace("  if($hookController.HasExited){throw 'Model hook controller exited early.'}","  if($controller.HasExited){throw 'Elevated model controller exited early.'}")
s=s.replace("-DebuggerPath (Join-Path $root 'manual-client-debugger.py')","-DebuggerPath (Join-Path $root 'manual-client-debugger.py') -PythonPath $python")
# A windowless Python activation helper logs to a file rather than stdout.
s=s.replace(" & $python (Join-Path $hostRoot 'activate-client.py')\n if($LASTEXITCODE -ne 0){throw 'Packaged background activation failed.'}"," $activation=Start-Process -FilePath $python -ArgumentList ('\"'+(Join-Path $hostRoot 'activate-client.py')+'\"') -WindowStyle Hidden -PassThru\n if(-not $activation.WaitForExit(10000) -or $activation.ExitCode -ne 0){throw 'Packaged background activation failed.'}\n Start-Sleep -Seconds 2")
s=s.replace("if($controller.HasExited -or $hookController.HasExited)","if($controller.HasExited)")
start.write_text(s,encoding='utf-8-sig')
activate=out/'runtime'/'phase21-host-ifeo'/'activate-client.py'
s=activate.read_text(encoding='utf-8-sig')
s=s.replace('import ctypes as C,ctypes.wintypes as W,json,uuid','import ctypes as C,ctypes.wintypes as W,json,uuid,pathlib')
s=s.replace(' print(json.dumps(dict(hresult=hex(hr&0xffffffff),pid=pid.value)))'," pathlib.Path(__file__).with_name('last-activation.json').write_text(json.dumps(dict(hresult=hex(hr&0xffffffff),pid=pid.value)),encoding='utf-8')")
ast.parse(s);activate.write_text(s,encoding='utf-8')
# Once warmed, send a single invocation. Do not reset the user's selection ten seconds later.
open_file=manual/'Open-ClickToDo.ps1'
s=open_file.read_text(encoding='utf-8-sig')
s=s[:s.index('# Replay once')]
open_file.write_text(s,encoding='utf-8-sig')
# Tighten cleanup for packaged clients whose Get-Process.Path is unavailable.
arm=out/'runtime'/'phase21-host-ifeo'/'Arm-HostStartupProbe.ps1'
s=arm.read_text(encoding='utf-8-sig')
line=" Get-Process -Name ClickToDo -ErrorAction SilentlyContinue | Where-Object {$_.StartTime.ToUniversalTime() -ge $started -and $_.Path -ieq 'C:\\Windows\\SystemApps\\MicrosoftWindows.Client.CoreAI_cw5n1h2txyewy\\ClickToDo.exe'} | Stop-Process -Force -ErrorAction SilentlyContinue"
assert line in s
s=s.replace(line," $clientTarget='C:\\Windows\\SystemApps\\MicrosoftWindows.Client.CoreAI_cw5n1h2txyewy\\ClickToDo.exe'\n Get-CimInstance Win32_Process -Filter \"Name='ClickToDo.exe'\" | Where-Object {$_.CreationDate.ToUniversalTime() -ge $started -and ($_.ExecutablePath -ieq $clientTarget -or ($_.CommandLine -and $_.CommandLine.StartsWith('\"'+$clientTarget+'\" ',[StringComparison]::OrdinalIgnoreCase)))} | ForEach-Object {Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue}")
arm.write_text(s,encoding='utf-8-sig')
config={'PowerShellExe':sys.argv[1],'PythonWindowlessExe':str(pathlib.Path(sys.executable).with_name('pythonw.exe')),'SessionSeconds':900}
(out/'config.json').write_text(json.dumps(config,ensure_ascii=False,indent=2),encoding='utf-8')
files=[out/'Dispatch.ps1',out/'config.json']+[out/'runtime'/phase/name for phase,names in selection.items() for name in names]
manifest=[{'path':str(p.relative_to(out)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}for p in sorted(files)]
data=json.dumps(manifest,ensure_ascii=False,indent=2).encode('utf-8')
(out/'manifest.json').write_bytes(data)
cs=(source/'Launcher.cs').read_text(encoding='utf-8').replace('__MANIFEST_SHA256__',hashlib.sha256(data).hexdigest())
generated=source/'Launcher.generated.cs';generated.write_text(cs,encoding='utf-8-sig')
compiler=r'C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe'
subprocess.run([compiler,'/nologo','/platform:x64','/target:winexe','/reference:System.Web.Extensions.dll','/reference:System.Windows.Forms.dll','/out:'+str(out/'ClickToDoLauncher.exe'),str(generated)],check=True)
print(json.dumps({'directory':str(out),'frozenFiles':len(manifest),'launcher':str(out/'ClickToDoLauncher.exe')},ensure_ascii=False))
