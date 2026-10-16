using System;
using System.Runtime.InteropServices;
using System.Threading;

// A-1: find the real SwDeviceCreate export, then call it with minimal, corrected
// marshalling (function-pointer callback, simple instance id, no optional fields).
class SwDev4
{
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    static extern IntPtr LoadLibraryW(string name);
    [DllImport("kernel32.dll", CharSet = CharSet.Ansi, SetLastError = true)]
    static extern IntPtr GetProcAddress(IntPtr h, string proc);

    [StructLayout(LayoutKind.Sequential)]
    struct SW_DEVICE_CREATE_INFO
    {
        public uint cbSize;
        public IntPtr pszInstanceId;
        public IntPtr pszzHardwareIds;
        public IntPtr pszzCompatibleIds;
        public IntPtr pContainerId;
        public uint CapabilityFlags;
        public IntPtr pszDeviceDescription;
        public IntPtr pszDeviceLocation;
        public IntPtr pSecurityDescriptor;
    }

    [UnmanagedFunctionPointer(CallingConvention.Winapi)]
    delegate void CreateCallback(IntPtr hSwDevice, int createResult, IntPtr pContext, IntPtr pszDeviceInstanceId);

    // delegate over cfgmgr32, called through a raw function pointer
    [UnmanagedFunctionPointer(CallingConvention.Winapi)]
    delegate int SwDeviceCreateFn(string enumerator, string parent, ref SW_DEVICE_CREATE_INFO info,
                                  IntPtr callback, IntPtr ctx, out IntPtr hDevice);

    [DllImport("cfgmgr32.dll", EntryPoint = "SwDeviceClose", SetLastError = false)]
    static extern void SwDeviceClose(IntPtr hDevice);

    static CreateCallback keepAlive;

    static IntPtr MultiSz(string s) { return Marshal.StringToHGlobalUni(s + "\0\0"); }

    static int Main()
    {
        Console.WriteLine("SW_DEVICE_CREATE_INFO size = " + Marshal.SizeOf(typeof(SW_DEVICE_CREATE_INFO)) + " bytes (expect 64 on x64)");

        string[] modules = { "cfgmgr32.dll", "swdevice.dll", "api-ms-win-devices-swdevice-l1-1-0.dll" };
        IntPtr fn = IntPtr.Zero;
        foreach (var m in modules)
        {
            IntPtr h = LoadLibraryW(m);
            if (h == IntPtr.Zero) { Console.WriteLine("  " + m + " : NOT PRESENT/LOADABLE (err " + Marshal.GetLastWin32Error() + ")"); continue; }
            IntPtr p = GetProcAddress(h, "SwDeviceCreate");
            Console.WriteLine("  " + m + " : loaded, SwDeviceCreate=" + (p == IntPtr.Zero ? "NOT EXPORTED" : "0x" + p.ToInt64().ToString("X")));
            if (p != IntPtr.Zero && fn == IntPtr.Zero) fn = p;
        }
        if (fn == IntPtr.Zero) { Console.WriteLine("RESULT: no SwDeviceCreate export found anywhere"); return 2; }

        keepAlive = (h, res, ctx, id) =>
        {
            string s = id == IntPtr.Zero ? "(null)" : Marshal.PtrToStringUni(id);
            Console.WriteLine("   callback createResult=0x" + res.ToString("X8") + " instance=" + s);
        };
        IntPtr cb = Marshal.GetFunctionPointerForDelegate(keepAlive);
        var call = (SwDeviceCreateFn)Marshal.GetDelegateForFunctionPointer(fn, typeof(SwDeviceCreateFn));

        // minimal attempt 1: no parent, hardware id only
        var info = new SW_DEVICE_CREATE_INFO();
        info.cbSize = (uint)Marshal.SizeOf(typeof(SW_DEVICE_CREATE_INFO));
        info.pszInstanceId = Marshal.StringToHGlobalUni("MEPTestDevice");
        info.pszzHardwareIds = MultiSz(@"SWC\MEP_CAM&VEN_8086_DEV_B03E");
        info.pszzCompatibleIds = IntPtr.Zero;
        info.pContainerId = IntPtr.Zero;
        info.CapabilityFlags = 0;
        info.pszDeviceDescription = Marshal.StringToHGlobalUni("Windows Camera Effects");
        info.pszDeviceLocation = IntPtr.Zero;
        info.pSecurityDescriptor = IntPtr.Zero;

        IntPtr handle = IntPtr.Zero;
        int hr = -1;
        try
        {
            hr = call("SWD", null, ref info, cb, IntPtr.Zero, out handle);
            Console.WriteLine("RESULT: minimal SwDeviceCreate hr=0x" + hr.ToString("X8") + " handle=0x" + handle.ToInt64().ToString("X"));
        }
        catch (Exception ex)
        {
            Console.WriteLine("RESULT: EXCEPTION " + ex.GetType().Name + " : " + ex.Message);
        }

        if (hr == 0 && handle != IntPtr.Zero)
        {
            Console.WriteLine("device created; holding 120 s so you can inspect it");
            Console.Out.Flush();
            Thread.Sleep(120000);
            SwDeviceClose(handle);
            Console.WriteLine("closed");
        }
        return 0;
    }
}
