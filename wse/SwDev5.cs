using System;
using System.Runtime.InteropServices;
using System.Threading;

// A-1 attempt 2: SwDeviceCreate (cfgmgr32.dll) with a COMPLETE SW_DEVICE_CREATE_INFO.
// Previous attempt passed NULL for pContainerId / pSecurityDescriptor / CompatibleIds
// and crashed; Microsoft's sample always supplies a container id, a security
// descriptor (from SDDL) and MULTI_SZ id lists.
class SwDev5
{
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

    [DllImport("cfgmgr32.dll", EntryPoint = "SwDeviceCreate", CharSet = CharSet.Unicode, SetLastError = false)]
    static extern int SwDeviceCreate(string enumerator, string parent, ref SW_DEVICE_CREATE_INFO info,
                                     IntPtr callback, IntPtr ctx, out IntPtr hDevice);

    [DllImport("cfgmgr32.dll", EntryPoint = "SwDeviceClose", SetLastError = false)]
    static extern void SwDeviceClose(IntPtr hDevice);

    [DllImport("advapi32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    static extern bool ConvertStringSecurityDescriptorToSecurityDescriptorW(string sddl, uint rev,
                                                                            out IntPtr psd, IntPtr size);

    static CreateCallback keepAlive;
    static IntPtr sd = IntPtr.Zero;
    static IntPtr cid = IntPtr.Zero;

    static IntPtr MultiSz(params string[] parts)
    {
        return Marshal.StringToHGlobalUni(string.Join("\0", parts) + "\0\0");
    }

    static int CreateOne(string parent, string instanceId, string hardwareId, string description, out IntPtr handle)
    {
        var info = new SW_DEVICE_CREATE_INFO();
        info.cbSize = (uint)Marshal.SizeOf(typeof(SW_DEVICE_CREATE_INFO));
        info.pszInstanceId = Marshal.StringToHGlobalUni(instanceId);
        info.pszzHardwareIds = MultiSz(hardwareId);
        info.pszzCompatibleIds = MultiSz("SWC\\Generic", "SWD\\GenericRaw", "SWD\\Generic");
        info.pContainerId = cid;
        info.CapabilityFlags = 0;
        info.pszDeviceDescription = Marshal.StringToHGlobalUni(description);
        info.pszDeviceLocation = Marshal.StringToHGlobalUni("WindowsStudioEffects");
        info.pSecurityDescriptor = sd;
        return SwDeviceCreate("SWD", parent, ref info, Marshal.GetFunctionPointerForDelegate(keepAlive), IntPtr.Zero, out handle);
    }

    static int Main(string[] args)
    {
        string parent = args.Length > 0 && args[0] != "-" ? args[0] : null;
        Console.WriteLine("struct size = " + Marshal.SizeOf(typeof(SW_DEVICE_CREATE_INFO)));
        Console.WriteLine("parent = " + (parent ?? "(null)"));

        if (!ConvertStringSecurityDescriptorToSecurityDescriptorW("D:P(A;;GA;;;SY)(A;;GA;;;BA)", 1, out sd, IntPtr.Zero))
            Console.WriteLine("  SDDL conversion failed err=" + Marshal.GetLastWin32Error());
        else
            Console.WriteLine("  security descriptor = 0x" + sd.ToInt64().ToString("X"));

        var g = new Guid("11111111-2222-3333-4444-555555555555");
        cid = Marshal.AllocHGlobal(16);
        Marshal.StructureToPtr(g, cid, false);
        Console.WriteLine("  container id = " + g);

        keepAlive = (h, res, ctx, id) =>
        {
            string s = id == IntPtr.Zero ? "(null)" : Marshal.PtrToStringUni(id);
            Console.WriteLine("   callback createResult=0x" + res.ToString("X8") + "  instance=" + s);
        };

        // step 1: minimal validation device, no parent
        IntPtr h1 = IntPtr.Zero;
        int hr1 = -1;
        try { hr1 = CreateOne(null, "MEPTestDevice", @"SWC\MEP_TEST&VEN_8086", "MEP test device", out h1); }
        catch (Exception ex) { Console.WriteLine("  step1 EXCEPTION " + ex.GetType().Name); }
        Console.WriteLine("STEP1 hr=0x" + hr1.ToString("X8") + " handle=0x" + h1.ToInt64().ToString("X"));

        // step 2: the three real MEP component devices
        var names = new string[] { "MEPEffectEngine", "MEPCamera", "MEPVoiceClarity" };
        var hwids = new string[] { @"SWC\MEP_VEN_8086_DEV_B03E", @"SWC\MEP_CAM&VEN_8086_DEV_B03E", @"SWC\MEP_AUD&VEN_8086_VOICEFOCUS_V2" };
        var descs = new string[] { "Windows Studio Effects Driver", "Windows Camera Effects", "Windows Studio Effects Voice Clarity" };
        var handles = new IntPtr[3];
        int[] hrs = new int[3];
        for (int i = 0; i < 3; i++)
        {
            try { hrs[i] = CreateOne(parent, names[i], hwids[i], descs[i], out handles[i]); }
            catch (Exception ex) { Console.WriteLine("  step2[" + i + "] EXCEPTION " + ex.GetType().Name); hrs[i] = -1; }
            Console.WriteLine("STEP2[" + i + "] " + hwids[i] + " hr=0x" + hrs[i].ToString("X8") + " handle=0x" + handles[i].ToInt64().ToString("X"));
        }

        Console.WriteLine("holding 150 s ...");
        Console.Out.Flush();
        Thread.Sleep(150000);
        for (int i = 0; i < 3; i++) if (handles[i] != IntPtr.Zero) SwDeviceClose(handles[i]);
        if (h1 != IntPtr.Zero) SwDeviceClose(h1);
        Console.WriteLine("closed");
        return 0;
    }
}
