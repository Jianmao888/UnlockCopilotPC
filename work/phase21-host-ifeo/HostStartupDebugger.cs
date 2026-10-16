// Bounded IFEO debugger for one SHA256-bound Microsoft workload host.
// The original on-disk image is never changed. An explicit --patch argument
// changes only two immediate values in this debugger's newly-created child.
using System;
using System.IO;
using System.Text;
using System.Collections.Generic;
using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Security.Principal;
using System.Web.Script.Serialization;

class HostStartupDebugger {
 const string Target=@"C:\Program Files\WindowsApps\WindowsWorkload.Manager.1_1.2511.1196.0_x64__8wekyb3d8bbwe\WorkloadsSessionHost.exe";
 const string Expected="14ba0122022b54681cbf8f90ecc5566e48aabeb98537b5fd1b1befedbc68c6d8";
 static string log;
 static JavaScriptSerializer json=new JavaScriptSerializer();
 [StructLayout(LayoutKind.Sequential,CharSet=CharSet.Unicode)] struct SI {
  public uint cb; public string reserved,desktop,title;
  public uint x,y,xs,ys,xc,yc,fill,flags;public ushort show,res2size;
  public IntPtr res2,stdin,stdout,stderr;
 }
 [StructLayout(LayoutKind.Sequential)] struct PI {public IntPtr process,thread;public uint pid,tid;}
 [StructLayout(LayoutKind.Explicit,Size=176)] struct DE {
  [FieldOffset(0)]public uint code;[FieldOffset(4)]public uint pid;[FieldOffset(8)]public uint tid;
  [FieldOffset(16)]public IntPtr file;[FieldOffset(24)]public IntPtr process;
  [FieldOffset(32)]public IntPtr thread;[FieldOffset(40)]public IntPtr image;
  [FieldOffset(16)]public uint exception;[FieldOffset(32)]public IntPtr exceptionAddress;
  [FieldOffset(16)]public uint exitCode;
 }
 [DllImport("kernel32.dll",CharSet=CharSet.Unicode,SetLastError=true)]static extern bool CreateProcessW(string app,StringBuilder cmd,IntPtr pa,IntPtr ta,bool inherit,uint flags,IntPtr env,string cwd,ref SI si,out PI pi);
 [DllImport("kernel32.dll",SetLastError=true)]static extern bool WaitForDebugEvent(out DE e,uint ms);
 [DllImport("kernel32.dll",SetLastError=true)]static extern bool ContinueDebugEvent(uint pid,uint tid,uint status);
 [DllImport("kernel32.dll",SetLastError=true)]static extern bool ReadProcessMemory(IntPtr h,IntPtr addr,byte[] data,UIntPtr size,out UIntPtr read);
 [DllImport("kernel32.dll",SetLastError=true)]static extern bool WriteProcessMemory(IntPtr h,IntPtr addr,byte[] data,UIntPtr size,out UIntPtr written);
 [DllImport("kernel32.dll",SetLastError=true)]static extern bool FlushInstructionCache(IntPtr h,IntPtr addr,UIntPtr size);
 [DllImport("kernel32.dll",SetLastError=true)]static extern bool GetProcessMitigationPolicy(IntPtr h,int policy,out uint value,UIntPtr size);
 [DllImport("kernel32.dll",CharSet=CharSet.Unicode)]static extern int GetPackageFullName(IntPtr h,ref uint length,StringBuilder value);
 [DllImport("kernel32.dll")]static extern bool ProcessIdToSessionId(uint pid,out uint session);
 [DllImport("kernel32.dll",SetLastError=true)]static extern bool DebugActiveProcessStop(uint pid);
 [DllImport("kernel32.dll",SetLastError=true)]static extern bool DebugSetProcessKillOnExit(bool kill);
 [DllImport("kernel32.dll",SetLastError=true)]static extern bool GetThreadContext(IntPtr thread,IntPtr context);
 [DllImport("kernel32.dll",SetLastError=true)]static extern bool SetThreadContext(IntPtr thread,IntPtr context);
 [DllImport("kernel32.dll",SetLastError=true)]static extern uint SuspendThread(IntPtr thread);
 [DllImport("kernel32.dll",SetLastError=true)]static extern uint ResumeThread(IntPtr thread);
 [DllImport("kernel32.dll")]static extern bool CloseHandle(IntPtr h);
 [DllImport("kernel32.dll")]static extern uint WaitForSingleObject(IntPtr h,uint ms);
 [DllImport("kernel32.dll")]static extern bool TerminateProcess(IntPtr h,uint exit);
 static void Check(bool ok){if(!ok)throw new System.ComponentModel.Win32Exception(Marshal.GetLastWin32Error());}
 static void Log(string name,object data){File.AppendAllText(log,json.Serialize(new {time=DateTime.UtcNow.ToString("o"),@event=name,data=data})+"\n",Encoding.UTF8);}
 static byte[] Read(IntPtr h,long address,int size){var b=new byte[size];UIntPtr n;Check(ReadProcessMemory(h,new IntPtr(address),b,(UIntPtr)size,out n));if(n.ToUInt64()!=(ulong)size)throw new Exception("Short read");return b;}
 static void Write(IntPtr h,long address,byte[] b){UIntPtr n;Check(WriteProcessMemory(h,new IntPtr(address),b,(UIntPtr)b.Length,out n));if(n.ToUInt64()!=(ulong)b.Length)throw new Exception("Short write");Check(FlushInstructionCache(h,new IntPtr(address),(UIntPtr)b.Length));}
 static void Rewind(IntPtr thread,long address){IntPtr memory=Marshal.AllocHGlobal(1248);try{IntPtr a=new IntPtr((memory.ToInt64()+15)&~15L);Marshal.WriteInt32(a,48,0x100001);Check(GetThreadContext(thread,a));Marshal.WriteInt64(a,248,address);Check(SetThreadContext(thread,a));}finally{Marshal.FreeHGlobal(memory);}}
 static object Policies(IntPtr h){var d=new Dictionary<string,uint>();foreach(int p in new int[]{2,8,9,10,13}){uint v;Check(GetProcessMitigationPolicy(h,p,out v,(UIntPtr)4));d[p.ToString()]=v;}return d;}
 static object Package(IntPtr h){uint n=0;int rc=GetPackageFullName(h,ref n,null);var b=new StringBuilder((int)Math.Max(1,n));rc=GetPackageFullName(h,ref n,b);return new {result=rc,name=rc==0?b.ToString():null};}
 static string Quote(string v){var b=new StringBuilder("\"");int slashes=0;foreach(char c in v){if(c=='\\'){slashes++;continue;}if(c=='\"'){b.Append('\\',slashes*2+1);b.Append(c);}else{b.Append('\\',slashes);b.Append(c);}slashes=0;}b.Append('\\',slashes*2);return b.Append('"').ToString();}
 static string Hash(){using(var s=SHA256.Create())using(var f=File.OpenRead(Target)){return BitConverter.ToString(s.ComputeHash(f)).Replace("-","").ToLowerInvariant();}}
 static int Main(string[] args){
  PI pi=new PI();bool created=false,attached=false,ok=false,suspended=false;var handles=new HashSet<IntPtr>();long image=0;byte[] returnByte=null;
  try {
   // Two fixed debugger arguments precede the complete original command line.
   if(args.Length<3 || (args[0]!="--observe" && args[0]!="--patch"))return 2;
   bool patch=args[0]=="--patch";
   string directory=Path.GetFullPath(args[1]);
   string staged=Path.GetDirectoryName(Process.GetCurrentProcess().MainModule.FileName);
   if(!directory.Equals(Path.Combine(staged,"logs"),StringComparison.OrdinalIgnoreCase))return 2;
   log=Path.Combine(directory,"wrapper-"+Process.GetCurrentProcess().Id+"-"+DateTime.UtcNow.Ticks+".jsonl");
   if(!Path.GetFullPath(args[2]).Equals(Target,StringComparison.OrdinalIgnoreCase))throw new Exception("Unexpected target path");
   string hash=Hash();if(hash!=Expected)throw new Exception("Target hash changed");
   uint session;ProcessIdToSessionId((uint)Process.GetCurrentProcess().Id,out session);
   Log("wrapper_start",new {pid=Process.GetCurrentProcess().Id,identity=WindowsIdentity.GetCurrent().User.Value,session=session,patch=patch,target=Target,sha256=hash,arguments=String.Join(" ",args,2,args.Length-2),package=Package(Process.GetCurrentProcess().Handle)});
   var words=new List<string>();for(int i=2;i<args.Length;i++)words.Add(Quote(args[i]));
   var si=new SI();si.cb=(uint)Marshal.SizeOf(si);si.flags=1;si.show=0;
   Check(CreateProcessW(Target,new StringBuilder(String.Join(" ",words)),IntPtr.Zero,IntPtr.Zero,false,0x08000002,IntPtr.Zero,Environment.CurrentDirectory,ref si,out pi));created=true;attached=true;
   Check(DebugSetProcessKillOnExit(false));
   var clock=Stopwatch.StartNew();
   while(clock.ElapsedMilliseconds<10000){
    DE e;if(!WaitForDebugEvent(out e,200)){if(Marshal.GetLastWin32Error()==121)continue;Check(false);}
    uint status=0x10002;bool detach=false;
    if(e.code==3){
     if(e.pid!=pi.pid)throw new Exception("Unexpected debug child");
     if(e.file!=IntPtr.Zero)CloseHandle(e.file);handles.Add(e.process);handles.Add(e.thread);
     image=e.image.ToInt64();ProcessIdToSessionId(pi.pid,out session);
     Log("child_before_entry",new {pid=pi.pid,tid=pi.tid,imagebase="0x"+image.ToString("x"),session=session,package=Package(pi.process),policies=Policies(pi.process)});
     foreach(int rva in new int[]{0xddfe,0xde22}){
      byte[] before=Read(pi.process,image+rva,4);if(BitConverter.ToUInt32(before,0)!=1)throw new Exception("Initializer mismatch at "+rva.ToString("x"));
      if(patch)Write(pi.process,image+rva,new byte[4]);
     }
     Log("startup_ready",new {pid=pi.pid,patch=patch});
     if(patch){returnByte=Read(pi.process,image+0xda36,1);if(returnByte[0]!=0x45)throw new Exception("Return instruction mismatch");Write(pi.process,image+0xda36,new byte[]{0xcc});}else detach=true;
    }else if(e.code==6){if(e.file!=IntPtr.Zero)CloseHandle(e.file);}
    else if(e.code==2){handles.Add(e.file);}
    else if(e.code==1 && e.exception==0x80000003 && e.exceptionAddress.ToInt64()==image+0xda36 && patch){
     if(e.tid!=pi.tid)throw new Exception("Unexpected checkpoint thread");
     Write(pi.process,image+0xda36,returnByte);Rewind(pi.thread,image+0xda36);
     Check(SuspendThread(pi.thread)!=0xffffffff);suspended=true;
     Log("after_initializer",new {pid=pi.pid,policies=Policies(pi.process)});detach=true;
    }else if(e.code==1 && e.exception!=0x80000003){status=0x80010001;}
    else if(e.code==5){Log("early_exit",new {pid=pi.pid,exitCode=e.exitCode});throw new Exception("Child exited before initial event");}
    Check(ContinueDebugEvent(e.pid,e.tid,status));
    if(detach){Check(DebugActiveProcessStop(pi.pid));attached=false;ok=true;Log("debugger_detached",new {pid=pi.pid});break;}
   }
   if(!ok)throw new TimeoutException("No initial debug event");
   if(suspended){
    Log("startup_wait_agent",new {pid=pi.pid});
    string signal=Path.Combine(directory,"host-"+pi.pid+"-agent-ready.signal");var waitAgent=Stopwatch.StartNew();
    while(!File.Exists(signal) && waitAgent.ElapsedMilliseconds<10000)System.Threading.Thread.Sleep(50);
    Log("agent_wait_end",new {pid=pi.pid,signal=File.Exists(signal)});
    Check(ResumeThread(pi.thread)!=0xffffffff);suspended=false;
   }
   System.Threading.Thread.Sleep(350);
   uint state=WaitForSingleObject(pi.process,0);
   if(state==0)Log("child_exited_early",new {pid=pi.pid});else Log("child_after_start",new {pid=pi.pid,policies=Policies(pi.process)});
   // Keep the debugger process alive while activation and the bounded test run.
   uint lifetimeMs=65000;
   string lifetimeFile=Path.Combine(staged,"host-lifetime-ms.txt");
   if(File.Exists(lifetimeFile)){
    uint configured;
    if(!UInt32.TryParse(File.ReadAllText(lifetimeFile).Trim(),out configured) || configured<1000 || configured>1800000)throw new Exception("Invalid bounded host lifetime");
    lifetimeMs=configured;
   }
   uint wait=WaitForSingleObject(pi.process,lifetimeMs);
   Log("bounded_wait_end",new {pid=pi.pid,status=wait});
   if(wait==0x102){TerminateProcess(pi.process,0);Log("watchdog_child_stopped",new {pid=pi.pid});}
   return 0;
  }catch(Exception error){try{if(log!=null)Log("error",new {message=error.ToString()});}catch{}return 1;}
  finally {
   if(suspended)ResumeThread(pi.thread);
   if(attached){DebugActiveProcessStop(pi.pid);if(created)TerminateProcess(pi.process,1);}
   if(created && !ok)TerminateProcess(pi.process,1);
   handles.Add(pi.process);handles.Add(pi.thread);foreach(IntPtr h in handles)if(h!=IntPtr.Zero)CloseHandle(h);
  }
 }
}
