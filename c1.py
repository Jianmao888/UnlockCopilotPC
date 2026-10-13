import zipfile, glob, os, re
BASE = r"C:\Users\jianm\Downloads\Windows-AI-包"
f = glob.glob(os.path.join(BASE,"**","*TextRecognition.365.1_1.2508*.msix"), recursive=True)
if f:
    with zipfile.ZipFile(f[0]) as z:
        items = sorted(((i.filename,i.file_size) for i in z.infolist() if not i.is_dir()), key=lambda x:-x[1])
        for n,s in items[:12]:
            print(f"  {s/1e6:9.3f} MB  {n}")
