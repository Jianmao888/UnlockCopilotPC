"""Use the package's normal Windows.Launch contract, with package identity."""
import ctypes as C,ctypes.wintypes as W,json,uuid
ole=C.WinDLL('ole32');P=C.c_void_p;G=C.c_byte*16
ole.CoInitializeEx.argtypes=[P,W.DWORD];ole.CoInitializeEx.restype=C.c_long
ole.CoCreateInstance.argtypes=[C.POINTER(C.c_byte),P,W.DWORD,C.POINTER(C.c_byte),C.POINTER(P)];ole.CoCreateInstance.restype=C.c_long
hr=ole.CoInitializeEx(None,2)
if hr<0:raise OSError(hex(hr&0xffffffff))
obj=P()
try:
 clsid=G.from_buffer_copy(uuid.UUID('45ba127d-10a8-46ea-8ab7-56ea9078943c').bytes_le)
 iid=G.from_buffer_copy(uuid.UUID('2e941141-7f97-4756-ba1d-9decde894a3d').bytes_le)
 hr=ole.CoCreateInstance(clsid,None,4,iid,C.byref(obj))
 if hr<0:raise OSError('CoCreateInstance '+hex(hr&0xffffffff))
 table=C.cast(obj,C.POINTER(C.POINTER(P))).contents
 activate=C.WINFUNCTYPE(C.c_long,P,W.LPCWSTR,W.LPCWSTR,W.DWORD,C.POINTER(W.DWORD))(table[3])
 pid=W.DWORD();hr=activate(obj,'MicrosoftWindows.Client.CoreAI_cw5n1h2txyewy!ClickToDoApp',None,0,C.byref(pid))
 print(json.dumps(dict(hresult=hex(hr&0xffffffff),pid=pid.value)))
 if hr<0:raise OSError('ActivateApplication '+hex(hr&0xffffffff))
finally:
 if obj.value:
  table=C.cast(obj,C.POINTER(C.POINTER(P))).contents
  C.WINFUNCTYPE(W.ULONG,P)(table[2])(obj)
 ole.CoUninitialize()
