#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <string>
#include <cstdio>
#pragma comment(lib,"advapi32.lib")
static const wchar_t* Name=L"CodexStudioCpuBridge";
static SERVICE_STATUS_HANDLE Handle=nullptr;static HANDLE Stop=nullptr;static std::wstring Root;
static void State(DWORD state,DWORD error=0,DWORD checkpoint=0){SERVICE_STATUS s={};s.dwServiceType=SERVICE_WIN32_OWN_PROCESS;s.dwCurrentState=state;s.dwControlsAccepted=state==SERVICE_RUNNING?SERVICE_ACCEPT_STOP|SERVICE_ACCEPT_SHUTDOWN:0;s.dwWin32ExitCode=error?ERROR_SERVICE_SPECIFIC_ERROR:0;s.dwServiceSpecificExitCode=error;s.dwCheckPoint=checkpoint;s.dwWaitHint=15000;SetServiceStatus(Handle,&s);}
static void SignalStop(){HANDLE f=CreateFileW((Root+L"\\worker.stop").c_str(),GENERIC_WRITE,FILE_SHARE_READ,nullptr,CREATE_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr);if(f!=INVALID_HANDLE_VALUE)CloseHandle(f);}
static DWORD WINAPI Control(DWORD code,DWORD,void*,void*){if(code==SERVICE_CONTROL_STOP||code==SERVICE_CONTROL_SHUTDOWN){State(SERVICE_STOP_PENDING,0,1);SetEvent(Stop);SignalStop();}return NO_ERROR;}
static bool WorkerReady(DWORD pid){FILE* f=nullptr;_wfopen_s(&f,(Root+L"\\status.json").c_str(),L"rb");if(!f)return false;char b[8192]={};size_t n=fread(b,1,sizeof(b)-1,f);fclose(f);std::string v(b,n);std::string marker="\"worker_pid\":"+std::to_string(pid)+",";return v.find(marker)!=std::string::npos&&v.find("\"active\":true")!=std::string::npos;}
static void WINAPI Main(DWORD,wchar_t**){
 Handle=RegisterServiceCtrlHandlerExW(Name,Control,nullptr);if(!Handle)return;Stop=CreateEventW(nullptr,TRUE,FALSE,nullptr);State(SERVICE_START_PENDING,0,1);
 wchar_t exe[32768]={};GetModuleFileNameW(nullptr,exe,32768);Root=exe;Root=Root.substr(0,Root.find_last_of(L"\\"));SetCurrentDirectoryW(Root.c_str());
 DeleteFileW((Root+L"\\worker.stop").c_str());
 SECURITY_ATTRIBUTES sa={sizeof(sa),nullptr,TRUE};HANDLE out=CreateFileW((Root+L"\\worker-console.log").c_str(),FILE_APPEND_DATA,FILE_SHARE_READ|FILE_SHARE_WRITE,&sa,OPEN_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr);HANDLE input=CreateFileW(L"NUL",GENERIC_READ,FILE_SHARE_READ|FILE_SHARE_WRITE,&sa,OPEN_EXISTING,0,nullptr);
 HANDLE job=CreateJobObjectW(nullptr,nullptr);JOBOBJECT_EXTENDED_LIMIT_INFORMATION limits={};limits.BasicLimitInformation.LimitFlags=JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;DWORD error=0;if(!job||!SetInformationJobObject(job,JobObjectExtendedLimitInformation,&limits,sizeof(limits)))error=GetLastError();
 std::wstring python=Root+L"\\python\\python.exe",cmd=L"\""+python+L"\" -I -u \""+Root+L"\\worker.py\" \""+Root+L"\"";STARTUPINFOW si={};si.cb=sizeof(si);si.dwFlags=STARTF_USESTDHANDLES;si.hStdInput=input;si.hStdOutput=out;si.hStdError=out;PROCESS_INFORMATION pi={};
 if(!error&&!CreateProcessW(python.c_str(),cmd.data(),nullptr,nullptr,TRUE,CREATE_NO_WINDOW|CREATE_SUSPENDED,nullptr,Root.c_str(),&si,&pi))error=GetLastError();
 if(!error&&!AssignProcessToJobObject(job,pi.hProcess))error=GetLastError();if(!error)ResumeThread(pi.hThread);
 if(pi.hThread)CloseHandle(pi.hThread);if(out!=INVALID_HANDLE_VALUE)CloseHandle(out);if(input!=INVALID_HANDLE_VALUE)CloseHandle(input);
 bool ready=false;
 if(!error){for(DWORD i=0;i<120;i++){HANDLE waits[]={Stop,pi.hProcess};DWORD w=WaitForMultipleObjects(2,waits,FALSE,500);if(w==WAIT_OBJECT_0){error=ERROR_CANCELLED;break;}if(w==WAIT_OBJECT_0+1){error=ERROR_PROCESS_ABORTED;break;}if(WorkerReady(pi.dwProcessId)){ready=true;break;}if(i%4==0)State(SERVICE_START_PENDING,0,i/4+2);}if(!ready&&!error)error=ERROR_TIMEOUT;}
 if(ready&&!error){State(SERVICE_RUNNING);HANDLE waits[]={Stop,pi.hProcess};DWORD w=WaitForMultipleObjects(2,waits,FALSE,INFINITE);if(w==WAIT_OBJECT_0+1)error=ERROR_PROCESS_ABORTED;}
 State(SERVICE_STOP_PENDING,0,1);SignalStop();if(pi.hProcess){if(WaitForSingleObject(pi.hProcess,7000)==WAIT_TIMEOUT)TerminateProcess(pi.hProcess,ERROR_CANCELLED);CloseHandle(pi.hProcess);}if(job)CloseHandle(job);if(Stop)CloseHandle(Stop);State(SERVICE_STOPPED,error==ERROR_CANCELLED?0:error);
}
int wmain(){SERVICE_TABLE_ENTRYW table[]={{const_cast<LPWSTR>(Name),Main},{nullptr,nullptr}};return StartServiceCtrlDispatcherW(table)?0:(int)GetLastError();}
