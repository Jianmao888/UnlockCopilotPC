import glob, os
from xml.etree import ElementTree as ET
root = r"C:\Users\jianm\OneDrive\文档\ChatGPT\2026-10-12\qing\outputs\Windows-AI-包获取核验"
mans = glob.glob(os.path.join(root, "**", "*.AppxManifest.xml"), recursive=True)

target = [m for m in mans if "TextRecognition.Lnl.1_1.2608" in m]
if target:
    print("="*80)
    print("完整 manifest:", os.path.basename(target[0]))
    print("="*80)
    print(open(target[0], encoding="utf-8", errors="replace").read())
