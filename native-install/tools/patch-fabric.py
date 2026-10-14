import hashlib
import os
import shutil
import struct
import sys

SRC = r"C:\Windows\System32\WSAIFabricHost.dll"
DST_DIR = r"C:\ProgramData\AiLab"
DST = os.path.join(DST_DIR, "WSAIFabricHost.dll")
EXPECT_SHA = "ea8f782b722161a15c2cc5bcff1407d4844aa972af4bb7bf45b5c0751e486170"
PATCH_OFF = 400087
ORIG_BYTE = 0xE8
NEW_BYTE = 0xE9

report = []

def w(s):
    report.append(s)
    print(s)

os.makedirs(DST_DIR, exist_ok=True)

# 1) copy
if os.path.exists(DST):
    os.remove(DST)
shutil.copy2(SRC, DST)
data = bytearray(open(DST, "rb").read())
w("copied: %s (%d bytes)" % (DST, len(data)))

# 2) verify identity
sha = hashlib.sha256(data).hexdigest()
w("sha256(copy) = %s" % sha)
w("matches expected: %s" % (sha == EXPECT_SHA))
if sha != EXPECT_SHA:
    w("ABORT: source hash mismatch")
    sys.exit(2)

# 3) verify the bytes we intend to patch
before = data[PATCH_OFF - 2:PATCH_OFF + 5]
w("bytes around patch offset: %s" % before.hex(" "))
if data[PATCH_OFF] != ORIG_BYTE:
    w("ABORT: expected 0x%02x at offset %d, found 0x%02x" % (ORIG_BYTE, PATCH_OFF, data[PATCH_OFF]))
    sys.exit(3)

# 4) patch: MOV EDI, 0x3e8 -> MOV EDI, 0x3e9
data[PATCH_OFF] = NEW_BYTE
after = data[PATCH_OFF - 2:PATCH_OFF + 5]
w("patched bytes:             %s" % after.hex(" "))
w("patch applied: %s" % (after[2] == NEW_BYTE))

# 5) recompute PE checksum (field at optional-header offset 0x40, treated as zero)
pe = struct.unpack_from("<I", data, 0x3C)[0]
opt = pe + 24
magic = struct.unpack_from("<H", data, opt)[0]
csum_off = opt + 0x40
old_csum = struct.unpack_from("<I", data, csum_off)[0]
w("pe=0x%x magic=0x%x checksum_field_off=%d old=0x%08x" % (pe, magic, csum_off, old_csum))

tmp = bytearray(data)
tmp[csum_off:csum_off + 4] = b"\x00\x00\x00\x00"
total = 0
n = len(tmp)
for i in range(0, n - 1, 2):
    total += tmp[i] | (tmp[i + 1] << 8)
    total = (total & 0xFFFF) + (total >> 16)
if n % 2:
    total += tmp[n - 1]
    total = (total & 0xFFFF) + (total >> 16)
total = (total & 0xFFFF) + (total >> 16)
total += n
new_csum = total & 0xFFFFFFFF
struct.pack_into("<I", data, csum_off, new_csum)
w("new checksum = 0x%08x" % new_csum)

open(DST, "wb").write(bytes(data))
w("written: %s" % DST)
w("final sha256 = %s" % hashlib.sha256(bytes(data)).hexdigest())
w("DONE")
