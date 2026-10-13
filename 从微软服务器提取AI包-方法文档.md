# 从微软服务器提取 Windows AI 组件包 —— 可复用方法

> 适用：需要研究/分析 Windows 的 `WindowsWorkload.*` AI 模型包，但本机不是 Copilot+ PC，
> Windows Update 不下发这些包的情况。
>
> 本文描述的是一条**从微软官方 CDN 直接取原始签名包**的通道，不需要 Copilot+ 设备，
> 也不需要下载整个累积更新（数 GB）。

---

## 一、核心思路

**这些包不在任何"商店"里，也没有独立下载入口。它们作为载荷内嵌在 Windows 的累积更新（LCU）里。**

```
Windows 累积更新 (LCU, 以 .msu 发布，数 GB)
   └── 内含 WIM 资源
         └── 其中一部分资源 = 完整的 WindowsWorkload.* MSIX 包
```

**关键点：**

1. MSU 的**文件名里没有 AI 包名**（只有 `Windows11.0-KBxxxxxxx-x64.msu` 这类名字）。直接在 UUP 文件清单里搜 `WindowsWorkload` 会**一无所获**。
2. 必须在 **WIM 资源表** 里找内嵌载荷。
3. 微软 CDN **支持 HTTP Range**，可以只取需要的那几 MB 字节，不必下载整个 4.69 GB 的 MSU。
4. 每个载荷在 WIM 资源表里都有 **offset / size / SHA1**，可完整校验。

---

## 二、你需要知道的三种格式

### 2.1 MSU / WIM

本次遇到的两个 LCU 的 `.msu` 文件，**文件头就是 WIM 魔数**：

```
偏移 0    : "MSWIM\0\0\0"
偏移 48   : 资源表描述符（24 字节）
偏移 72   : 映像 XML 描述符（24 字节）
```

**描述符的 24 字节结构：**

```python
raw, offset, original_size = struct.unpack_from('<QQQ', data, pos)
size  = raw & ((1 << 56) - 1)     # 低 56 位 = 大小
flags = raw >> 56                 # 高 8 位  = 标志
```

### 2.2 WIM 资源表

每个资源项 **50 字节**：

```
+0   uint64   size(低56位) | flags(高8位)
+8   uint64   offset            ← 该资源在文件中的绝对偏移
+16  uint64   original_size     （未压缩大小）
+24  uint16   part              分卷号
+26  uint32   ref_count         引用计数
+30  byte[20] SHA1              ← 校验用
```

**`flags & 2` 表示该资源有元数据**，即它是一个"有文件名的文件"。
**`flags & 2 == 0` 表示它是纯数据块**（例如目录元数据本身）。

### 2.3 WIM 目录项（dentry）

元数据块里是目录树。每项：

```
+0   uint64   length            本项总长度
+8   uint32   attributes
+12  uint32   security_id
+16  uint64   subdir_offset     子目录偏移，0 = 无
+64  byte[20] SHA1              ← 用它去资源表里查 offset/size
+96  uint16   streams
+98  uint16   short_name_len
+100 uint16   name_len
+102 wchar[]  name              UTF-16LE
```

**SHA1 是连接"文件名"和"文件字节"的唯一桥梁。**

### 2.4 MSIX

MSIX 就是 ZIP。可以直接用 Python `zipfile` 读：

```python
with zipfile.ZipFile("xxx.msix") as z:
    manifest = z.read("AppxManifest.xml")
    sig      = z.read("AppxSignature.p7x")
    names    = [i.filename for i in z.infolist()]
```

---

## 三、六步流程

```
① 拿更新索引      UUP dump API → MSU 的 CDN URL + SHA256
② 探测文件头      取前 256 KB → 解析 WIM 头 → 拿到资源表描述符
③ 取资源表        按描述符 Range 取回 → 得到所有资源的 offset/size/sha1
④ 取目录元数据    对 flags&2 的项取回 → 解析出 文件名 ↔ SHA1
⑤ 按字节范围取包  对目标 MSIX 发 Range 请求 → 完整 MSIX 字节
⑥ 校验            WIM 资源 SHA1 + Authenticode 签名 + 包内 Identity
```

### 步骤 ① 拿更新索引

UUP dump 提供元数据索引（**只提供元数据，字节来自微软 CDN**）：

