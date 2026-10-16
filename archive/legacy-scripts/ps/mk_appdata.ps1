$base = 'C:\ProgramData\Microsoft\Windows\AppRepository\Families'
$appdata = Join-Path $base 'ApplicationData'
$dirs = @(Get-ChildItem 'C:\Program Files\WindowsApps' -Directory -EA SilentlyContinue |
          Where-Object { $_.Name -match '^WindowsWorkload\.' })
$n = 0
foreach ($d in $dirs) {
    $parts = $d.Name -split '_'
    if ($parts.Count -lt 3) { continue }
    $fam = $parts[0] + '_' + $parts[-1]
    $t = Join-Path $appdata "$fam\Machine"
    if (-not (Test-Path $t)) { New-Item -Path $t -ItemType Directory -Force | Out-Null; $n++ }
    $acl = Get-Acl $t
    $rule = New-Object System.Security.AccessControl.FileSystemAccessRule("NT AUTHORITY\LOCAL SERVICE","Modify, ListDirectory","ContainerInherit, ObjectInherit","None","Allow")
    $acl.SetAccessRule($rule)
    Set-Acl -Path $t -AclObject $acl
}
Write-Output ("  created " + $n + " new Machine folders, ACL applied to " + $dirs.Count)
Get-ChildItem $appdata -EA SilentlyContinue | Where-Object { $_.Name -match '^WindowsWorkload' } | Select-Object -First 5 | ForEach-Object { "    " + $_.Name }
