#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <swdevice.h>
#include <cfgmgr32.h>
#include <cstdio>
#include <string>
#include <vector>
#include <algorithm>
#include <mutex>
#pragma comment(lib,"swdevice.lib")
#pragma comment(lib,"cfgmgr32.lib")
#pragma comment(lib,"advapi32.lib")
static const WCHAR* ServiceName=L"CodexStudioSoftwareHostV2";
static const WCHAR* LegacyId=L"ROOT\\MEP_CAM_VEN_8086_DEV_B03E\\0000";
static const GUID EffectsCategory={0x1d813233,0x9cde,0x42bf,{0xb4,0x46,0x8f,0x47,0x06,0x7b,0x49,0x46}};
static HANDLE StopEvent=nullptr;static SERVICE_STATUS_HANDLE StatusHandle=nullptr;static bool Console=false;
static std::wstring Directory,Ini;static std::mutex OutputMutex;
static void Log(const char* event,DWORD code=0){
 std::lock_guard<std::mutex> guard(OutputMutex);SYSTEMTIME t;GetSystemTime(&t);FILE* f=nullptr;
 _wfopen_s(&f,(Directory+L"\\host.log").c_str(),L"a");
 if(f){fprintf(f,"%04u-%02u-%02uT%02u:%02u:%02uZ event=%s code=%lu pid=%lu\n",t.wYear,t.wMonth,t.wDay,t.wHour,t.wMinute,t.wSecond,event,code,GetCurrentProcessId());fclose(f);}
}
static void State(const char* mode,bool active,DWORD code=0){
 std::lock_guard<std::mutex> guard(OutputMutex);FILE* f=nullptr;auto tmp=Directory+L"\\status.json.tmp";
 _wfopen_s(&f,tmp.c_str(),L"w");if(!f)return;
 fprintf(f,"{\"mode\":\"%s\",\"active\":%s,\"pid\":%lu,\"code\":%lu,\"uptime_ms\":%llu,\"legacy_disable_persistent\":false,\"automatic_camera_capture\":false}\n",mode,active?"true":"false",GetCurrentProcessId(),code,GetTickCount64());fclose(f);
 MoveFileExW(tmp.c_str(),(Directory+L"\\status.json").c_str(),MOVEFILE_REPLACE_EXISTING|MOVEFILE_WRITE_THROUGH);
}
static void ScmState(DWORD mode,DWORD error=NO_ERROR,DWORD checkpoint=0){
 if(!StatusHandle)return;SERVICE_STATUS s={};s.dwServiceType=SERVICE_WIN32_OWN_PROCESS;s.dwCurrentState=mode;
 s.dwControlsAccepted=mode==SERVICE_RUNNING?(SERVICE_ACCEPT_STOP|SERVICE_ACCEPT_SHUTDOWN):0;
 s.dwWin32ExitCode=error?ERROR_SERVICE_SPECIFIC_ERROR:NO_ERROR;s.dwServiceSpecificExitCode=error;s.dwCheckPoint=checkpoint;s.dwWaitHint=15000;SetServiceStatus(StatusHandle,&s);
}
static CONFIGRET Locate(PCWSTR id,DEVINST* dn){return CM_Locate_DevNodeW(dn,const_cast<PWSTR>(id),CM_LOCATE_DEVNODE_NORMAL);}
static std::wstring DeviceId(DEVINST dn){WCHAR b[MAX_DEVICE_ID_LEN]={};return CM_Get_Device_IDW(dn,b,MAX_DEVICE_ID_LEN,0)==CR_SUCCESS?b:L"";}
static bool Started(DEVINST dn){ULONG s=0,p=0;return CM_Get_DevNode_Status(&s,&p,dn,0)==CR_SUCCESS&&(s&DN_STARTED)&&p==0;}
static DWORD SetCameraEffects(DWORD value){
 WCHAR key[4096]={};GetPrivateProfileStringW(L"Studio",L"CameraInterfaceKey",L"",key,4096,Ini.c_str());
 const std::wstring k=key;
 if(k.find(L"SYSTEM\\CurrentControlSet\\Control\\DeviceClasses\\{E5323777-F976-4f5b-9B55-B94699C46E44}\\##?#")!=0||k.find(L"\\#GLOBAL")==std::wstring::npos)return ERROR_INVALID_DATA;
 HKEY h=nullptr;LSTATUS e=RegOpenKeyExW(HKEY_LOCAL_MACHINE,key,0,KEY_SET_VALUE,&h);
 if(e==ERROR_SUCCESS){e=RegSetValueExW(h,L"FSMEnableMsEffects",0,REG_DWORD,reinterpret_cast<BYTE*>(&value),sizeof(value));RegCloseKey(h);}return e;
}
static CONFIGRET EnableLegacy(){DEVINST n=0;CONFIGRET cr=Locate(LegacyId,&n);return cr==CR_SUCCESS?CM_Enable_DevNode(n,0):cr;}
static bool FindHealthyChild(DEVINST main,std::wstring* childId){
 if(!Started(main))return false;DEVINST child=0;if(CM_Get_Child(&child,main,0)!=CR_SUCCESS)return false;
 bool camera=false;
 do{auto id=DeviceId(child);std::transform(id.begin(),id.end(),id.begin(),towupper);if(id.find(L"SWD\\DRIVERENUM\\MEP_CAMERA_COMPONENT&")==0&&Started(child)){*childId=id;camera=true;break;}}while(CM_Get_Sibling(&child,child,0)==CR_SUCCESS);
 if(!camera)return false;
 HKEY key=nullptr;if(CM_Open_DevNode_Key(main,KEY_READ,0,RegDisposition_OpenExisting,&key,CM_REGISTRY_HARDWARE)!=CR_SUCCESS)return false;
 WCHAR path[2048]={};DWORD size=sizeof(path),type=0;LSTATUS e=RegQueryValueExW(key,L"MEPAssets",nullptr,&type,reinterpret_cast<BYTE*>(path),&size);RegCloseKey(key);
 if(e!=ERROR_SUCCESS||(type!=REG_SZ&&type!=REG_EXPAND_SZ))return false;
 auto engine=std::wstring(path)+L"\\PerceptionCore.dll";if(GetFileAttributesW(engine.c_str())==INVALID_FILE_ATTRIBUTES)return false;
 ULONG length=0;if(CM_Get_Device_Interface_List_SizeW(&length,const_cast<GUID*>(&EffectsCategory),nullptr,CM_GET_DEVICE_INTERFACE_LIST_PRESENT)!=CR_SUCCESS||!length)return false;
 std::vector<WCHAR> links(length+2);if(CM_Get_Device_Interface_ListW(const_cast<GUID*>(&EffectsCategory),nullptr,links.data(),length,CM_GET_DEVICE_INTERFACE_LIST_PRESENT)!=CR_SUCCESS)return false;
 auto expected=*childId;std::replace(expected.begin(),expected.end(),L'\\',L'#');
 for(const WCHAR* p=links.data();*p;p+=wcslen(p)+1){std::wstring value=p;std::transform(value.begin(),value.end(),value.begin(),towupper);if(value.find(expected)!=std::wstring::npos)return true;}
 return false;
}
struct CallbackContext{HANDLE event;HRESULT hr;std::wstring id;};
static void CALLBACK Created(HSWDEVICE,HRESULT hr,void* p,PCWSTR id){auto c=static_cast<CallbackContext*>(p);c->hr=hr;if(id)c->id=id;SetEvent(c->event);}
static DWORD RunHost(){
 State("starting",false);Log("starting");ScmState(SERVICE_START_PENDING,0,1);
 // Keep a previously healthy retained tree routed correctly during a service restart.
 DEVINST existingMain=0;std::wstring existingChild;
 const bool existingHealthy=Locate(L"SWD\\CodexStudio\\MepAssets1",&existingMain)==CR_SUCCESS&&FindHealthyChild(existingMain,&existingChild);
 if(!existingHealthy)Log("legacy_enable_before_creation",EnableLegacy());
 auto c=new CallbackContext{CreateEventW(nullptr,TRUE,FALSE,nullptr),E_PENDING,{}};HSWDEVICE device=nullptr;
 SW_DEVICE_CREATE_INFO ci={};ci.cbSize=sizeof(ci);ci.pszInstanceId=L"MepAssets1";ci.pszzHardwareIds=L"SWC\\MEP_VEN_8086_DEV_B03E\0";ci.CapabilityFlags=SWDeviceCapabilitiesSilentInstall;ci.pszDeviceDescription=L"Windows Studio Effects Software Host";
 const bool injectFailure=GetPrivateProfileIntW(L"Studio",L"FailStartupTest",0,Ini.c_str())!=0;
 HRESULT hr=injectFailure?HRESULT_FROM_WIN32(ERROR_NOT_SUPPORTED):SwDeviceCreate(L"CodexStudio",L"HTREE\\ROOT\\0",&ci,0,nullptr,Created,c,&device);
 const bool createInitiated=SUCCEEDED(hr);
 DWORD error=0;bool switched=false;
 if(FAILED(hr)){error=static_cast<DWORD>(hr);Log("create_failed",error);}
 if(!error){HANDLE events[]={StopEvent,c->event};DWORD w=WaitForMultipleObjects(2,events,FALSE,15000);if(w!=WAIT_OBJECT_0+1)error=w==WAIT_OBJECT_0?ERROR_CANCELLED:ERROR_TIMEOUT;else if(FAILED(c->hr))error=static_cast<DWORD>(c->hr);}
 if(!error){hr=SwDeviceSetLifetime(device,SWDeviceLifetimeHandle);if(FAILED(hr))error=static_cast<DWORD>(hr);}
 DEVINST main=0;std::wstring child;
 if(!error){
  bool ready=false;for(DWORD i=0;i<120;i++){
   if(WaitForSingleObject(StopEvent,500)==WAIT_OBJECT_0){error=ERROR_CANCELLED;break;}
   if(Locate(c->id.c_str(),&main)==CR_SUCCESS&&FindHealthyChild(main,&child)){ready=true;break;}
   if(i%4==0)ScmState(SERVICE_START_PENDING,0,i/4+2);
  }
  if(!ready&&!error)error=ERROR_TIMEOUT;
 }
 if(!error){
  DEVINST legacy=0;CONFIGRET cr=Locate(LegacyId,&legacy);
  if(cr==CR_SUCCESS){cr=CM_Disable_DevNode(legacy,CM_DISABLE_UI_NOT_OK);if(cr==CR_SUCCESS)switched=true;else error=CM_MapCrToWin32Err(cr,ERROR_GEN_FAILURE);}
  else if(cr!=CR_NO_SUCH_DEVNODE)error=CM_MapCrToWin32Err(cr,ERROR_GEN_FAILURE);
 }
 if(!error){error=SetCameraEffects(1);if(error)Log("optin_failed",error);}
 if(!error){hr=SwDeviceSetLifetime(device,SWDeviceLifetimeParentPresent);if(FAILED(hr))error=static_cast<DWORD>(hr);}
 if(!error){
  State("ready",true);Log("ready_session_only_legacy_disable");ScmState(SERVICE_RUNNING);
  while(WaitForSingleObject(StopEvent,1000)==WAIT_TIMEOUT){
   if(Console&&GetFileAttributesW((Directory+L"\\console.stop").c_str())!=INVALID_FILE_ATTRIBUTES)break;
   if(Locate(c->id.c_str(),&main)!=CR_SUCCESS||!FindHealthyChild(main,&child)){error=ERROR_DEVICE_NOT_CONNECTED;Log("health_failed",error);break;}
  }
 }
 ScmState(SERVICE_STOP_PENDING,0,1);
 // Stopping/crashing this process must not unplug a healthy graph in the current
 // boot. ParentPresent is deliberately paired with an automatic boot service.
 DEVINST retainedMain=0;std::wstring retainedChild;
 bool retainedHealthy=Locate(L"SWD\\CodexStudio\\MepAssets1",&retainedMain)==CR_SUCCESS&&FindHealthyChild(retainedMain,&retainedChild);
 if(retainedHealthy&&device&&FAILED(SwDeviceSetLifetime(device,SWDeviceLifetimeParentPresent)))retainedHealthy=false;
 if(retainedHealthy){
  DEVINST legacy=0;if(Locate(LegacyId,&legacy)==CR_SUCCESS)CM_Disable_DevNode(legacy,CM_DISABLE_UI_NOT_OK);
  Log("retained_tree_optin",SetCameraEffects(1));
 }else if(switched||error)Log("legacy_enable_recovery_required",EnableLegacy());
 if(device)SwDeviceClose(device);
 // A delayed create callback may still own its context after a timeout. In that
 // bounded failure path let process teardown reclaim it, rather than free it early.
 if(!createInitiated||WaitForSingleObject(c->event,0)==WAIT_OBJECT_0){CloseHandle(c->event);delete c;}
 State(retainedHealthy?(error?"degraded-retained-tree":"stopped-tree-retained"):"recovery-required",retainedHealthy,error);
 Log(retainedHealthy?"tree_retained_on_exit":"recovery_required",error);return error==ERROR_CANCELLED?0:error;
}
static DWORD WINAPI Handler(DWORD code,DWORD,void*,void*){if(code==SERVICE_CONTROL_STOP||code==SERVICE_CONTROL_SHUTDOWN){SetEvent(StopEvent);return NO_ERROR;}return ERROR_CALL_NOT_IMPLEMENTED;}
static void WINAPI ServiceMain(DWORD,LPWSTR*){StatusHandle=RegisterServiceCtrlHandlerExW(ServiceName,Handler,nullptr);if(!StatusHandle)return;DWORD e=RunHost();ScmState(SERVICE_STOPPED,e);}
int wmain(int argc,wchar_t** argv){
 WCHAR path[32768]={};GetModuleFileNameW(nullptr,path,32768);Directory=path;Directory=Directory.substr(0,Directory.find_last_of(L"\\/"));Ini=Directory+L"\\StudioHost.ini";StopEvent=CreateEventW(nullptr,TRUE,FALSE,nullptr);
 if(argc==2&&!wcscmp(argv[1],L"--console")){Console=true;DWORD e=RunHost();CloseHandle(StopEvent);return e?1:0;}
 if(argc!=2||wcscmp(argv[1],L"--service"))return 2;
 SERVICE_TABLE_ENTRYW table[]={{const_cast<PWSTR>(ServiceName),ServiceMain},{nullptr,nullptr}};
 BOOL ok=StartServiceCtrlDispatcherW(table);DWORD e=ok?0:GetLastError();CloseHandle(StopEvent);return e?1:0;
}