```powershell
$ids = @{
  'uup-msu-files.json'     = '<索引 UUID>'
}
foreach ($name in $ids.Keys) {
  $uri = 'https://api.uupdump.net/get.php?id=' + $ids[$name] + '&pack=0&edition=0'
  $metadata = (Invoke-WebRequest -Uri $uri).Content | ConvertFrom-Json -AsHashtable
  $files = @($metadata.response.files.GetEnumerator() |
    Where-Object { $_.Key -match '^Windows11.*msu$' } |
    ForEach-Object { [pscustomobject]@{
        Name=$_.Key; Size=$_.Value.size; Sha256=$_.Value.sha256; Url=$_.Value.url } })
  if ($files.Count -eq 0) { throw '该索引未返回预期 MSU' }
  $files | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $name -Encoding utf8
}
```

产出形如：

```json
[{"Name":"Windows11.0-KB5124010-x64.msu","Size":"4689703377","Sha256":"...","Url":"http://tlu.dl.delivery.mp.microsoft.com/..."}]
```

**CDN URL 有时效**（`P1` 参数是过期时间戳）。失效后重跑本步骤刷新即可。

### 步骤 ② 探测文件头

```python
req = urllib.request.Request(url, headers={'Range': 'bytes=0-262143'})
data = urllib.request.urlopen(req).read()
assert data[:8] == b'MSWIM\0\0\0'
table_desc = descriptor(data, 48)
xml_desc   = descriptor(data, 72)
```

### 步骤 ③ 取资源表

```python
table = get_range(table_desc['offset'], table_desc['size'])
entries = []
for p in range(0, len(table), 50):
    raw, offset, original = struct.unpack_from('<QQQ', table, p)
    entries.append({
        'size': raw & ((1 << 56) - 1), 'flags': raw >> 56,
        'offset': offset, 'original_size': original,
        'part': struct.unpack_from('<H', table, p + 24)[0],
        'ref_count': struct.unpack_from('<I', table, p + 26)[0],
        'sha1': table[p + 30:p + 50].hex(),
    })
```

### 步骤 ④ 取目录元数据，映射文件名

```python
for i, e in enumerate(entries):
    if e['flags'] & 2:                       # 有文件名的资源
        meta = get_range(e['offset'], e['size'])
        assert hashlib.sha1(meta).hexdigest() == e['sha1']   # 顺带校验
        walk_dentries(meta, ...)             # 解析目录树，得到 name ↔ sha1
```

目录树解析（含子目录递归）：

```python
def walk(offset, prefix=''):
    p = offset
    while p + 8 <= len(data):
        length = struct.unpack_from('<Q', data, p)[0]
        if length == 0: break
        if length < 102 or p + length > len(data): raise ValueError('bad dentry')
        attr, sec, sub = struct.unpack_from('<IIQ', data, p + 8)
        sha1 = data[p+64:p+84].hex()
        streams, short_len, name_len = struct.unpack_from('<HHH', data, p + 96)
        name = data[p+102:p+102+name_len].decode('utf-16-le')
        full = (prefix + '/' + name).strip('/')
        if sha1 in by_hash:                  # by_hash: sha1 -> 资源表项
            yield full, by_hash[sha1]
        if sub: walk(sub, full)
        p += length
```

### 步骤 ⑤ 按字节范围取包

```python
def fetch(url, offset, size, target):
    req = urllib.request.Request(url, headers={'Range': f'bytes={offset}-{offset+size-1}'})
    with urllib.request.urlopen(req, timeout=60) as r:
        assert r.status == 206, '必须是 206 Partial Content'
        assert r.headers['Content-Range'].startswith(f'bytes {offset}-{offset+size-1}/')
        with open(target, 'wb') as f:
            remaining = size
            while remaining:
                block = r.read(min(1 << 20, remaining))
                if not block: raise ValueError('unexpected EOF')
                f.write(block); remaining -= len(block)
```

### 步骤 ⑥ 校验（**不可省略**）

```powershell
# 1) WIM 资源 SHA1 —— 在步骤 ⑤ 之后立即比对
# 2) 签名
Get-ChildItem *.msix | ForEach-Object {
  $sig = Get-AuthenticodeSignature -LiteralPath $_.FullName
  [pscustomobject]@{ File=$_.Name; Status=$sig.Status;
                     Signer=$sig.SignerCertificate.Subject;
                     SHA256=(Get-FileHash -LiteralPath $_.FullName).Hash }
}
# 期望: Status = Valid, Signer = CN=Microsoft Corporation
```

