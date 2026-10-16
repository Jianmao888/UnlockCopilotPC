param(
    [Parameter(Mandatory=$true)][ValidateSet('Enable','Disable')][string]$Action,
    [string]$DebuggerPath
)

$ErrorActionPreference = 'Stop'
$packageFullName = 'MicrosoftWindows.Client.CoreAI_1000.26100.9549.0_x64__cw5n1h2txyewy'
$python = 'C:\Users\jianm\AppData\Local\Programs\Python\Python312\python.exe'
$debugger = Join-Path $PSScriptRoot 'package-debugger.py'
if($DebuggerPath){$debugger=(Resolve-Path -LiteralPath $DebuggerPath).Path}

if (-not ('CodexPackageDebugInvoker' -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;

[ComImport, Guid("B1AEC16F-2383-4852-B0E9-8F0B1DC66B4D")]
public class CodexPackageDebugSettingsClass { }

public static class CodexPackageDebugInvoker {
    [UnmanagedFunctionPointer(CallingConvention.StdCall, CharSet = CharSet.Unicode)]
    private delegate int EnableDelegate(IntPtr self, string packageFullName, string debuggerCommandLine, IntPtr environment);
    [UnmanagedFunctionPointer(CallingConvention.StdCall, CharSet = CharSet.Unicode)]
    private delegate int DisableDelegate(IntPtr self, string packageFullName);

    public static int Enable(IntPtr self, string packageFullName, string debuggerCommandLine) {
        IntPtr table = Marshal.ReadIntPtr(self);
        IntPtr method = Marshal.ReadIntPtr(table, 3 * IntPtr.Size);
        return Marshal.GetDelegateForFunctionPointer<EnableDelegate>(method)(self, packageFullName, debuggerCommandLine, IntPtr.Zero);
    }
    public static int Disable(IntPtr self, string packageFullName) {
        IntPtr table = Marshal.ReadIntPtr(self);
        IntPtr method = Marshal.ReadIntPtr(table, 4 * IntPtr.Size);
        return Marshal.GetDelegateForFunctionPointer<DisableDelegate>(method)(self, packageFullName);
    }
}
'@
}

$rawSettings = [Activator]::CreateInstance([type][CodexPackageDebugSettingsClass])
$unknown = [Runtime.InteropServices.Marshal]::GetIUnknownForObject($rawSettings)
$settings = [IntPtr]::Zero
try {
    $iid = [Guid]'F27C3930-8029-4AD1-94E3-3DBA417810C1'
    $queryResult = [Runtime.InteropServices.Marshal]::QueryInterface($unknown, [ref]$iid, [ref]$settings)
    if ($queryResult -lt 0) { throw ('QueryInterface failed with HRESULT 0x{0:X8}' -f ($queryResult -band 0xffffffff)) }
    if ($Action -eq 'Enable') {
        $commandLine = '"' + $python + '" "' + $debugger + '"'
        $hr = [CodexPackageDebugInvoker]::Enable($settings, $packageFullName, $commandLine)
    } else {
        $hr = [CodexPackageDebugInvoker]::Disable($settings, $packageFullName)
    }
    '{0}: HRESULT=0x{1:X8}; package={2}' -f $Action, ($hr -band 0xffffffff), $packageFullName
    if ($hr -lt 0) { throw ('PackageDebugSettings failed with HRESULT 0x{0:X8}' -f ($hr -band 0xffffffff)) }
} finally {
    if ($settings -ne [IntPtr]::Zero) { [void][Runtime.InteropServices.Marshal]::Release($settings) }
    [void][Runtime.InteropServices.Marshal]::Release($unknown)
    if ($rawSettings -and [Runtime.InteropServices.Marshal]::IsComObject($rawSettings)) {
        [void][Runtime.InteropServices.Marshal]::ReleaseComObject($rawSettings)
    }
}
