using System;
using System.Collections.Generic;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;

// Explicit single-product installation runner. Uses the verified original
// factory, generates the real plan, requires zero missing files, then calls
// the original session's Install method only when requested by the launcher.
public static class InstallRunner
{
    [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
    static extern IntPtr LoadLibraryExW(string path, IntPtr file, uint flags);
    [DllImport("kernel32.dll", CharSet=CharSet.Ansi, SetLastError=true)]
    static extern IntPtr GetProcAddress(IntPtr module, string name);
    [DllImport("kernel32.dll")] static extern bool FreeLibrary(IntPtr module);
    [DllImport("kernel32.dll", CharSet=CharSet.Unicode)]
    static extern uint GetModuleFileNameW(IntPtr module, StringBuilder path, int length);
    [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
    static extern bool GetModuleHandleExW(uint flags, IntPtr address, out IntPtr module);
    [DllImport("combase.dll")] static extern int RoInitialize(uint kind);
    [DllImport("combase.dll")] static extern void RoUninitialize();
    [DllImport("combase.dll",EntryPoint="GetRestrictedErrorInfo",ExactSpelling=true)] static extern int GetRestrictedErrorInfo(out IntPtr info);
    [DllImport("oleaut32.dll")] static extern void SysFreeString(IntPtr text);
    [UnmanagedFunctionPointer(CallingConvention.StdCall)]
    delegate int CreateSession(uint kind, [MarshalAs(UnmanagedType.LPWStr)] string source,
        IntPtr zero16, uint optionVersion, IntPtr options, out IntPtr session);
    [UnmanagedFunctionPointer(CallingConvention.StdCall)]
    delegate int GetObject(IntPtr self, out IntPtr result);
    [UnmanagedFunctionPointer(CallingConvention.StdCall)]
    delegate int GetCount(IntPtr self, out uint count);
    [UnmanagedFunctionPointer(CallingConvention.StdCall)]
    delegate int InstallObject(IntPtr self, out IntPtr result, out uint rebootRequired);
    [UnmanagedFunctionPointer(CallingConvention.StdCall)]
    delegate uint ReleaseObject(IntPtr self);
    [UnmanagedFunctionPointer(CallingConvention.StdCall)]
    delegate int ErrorDetails(IntPtr self,out IntPtr description,out int error,out IntPtr restricted,out IntPtr sid);

    public sealed class Event
    {
        public string Stage {get;set;}
        public string Value {get;set;}
    }
    static List<Event> events;
    static string logPath;
    static void Log(string stage, string value)
    {
        events.Add(new Event{Stage=stage,Value=value});
        File.AppendAllText(logPath, DateTime.UtcNow.ToString("o")+"\t"+stage+"\t"+value+Environment.NewLine);
    }
    static string Hex(int value) {return "0x"+unchecked((uint)value).ToString("X8");}
    static IntPtr Slot(IntPtr obj, int index)
    {return Marshal.ReadIntPtr(Marshal.ReadIntPtr(obj), index*IntPtr.Size);}
    static string DescribeAddress(IntPtr addr)
    {
        IntPtr module;
        if(!GetModuleHandleExW(0x4|0x2,addr,out module)) return "unmapped:"+addr.ToString("x");
        var sb=new StringBuilder(2048);GetModuleFileNameW(module,sb,sb.Capacity);
        return sb.ToString()+"+0x"+(addr.ToInt64()-module.ToInt64()).ToString("x");
    }
    static void Release(ref IntPtr obj, string name)
    {
        if(obj==IntPtr.Zero)return;
        Log("release.begin",name);
        Marshal.GetDelegateForFunctionPointer<ReleaseObject>(Slot(obj,2))(obj);
        obj=IntPtr.Zero;
        Log("release.end",name);
    }
    static void CaptureErrorDetails()
    {
        IntPtr info=IntPtr.Zero,description=IntPtr.Zero,restricted=IntPtr.Zero,sid=IntPtr.Zero;
        try
        {
            int hr=GetRestrictedErrorInfo(out info);Log("restrictedErrorInfo",Hex(hr));
            if(hr<0 || info==IntPtr.Zero)return;
            int error;
            hr=Marshal.GetDelegateForFunctionPointer<ErrorDetails>(Slot(info,3))(info,out description,out error,out restricted,out sid);
            Log("restrictedErrorDetails",Hex(hr)+"; error="+Hex(error));
            if(description!=IntPtr.Zero)Log("error.description",Marshal.PtrToStringBSTR(description));
            if(restricted!=IntPtr.Zero)Log("error.restrictedDescription",Marshal.PtrToStringBSTR(restricted));
            if(sid!=IntPtr.Zero)Log("error.capabilitySid",Marshal.PtrToStringBSTR(sid));
        }
        finally
        {
            if(description!=IntPtr.Zero)SysFreeString(description);
            if(restricted!=IntPtr.Zero)SysFreeString(restricted);
            if(sid!=IntPtr.Zero)SysFreeString(sid);
            Release(ref info,"restricted error info");
        }
    }
    public static List<Event> Run(string library, string source, string eventsFile, bool installProduct)
    {
        events=new List<Event>();logPath=eventsFile;
        // Do not terminate a process in the middle of a native deployment.
        IntPtr module=IntPtr.Zero,options=IntPtr.Zero,zero=IntPtr.Zero,json=IntPtr.Zero;
        IntPtr session=IntPtr.Zero,request=IntPtr.Zero,files=IntPtr.Zero,result=IntPtr.Zero;
        bool uninit=false;
        try
        {
            Log("mode",installProduct ? "explicit-single-product-install" : "request-getters-only");
            int hr=RoInitialize(1);Log("RoInitialize",Hex(hr));
            uninit=hr>=0;
            if(hr<0 && unchecked((uint)hr)!=0x80010106)return events;
            module=LoadLibraryExW(library,IntPtr.Zero,0x100|0x800);
            if(module==IntPtr.Zero){Log("LoadLibraryEx.failed",Marshal.GetLastWin32Error().ToString());return events;}
            Log("loaded",library);
            IntPtr export=GetProcAddress(module,"CreateDeploymentSessionEx");
            if(export==IntPtr.Zero){Log("GetProcAddress.failed",Marshal.GetLastWin32Error().ToString());return events;}
            Log("factory",DescribeAddress(export));
            options=Marshal.AllocHGlobal(56);Marshal.Copy(new byte[56],0,options,56);
            zero=Marshal.AllocHGlobal(16);Marshal.Copy(new byte[16],0,zero,16);
            json=Marshal.StringToHGlobalUni("{\"ModuleID\":\"LocalServicingOnline\"}");
            Marshal.WriteIntPtr(options,json);
            Log("create.begin",source);
            hr=Marshal.GetDelegateForFunctionPointer<CreateSession>(export)(1,source,zero,2,options,out session);
            Log("create.end",Hex(hr)+"; session="+session.ToString("x"));
            if(hr<0){CaptureErrorDetails();return events;}
            if(session==IntPtr.Zero)return events;
            for(int i=0;i<6;i++)Log("session.slot."+i,DescribeAddress(Slot(session,i)));
            // Derived from the exact UALite constructor/vtable in this research.
            // Stop if a different object or binary dispatch layout is returned.
            if(Slot(session,4).ToInt64()!=module.ToInt64()+0x2ce10 ||
               Slot(session,5).ToInt64()!=module.ToInt64()+0x2df80)
            {Log("guard.stop","session vtable differs from the verified UALite layout");return events;}
            Log("getDownloadRequest.begin","original session slot4 / +0x20");
            hr=Marshal.GetDelegateForFunctionPointer<GetObject>(Slot(session,4))(session,out request);
            Log("getDownloadRequest.end",Hex(hr));
            if(hr<0 || request==IntPtr.Zero)return events;
            Log("getFileRequests.begin","request slot5 / +0x28");
            hr=Marshal.GetDelegateForFunctionPointer<GetObject>(Slot(request,5))(request,out files);
            Log("getFileRequests.end",Hex(hr));
            if(hr<0 || files==IntPtr.Zero)return events;
            uint count;
            hr=Marshal.GetDelegateForFunctionPointer<GetCount>(Slot(files,3))(files,out count);
            Log("fileRequestCount",Hex(hr)+"; count="+count);
            if(hr<0 || count!=0){Log("guard.stop","Missing files or unsuccessful file count; Install was not called");return events;}
            if(!installProduct){Log("stop","Planning only; Install was not called");return events;}
            Log("install.begin","original session slot5 / +0x28; authorized single product");
            uint rebootRequired=0;
            hr=Marshal.GetDelegateForFunctionPointer<InstallObject>(Slot(session,5))(session,out result,out rebootRequired);
            Log("install.end",Hex(hr)+"; rebootRequired="+rebootRequired+"; result="+result.ToString("x"));
            if(hr<0)CaptureErrorDetails();
            return events;
        }
        catch(Exception ex){Log("managed.exception",ex.GetType().FullName+": "+ex.Message);return events;}
        finally
        {
            Release(ref result,"install result");
            Release(ref files,"file requests");
            Release(ref request,"download request");
            Release(ref session,"session");
            if(json!=IntPtr.Zero)Marshal.FreeHGlobal(json);
            if(zero!=IntPtr.Zero)Marshal.FreeHGlobal(zero);
            if(options!=IntPtr.Zero)Marshal.FreeHGlobal(options);
            if(module!=IntPtr.Zero)FreeLibrary(module);
            if(uninit)RoUninitialize();
            Log("process.done","cleanup completed");
        }
    }
}