```python
# 3) 包内 Identity 与架构
with zipfile.ZipFile(target) as z:
    root = ET.fromstring(z.read("AppxManifest.xml"))
    ident = next(n for n in root if n.tag.endswith("Identity")).attrib
    print(ident['Name'], ident['Version'], ident['ProcessorArchitecture'])
```

---

## 四、特殊情况：载荷文件名是 GUID

某些 LCU 里，AI 包的**文件名是 GUID**（例如 `14847cc3-88d4-0cbf-cfb7-1ab27f06eb15_1.2508.888.0_x64.msix`），
真实身份只存在于包内的 `AppxManifest.xml`。

**问题**：包最大 447 MB，逐个下载不可行。

### 解决：用 zip 中央目录 + HTTP Range，只取几十 KB

**原理**：ZIP 的中央目录在**文件末尾**。标准库 `zipfile` 打开时只需读
End-of-Central-Directory + 中央目录；读某个条目时才去读它的局部头和压缩数据。

**只要给它一个由 HTTP Range 支撑的文件对象，它自己就只会请求必要的字节。**

```python
class HttpRangeFile(io.RawIOBase):
    def __init__(self, url, base, size):
        self.url, self.base, self.size, self.pos = url, base, size, 0

    def seekable(self): return True
    def readable(self): return True
    def tell(self): return self.pos

    def seek(self, off, whence=0):
        if whence == 0:   self.pos = off
        elif whence == 1: self.pos += off
        elif whence == 2: self.pos = self.size + off
        self.pos = max(0, min(self.pos, self.size))
        return self.pos

    def read(self, n=-1):
        n = min(n if (n is not None and n >= 0) else self.size - self.pos,
                self.size - self.pos)
        if n <= 0: return b''
        start = self.base + self.pos
        req = urllib.request.Request(
            self.url, headers={'Range': f'bytes={start}-{start+n-1}'})
        data = urllib.request.urlopen(req, timeout=60).read()
        self.pos += len(data)
        return data

# 用法
with zipfile.ZipFile(HttpRangeFile(url, offset, size)) as z:
    manifest = z.read("AppxManifest.xml")        # 只取了几十 KB
    root = ET.fromstring(manifest)
    ident = next(n for n in root if n.tag.endswith("Identity")).attrib
```

**实测效果：56 个 GUID 命名的包全部识别，总共只取 0.12 MB**
（如果全量下载需 2.18 GB）。

---

## 五、完整工具清单

| 文件 | 作用 | 用法 |
|---|---|---|
| `fetch_all_ai_payloads.py` | 从指定 LCU 批量提取 | `--only <子串>` `--max-size <MB>` `--list` |
| `fetch_legacy_payloads.py` | 从 LCU 按**包名/预设**提取 | `--preset core\|365\|lnl` `--name <包名>` |
| `identify_legacy_packages.py` | **廉价识别 GUID 命名包** | `[--max N]` |
| `coverage.py` | 依赖闭包覆盖度分析 | 直接运行 |
| `inventory.py` | 生成清单 JSON | 直接运行 |
| `check_url.py` | 检查 CDN URL 是否过期 | 直接运行 |

**下载器的必备特性：**

1. **断点续传** —— 写 `.partial`，若已存在则用 `Range: bytes={start+have}-{end}` 续传
2. **SHA1 校验后才 `replace`** —— 校验不通过不产出正式文件
3. **体积上限** —— 防止误下载整个 LCU
4. **主机白名单** —— 只允许 `*.delivery.mp.microsoft.com` / `download.windowsupdate.com` / `download.microsoft.com`
5. **不关闭 TLS 校验**

---

## 六、常见坑

