#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <swdevice.h>
#include <cfgmgr32.h>
#include <cstdio>
#include <string>
#pragma comment(lib,"swdevice.lib")
#pragma comment(lib,"cfgmgr32.lib")
struct CreateContext{HANDLE event;HRESULT hr;std::wstring id;};
void CALLBACK Created(HSWDEVICE,HRESULT hr,void* context,PCWSTR id){auto c=static_cast<CreateContext*>(context);c->hr=hr;if(id)c->id=id;SetEvent(c->event);}
void PrintNode(DEVINST n,int depth){
    WCHAR id[MAX_DEVICE_ID_LEN]={};ULONG status=0,problem=0;
    CM_Get_Device_IDW(n,id,MAX_DEVICE_ID_LEN,0);CM_Get_DevNode_Status(&status,&problem,n,0);
    wprintf(L"node depth=%d started=%d status=0x%08lX problem=%lu id=%s\n",depth,(status&DN_STARTED)!=0,status,problem,id);fflush(stdout);
    if(depth>=3)return;DEVINST child;
    if(CM_Get_Child(&child,n,0)==CR_SUCCESS){do{PrintNode(child,depth+1);}while(CM_Get_Sibling(&child,child,0)==CR_SUCCESS);}
}
int wmain(int argc,wchar_t** argv){
    bool persist=false,remove=false;DWORD seconds=10;
    for(int i=1;i<argc;i++){if(!wcscmp(argv[i],L"--persist"))persist=true;else if(!wcscmp(argv[i],L"--remove"))remove=true;else if(!wcscmp(argv[i],L"--seconds")&&i+1<argc)seconds=wcstoul(argv[++i],nullptr,10);else return 2;}
    if(seconds>60)return 2;
    CreateContext context{CreateEventW(nullptr,TRUE,FALSE,nullptr),E_PENDING,{}};
    SW_DEVICE_CREATE_INFO ci={};ci.cbSize=sizeof(ci);ci.pszInstanceId=L"MepAssets1";
    ci.pszzHardwareIds=L"SWC\\MEP_VEN_8086_DEV_B03E\0";
    ci.CapabilityFlags=SWDeviceCapabilitiesSilentInstall;
    ci.pszDeviceDescription=L"Windows Studio Effects Software Host";
    HSWDEVICE device=nullptr;
    HRESULT hr=SwDeviceCreate(L"CodexStudio",L"HTREE\\ROOT\\0",&ci,0,nullptr,Created,&context,&device);
    wprintf(L"SwDeviceCreate=0x%08X\n",(unsigned)hr);fflush(stdout);
    if(FAILED(hr))return 3;
    if(WaitForSingleObject(context.event,15000)!=WAIT_OBJECT_0){SwDeviceClose(device);return 4;}
    wprintf(L"callback=0x%08X id=%s\n",(unsigned)context.hr,context.id.c_str());fflush(stdout);
    if(FAILED(context.hr)){SwDeviceClose(device);return 5;}
    if(remove){hr=SwDeviceSetLifetime(device,SWDeviceLifetimeHandle);wprintf(L"remove lifetime=0x%08X\n",(unsigned)hr);SwDeviceClose(device);CloseHandle(context.event);return FAILED(hr)?6:0;}
    for(DWORD i=0;i<seconds;i++){Sleep(1000);DEVINST n=0;if(CM_Locate_DevNodeW(&n,const_cast<PWSTR>(context.id.c_str()),0)==CR_SUCCESS)PrintNode(n,0);}
    if(persist){hr=SwDeviceSetLifetime(device,SWDeviceLifetimeParentPresent);wprintf(L"persist lifetime=0x%08X\n",(unsigned)hr);}
    SwDeviceClose(device);CloseHandle(context.event);wprintf(L"closed persistent=%d\n",persist);return FAILED(hr)?7:0;
}
