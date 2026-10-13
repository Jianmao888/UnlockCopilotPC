import pefile
pe = pefile.PE(r"C:\Windows\System32\InstallService.dll", fast_load=True)
pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_IMPORT"]])
print("=== InstallService.dll 全部导入 DLL ===")
for e in pe.DIRECTORY_ENTRY_IMPORT:
    n = e.dll.decode()
    flag = ""
    if any(k in n.lower() for k in ["wuapi","wuaueng","wuau","update","rpc","ole32","combase","winhttp"]):
        flag = "   <<<< 关键"
    print(f"  {n}  ({len(e.imports)}){flag}")
