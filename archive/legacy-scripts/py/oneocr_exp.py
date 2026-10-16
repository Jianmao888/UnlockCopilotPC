import zipfile, glob, os, struct, re
BASE = r"C:\Users\jianm\Downloads\Windows-AI-包"
f = glob.glob(os.path.join(BASE,"**","*TextRecognition.365.1_1.2508*.msix"), recursive=True)[0]
out = r"C:\Users\jianm\Code\DeepseekHarness\oneocr-extract"
os.makedirs(out, exist_ok=True)
with zipfile.ZipFile(f) as z:
    for n in ("oneocr.dll","onnxruntime.dll","TextRecognitionSession.dll","oneocr.onemodel"):
        if n in z.namelist():
            data = z.read(n)
            open(os.path.join(out,n),"wb").write(data)
            print(f"  提取 {n}  {len(data)/1e6:.2f} MB")

p = os.path.join(out,"oneocr.dll")
d = open(p,"rb").read()
print(f"\n=== oneocr.dll 导出表解析 ===")
# PE 头
pe = struct.unpack_from('<I', d, 0x3C)[0]
assert d[pe:pe+4] == b'PE\0\0'
nsec = struct.unpack_from('<H', d, pe+6)[0]
optsz = struct.unpack_from('<H', d, pe+20)[0]
opt = pe+24
magic = struct.unpack_from('<H', d, opt)[0]
print(f"  PE32+ magic = 0x{magic:04x}")
ddoff = opt + (112 if magic==0x20b else 96)
exp_rva, exp_sz = struct.unpack_from('<II', d, ddoff)
print(f"  导出目录 RVA=0x{exp_rva:x} size={exp_sz}")
secoff = opt + optsz
secs=[]
for i in range(nsec):
    o = secoff + i*40
    name = d[o:o+8].rstrip(b'\0').decode('ascii','ignore')
    vsz, va, rsz, ra = struct.unpack_from('<IIII', d, o+8)
    secs.append((name,va,vsz,ra,rsz))
def rva2off(rva):
    for n,va,vsz,ra,rsz in secs:
        if va <= rva < va+max(vsz,rsz): return ra + (rva-va)
    return None
eo = rva2off(exp_rva)
nfun, nnam = struct.unpack_from('<II', d, eo+20)
anames = struct.unpack_from('<I', d, eo+32)[0]
aoff = rva2off(anames)
print(f"  导出函数 {nfun} 个，命名 {nnam} 个")
print("  --- 导出名（前 60）---")
names=[]
for i in range(nnam):
    nr = struct.unpack_from('<I', d, aoff+i*4)[0]
    no = rva2off(nr)
    e = d.find(b'\0', no)
    names.append(d[no:e].decode('ascii','ignore'))
for n in names[:60]: print("     " + n)
