import re
p = r"C:\Windows\SystemApps\Microsoft.AIFabric.CBS.1.6_8wekyb3d8bbwe\Microsoft.Windows.Workloads.dll"
d = open(p,"rb").read()

# 已知的 CRT 噪音
CRT = set("""bad function call success address family not supported address in use address not available already connected
argument list too long argument out of domain bad address bad file descriptor bad message broken pipe connection aborted
connection already in progress connection refused connection reset cross device link destination address required
device or resource busy directory not empty executable format error file exists file too large filename too long
function not supported host unreachable identifier removed illegal byte sequence inappropriate io control operation
interrupted invalid argument invalid seek io error is a directory message size network down network reset network unreachable
no buffer space no child process no link no lock available no message available no message no protocol option no space on device
no stream resources no such device or address no such device no such file or directory no such process not a directory
not a socket not a stream not connected not enough memory not supported operation canceled operation in progress
operation not permitted operation not supported operation would block owner dead permission denied protocol error
protocol not supported read only file system resource deadlock would occur resource unavailable try again result out of range
state not recoverable stream timeout text file busy timed out too many files open in system too many files open too many links""".split("\n"))

seen=set(); out=[]
for m in re.finditer(rb"[\x20-\x7E]{5,}", d):
    s = m.group(0).decode("ascii","ignore").strip()
    if not s or s in seen: continue
    low = s.lower()
    if low in CRT: continue
    # 排除看起来像机器码的
    if re.match(r'^[A-Z\$\[\]@\^_\\\\\|<>~0-9A-Fa-f\s\.\:\;\,\-\+\*\/\(\)]+$', s) and len(s) < 40: continue
    if len(re.findall(r'[aeiouAEIOU]', s)) < 2: continue
    if len(re.findall(r'[^A-Za-z0-9 \.\-_\\/:]', s)) > len(s)*0.3: continue
    seen.add(s); out.append(s)

print(f"剩余 {len(out)} 条:\n")
for s in out:
    print("   " + s[:180])
