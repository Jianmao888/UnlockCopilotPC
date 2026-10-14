"""Read the previously observed AIComponentManager collection; no guessed component properties or mutators."""
import ctypes,json,pathlib,sys
from ctypes import wintypes as W
root=pathlib.Path(__file__).resolve().parent
result={'hooked':False,'operations':[]}
c=ctypes.WinDLL('combase.dll')
def bind(n,r,a):
 f=getattr(c,n);f.restype=r;f.argtypes=a;return f
init=bind('RoInitialize',ctypes.c_long,[ctypes.c_uint])
uninit=bind('RoUninitialize',None,[])
mkstr=bind('WindowsCreateString',ctypes.c_long,[W.LPCWSTR,ctypes.c_uint,ctypes.POINTER(ctypes.c_void_p)])
delstr=bind('WindowsDeleteString',ctypes.c_long,[ctypes.c_void_p])
rawstr=bind('WindowsGetStringRawBuffer',ctypes.c_void_p,[ctypes.c_void_p,ctypes.POINTER(ctypes.c_uint)])
factory=bind('RoGetActivationFactory',ctypes.c_long,[ctypes.c_void_p,ctypes.c_void_p,ctypes.POINTER(ctypes.c_void_p)])
def check(hr,label):
 result['operations'].append({'operation':label,'hresult':f'0x{hr&0xffffffff:08X}'})
 (root/'component-enumeration-after.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
 if hr<0:raise RuntimeError(label+f': 0x{hr&0xffffffff:08X}')
def slot(p,i):return ctypes.cast(ctypes.cast(p,ctypes.POINTER(ctypes.c_void_p))[0],ctypes.POINTER(ctypes.c_void_p))[i]
def objcall(p,i,*args):
 f=ctypes.WINFUNCTYPE(ctypes.c_long,ctypes.c_void_p,*([ctypes.c_uint32]*len(args)),ctypes.POINTER(ctypes.c_void_p))(slot(p,i))
 out=ctypes.c_void_p();check(f(p,*args,ctypes.byref(out)),f'object slot {i}');return out.value
def stringcall(p,index):
 h=objcall(p,index)
 try:
  length=ctypes.c_uint();address=rawstr(h,ctypes.byref(length))
  return ctypes.wstring_at(address,length.value) if address else ''
 finally:
  if h:delstr(h)
def classname(p):return stringcall(p,4)
refs=[];initialized=False
try:
 hr=init(1);check(hr,'RoInitialize');initialized=True
 h=ctypes.c_void_p();name='Windows.AI.Management.Internal.AIComponentManager'
 check(mkstr(name,len(name),ctypes.byref(h)),'WindowsCreateString')
 try:
  iid=ctypes.create_string_buffer(bytes.fromhex('3500000000000000c000000000000046'),16)
  fac=ctypes.c_void_p();check(factory(h,iid,ctypes.byref(fac)),'RoGetActivationFactory')
 finally:delstr(h)
 refs.append(fac.value)
 # Slot 6 on IActivationFactory is the standard ActivateInstance method.
 manager=objcall(fac.value,6);refs.append(manager)
 result['managerClass']=classname(manager)
 if result['managerClass']!=name:raise RuntimeError('Unexpected manager class')
 # The earlier probe observed this exact method returning the component vector.
 collection=objcall(manager,6);refs.append(collection)
 result['collectionClass']=classname(collection)
 count=ctypes.c_uint()
 fn=ctypes.WINFUNCTYPE(ctypes.c_long,ctypes.c_void_p,ctypes.POINTER(ctypes.c_uint))(slot(collection,7))
 check(fn(collection,ctypes.byref(count)),'component collection get_Size')
 if count.value>100:raise RuntimeError('Implausible component count; stopping')
 result['count']=count.value;result['items']=[]
 kernel=ctypes.WinDLL('kernel32.dll');module=kernel.GetModuleHandleW
 module.argtypes=[W.LPCWSTR];module.restype=ctypes.c_void_p
 base=module('AIComponentMgmt.dll')
 verified={6:0x11760,7:0x11710,8:0x116c0,9:0x11a50,11:0x11670}
 for i in range(count.value):
  component=objcall(collection,6,i);refs.append(component)
  item={'index':i,'runtimeClass':classname(component)}
  if base and all(slot(component,k)==base+v for k,v in verified.items()):
   item['stringsByVerifiedSlot']={str(k):stringcall(component,k) for k in verified}
  else:item['propertyReadSkipped']='Default interface did not match the statically verified string getters'
  result['items'].append(item)
except Exception as e:result['error']=repr(e)
finally:
 for ref in reversed(refs):
  if ref:ctypes.WINFUNCTYPE(ctypes.c_uint,ctypes.c_void_p)(slot(ref,2))(ref)
 if initialized:uninit()
 (root/'component-enumeration-after.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps(result,ensure_ascii=True))
