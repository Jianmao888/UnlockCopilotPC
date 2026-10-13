import glob, os, re
from xml.etree import ElementTree as ET
root = r"C:\Users\jianm\OneDrive\文档\ChatGPT\2026-10-12\qing\outputs\Windows-AI-包获取核验"
manifests = glob.glob(os.path.join(root, "**", "*.AppxManifest.xml"), recursive=True)
print(f"找到 {len(manifests)} 份 manifest\n")

NS = {
 'f':'http://schemas.microsoft.com/appx/manifest/foundation/windows10',
 'uap':'http://schemas.microsoft.com/appx/manifest/uap/windows10',
 'rescap':'http://schemas.microsoft.com/appx/manifest/foundation/windows10/restrictedcapabilities',
 'mp':'http://schemas.microsoft.com/appx/2014/phone/manifest',
}
def find(root, path, ns=None):
    try: return root.find(path, NS)
    except Exception: return None

for m in sorted(manifests):
    try:
        t = ET.parse(m); r = t.getroot()
    except Exception as e:
        print(f"--- {os.path.basename(m)} 解析失败: {e}"); continue
    print("="*78)
    print(os.path.basename(m).replace('.AppxManifest.xml',''))
    print("="*78)
    ident = find(r, 'f:Identity')
    if ident is not None:
        print(f"  Identity: Name={ident.get('Name')}")
        print(f"            Publisher={ident.get('Publisher')}")
        print(f"            Version={ident.get('Version')}  Arch={ident.get('ProcessorArchitecture')}")
        print(f"            ResourceId={ident.get('ResourceId')}")
    # 依赖
    deps = find(r, 'f:Dependencies')
    if deps is not None:
        for c in deps:
            tag = c.tag.split('}')[-1]
            if tag == 'TargetDeviceFamily':
                print(f"  TargetDeviceFamily: {c.get('Name')}  Min={c.get('MinVersion')}  MaxTested={c.get('MaxVersionTested')}")
            elif tag == 'PackageDependency':
                print(f"  PackageDependency : {c.get('Name')}  Min={c.get('MinVersion')}")
    # 能力
    caps = find(r, 'f:Capabilities')
    if caps is not None:
        names = [c.get('Name') for c in caps]
        print(f"  Capabilities: {names}")
    # 扩展
    exts = find(r, 'f:Extensions')
    if exts is not None:
        en = [e.tag.split('}')[-1] + (":" + (e.get('Category') or e.get('Name') or '') ) for e in exts]
        print(f"  Extensions: {en[:8]}")
    # uap 属性
    props = find(r, 'f:Properties')
    if props is not None:
        for c in props:
            tag = c.tag.split('}')[-1]
            if tag in ('DisplayName','PublisherDisplayName'):
                print(f"  {tag}: {c.text}")
            else:
                print(f"  {tag}: {c.text if c.text else (c.attrib or '')}")
    print()