| 坑 | 现象 | 解决 |
|---|---|---|
| **CDN URL 过期** | HTTP 403 / 404 | 重跑步骤 ① 刷新元数据 |
| **在 UUP 文件清单里搜包名** | 一无所获 | AI 包名只在 **WIM 资源表**里 |
| **以为 MSU 是 CAB** | 解析失败 | 本次两个 LCU 的文件头是 **`MSWIM`**，不是 `MSCF` |
| **试图下载完整 MSU** | 浪费 4.69 GB 且慢 | 用 Range 只取需要的 payload |
| **忽略资源 SHA1** | 拿到损坏/截断的包 | 必须逐项比对 |
| **只信文件名** | GUID 名字无法判断身份 | 用中央目录技巧读 manifest |
| **直接用 `zipfile` 打开远程包** | 会下载全量 | 用上面的 `HttpRangeFile` |
| **中央目录在流式响应里找不到** | `BadZipFile` | 确保 `seek` 实现正确、`size` 用资源表的真实大小 |
| **同名不同代的包混用** | 依赖对不上 | 见下面"代际"一节 |

---

## 七、代际问题（重要）

同一组功能会有**多个代际**的包，运行时不兼容，**不能混装**。

判断方法：看 `C:\Windows\SystemApps\Microsoft.AIFabric.CBS.*\workloads*.json` 里
`Packages` 数组引用的运行时名。

| 代 | 运行时 | 典型来源 |
|---|---|---|
| **3.7 代** | `PSOnnxRuntime.<平台>.3.7` + `PSTokenizerShared.<平台>.3.7` | 较早的 LCU（如 KB5066835） |
| **5.2 代** | `WinMLShared.5.2` + `EP.<厂商>.<框架>.Framework.1.8` | 较新的 LCU（如 KB5124010） |

**取包前先读本机 JSON，确认要哪一代。**

### 平台变体

同一功能还有**平台变体**，由**检测到的 NPU 类型**选择（不是 CPU）：

```
Microsoft.Windows.Workloads.dll
  导出 WorkloadManagerLoadWorkloadsUsingBrokerNpuType
    → NPUDetect\npudetect.dll : npudetect_detect_npu()
        → DXCore 枚举适配器，找描述含 "NPU Compute Accelerator Device" 的设备
```

| 平台标记 | 含义 |
|---|---|
| `Lnl` | Intel Lunar Lake |
| `Ptl` | Intel Panther Lake |
| `Stx` | AMD Strix |
| `Qnn` / `J32` | Qualcomm |
| `365` | **Windows 365 云 PC（无 NPU，CPU 路径）** |
| （无后缀） | 通用 |

**包名的平台后缀必须与 `workloads.json` 里的引用一致，否则系统不会认领。**

---

## 八、校验清单（取完后逐项确认）

```
[ ] 每个包的 WIM 资源 SHA1 与资源表一致
[ ] 每个包 Get-AuthenticodeSignature = Valid
[ ] 签名者 = CN=Microsoft Corporation
[ ] 包内 Identity/Name/Version/ProcessorArchitecture 与预期一致
[ ] 依赖闭包完整：对照 workloads*.json 的 Workloads[].Packages 逐项核对
[ ] 没有混淆代际
```

**依赖闭包核对**可直接用 `coverage.py`：它读本机的 `workloads*.json`，
对每个 workload 列出"需要 N / 有 M / 缺 K"，并打印缺失清单。

---

## 九、合规与安全边界

- ✅ **只读取微软官方 CDN 的字节**，不修改、不重打包、不重新签名
- ✅ **不安装到系统**（下载到工作目录即可）
- ✅ **保留原始签名**供独立校验
- ❌ 不要关闭 TLS 校验
- ❌ 不要把载荷主机扩展到微软域名之外
- ❌ 不要绕过更新服务给出的协议（有些投递主机只有 HTTP）
- ⚠️ 包内含微软签名与完整性强制（`<uap10:PackageIntegrity><uap10:Content Enforcement="on"/>`），
  **任何改动都会导致签名失效**

---

## 十、本次实例参数（可直接复现）

| 项 | 值 |
|---|---|
| 目标机 | Windows 26300.9550 (26H2) x64 |
| 新代 LCU | `Windows11.0-KB5124010-x64.msu`，4,689,703,377 字节 |
| 新代索引 ID | `fe47c57f-a77f-41e3-9012-00b4187e3462` |
| 旧代 LCU | `Windows11.0-KB5066835-x64.msu`，3,591,245,399 字节 |
| 旧代索引 ID | `15127f8d-75c8-4150-98d1-5020aa815a35` |
| 新代载荷数 | 53 个 MSIX（1,981.4 MB） |
| 旧代载荷数 | 56 个 MSIX（2.18 GB，其中 24 个已下载，866.0 MB） |

