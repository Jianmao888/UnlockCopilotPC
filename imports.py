import pefile
DLL = r"C:\Windows\System32\InstallService.dll"
pe = pefile.PE(DLL, fast_load=True)
pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_IMPORT"]])
print("=== InstallService.dll 的网络相关导入 ===")
for e in pe.DIRECTORY_ENTRY_IMPORT:
    n = e.dll.decode()
    if any(k in n.lower() for k in ["winhttp","wininet","urlmon","websocket","http","tls","crypto","bcrypt","schannel","ws2","dnsapi"]):
        funcs = [imp.name.decode() if imp.name else f"ord{imp.ordinal}" for imp in e.imports]
        print(f"\n--- {n} ({len(funcs)} 个) ---")
        for f in funcs[:40]:
            print(f"    {f}")
