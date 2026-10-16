using System;
using System.Runtime.InteropServices;
using System.Threading;

// Creates Windows Studio Effects software-component devices without the Intel NPU,
// so that the (already staged) MEP driver packages install and the
// KSCATEGORY_WINDOWS_CAMERAEFFECTS interface appears.
class SwDevHost
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

    delegate void CreateCallback(IntPtr hSwDevice, int createResult, IntPtr pContext, IntPtr pszDeviceInstanceId);

    [DllImport("swdevice.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    static extern int SwDeviceCreate(string enumerator, string parent, ref SW_DEVICE_CREATE_INFO info,
                                     CreateCallback cb, IntPtr ctx, out IntPtr hDevice);

    [DllImport("swdevice.dll", SetLastError = true)]
    static extern void SwDeviceClose(IntPtr hDevice);

    static CreateCallback keepAlive;   // must not be collected

    static IntPtr MultiSz(params string[] s)
    {
        string joined = string.Join("\0", s) + "\0\0";
        return Marshal.StringToHGlobalUni(joined);
    }

    static int Create(string instanceId, string hardwareIds, string description, out IntPtr handle)
    {
        var info = new SW_DEVICE_CREATE_INFO();
        info.cbSize = (uint)Marshal.SizeOf(typeof(SW_DEVICE_CREATE_INFO));
        info.pszInstanceId = Marshal.StringToHGlobalUni(instanceId);
        info.pszzHardwareIds = MultiSz(hardwareIds);
        info.pszzCompatibleIds = MultiSz();
        info.pContainerId = IntPtr.Zero;
        info.CapabilityFlags = 0;
        info.pszDeviceDescription = Marshal.StringToHGlobalUni(description);
        info.pszDeviceLocation = Marshal.StringToHGlobalUni("WindowsStudioEffects");
        info.pSecurityDescriptor = IntPtr.Zero;

        IntPtr h;
        int hr = SwDeviceCreate("SWD", null, ref info, keepAlive, IntPtr.Zero, out h);
        handle = h;
        return hr;
    }

    static int Main()
    {
        keepAlive = (h, res, ctx, id) =>
        {
            string s = id == IntPtr.Zero ? "(null)" : Marshal.PtrToStringUni(id);
            Console.WriteLine("   callback: createResult=0x" + res.ToString("X8") + "  instance=" + s);
        };

        Console.WriteLine("creating Windows Studio Effects software devices");
        var handles = new IntPtr[3];
        int[] hrs = new int[3];

        hrs[0] = Create("MEP_VEN_8086_DEV_B03E", "SWC\\MEP_VEN_8086_DEV_B03E",
                        "Windows Studio Effects Driver", out handles[0]);
        hrs[1] = Create("MEP_CAM_VEN_8086_DEV_B03E", "SWC\\MEP_CAM&VEN_8086_DEV_B03E",
                        "Windows Camera Effects", out handles[1]);
        hrs[2] = Create("MEP_AUD_VEN_8086_VOICEFOCUS_V2", "SWC\\MEP_AUD&VEN_8086_VOICEFOCUS_V2",
                        "Windows Studio Effects Voice Clarity APO", out handles[2]);

        for (int i = 0; i < 3; i++)
            Console.WriteLine("   create[" + i + "] hr=0x" + hrs[i].ToString("X8") + " handle=0x" + handles[i].ToInt64().ToString("X"));

        Console.WriteLine("holding devices for 240 seconds ...");
        Console.Out.Flush();
        Thread.Sleep(240000);

        for (int i = 0; i < 3; i++) if (handles[i] != IntPtr.Zero) SwDeviceClose(handles[i]);
        Console.WriteLine("closed");
        return 0;
    }
}