**成果：**

```
77 个原版 MSIX / 2847.5 MB
Valid 77 / 77，签名者 Microsoft Corporation
WIM 资源 SHA1 逐项一致，下载失败 0
```

**依赖闭包完整度（对照本机 workloads*.json）：**

| 平台 | ContentExtraction | Analysis |
|---|---|---|
| 365 | 7/7 缺 0 | 12/12 缺 0 |
| Lnl | 7/7 缺 0 | 12/12 缺 0 |
| Ptl | 7/7 缺 0 | 12/12 缺 0 |

---

## 十一、附：最小可运行示例

> **本段代码已实测通过。** 对 `Windows11.0-KB5124010-x64.msu`（4,689,703,377 字节）运行结果：
> ```
> WIM 头 OK  资源表: offset=4689677202 size=5750
> 资源项: 115
> 共 114 个命名载荷   其中 .msix: 53
> 取到 WindowsWorkload.Data.ContentExtraction.Lnl.1  51003 字节  SHA1 ✓
> Identity: Name=WindowsWorkload.Data.ContentExtraction.Lnl.1
>           Publisher=CN=Microsoft Corporation, ...  Version=1.2608.951.0  Arch=x64
> ```
> 验证脚本：`doc_example_test.py`

把以下内容存成一个 `.py` 文件即可跑通"探测 → 列载荷 → 取一个包"：

```python
import hashlib, io, json, struct, urllib.request, zipfile
import xml.etree.ElementTree as ET

URL  = "<从步骤①拿到的 MSU CDN URL>"
SIZE = 4689703377          # MSU 总大小

def get_range(off, n):
    req = urllib.request.Request(URL, headers={'Range': f'bytes={off}-{off+n-1}'})
    with urllib.request.urlopen(req, timeout=60) as r:
        assert r.status == 206
        return r.read()

def desc(buf, pos):
    raw, off, orig = struct.unpack_from('<QQQ', buf, pos)
    return raw & ((1 << 56) - 1), raw >> 56, off, orig

hdr = get_range(0, 262144)
assert hdr[:8] == b'MSWIM\0\0\0'
t_size, _, t_off, _ = desc(hdr, 48)

table = get_range(t_off, t_size)
res = []
for p in range(0, len(table), 50):
    raw, off, orig = struct.unpack_from('<QQQ', table, p)
    res.append({'size': raw & ((1 << 56) - 1), 'flags': raw >> 56,
                'offset': off, 'sha1': table[p+30:p+50].hex()})

# 取所有带元数据的资源，解析文件名
by_hash = {e['sha1']: e for e in res}
files = {}
for e in res:
    if not (e['flags'] & 2):
        continue
    meta = get_range(e['offset'], e['size'])
    assert hashlib.sha1(meta).hexdigest() == e['sha1']
    root = (struct.unpack_from('<I', meta, 0)[0] + 7) & ~7
    def walk(off, pre=''):
        p = off
        while p + 8 <= len(meta):
            ln = struct.unpack_from('<Q', meta, p)[0]
            if ln == 0 or ln < 102 or p + ln > len(meta): break
            sha1 = meta[p+64:p+84].hex()
            nm_len = struct.unpack_from('<H', meta, p+100)[0]
            name = meta[p+102:p+102+nm_len].decode('utf-16-le')
            full = (pre + '/' + name).strip('/')
            if sha1 in by_hash:
                files[full] = by_hash[sha1]
            sub = struct.unpack_from('<Q', meta, p+16)[0]
            if sub: walk(sub, full)
            p += ln
    walk(root)

print(f"共 {len(files)} 个命名载荷")
for n, e in sorted(files.items()):
    print(f"  {e['size']/1e6:9.2f} MB  {n}")

# 取其中一个
target = next(n for n in files if n.lower().endswith('.msix'))
e = files[target]
data = get_range(e['offset'], e['size'])
assert hashlib.sha1(data).hexdigest() == e['sha1']
open(target.split('/')[-1], 'wb').write(data)

with zipfile.ZipFile(io.BytesIO(data)) as z:
    root = ET.fromstring(z.read('AppxManifest.xml'))
    ident = next(n for n in root if n.tag.endswith('Identity')).attrib
    print('Identity:', ident)
```
