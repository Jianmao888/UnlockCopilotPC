using System;
using System.Runtime.InteropServices;
using System.Threading;

// Creates the Windows Studio Effects component devices as SOFTWARE DEVICES of the
// computer device -- mirroring how the real "VocaEffectPack" (Voice Clarity) device
// appears at SWD\DRIVERENUM\{...}#<Name>&... with parent SWD\COMPUTER\...
// Uses the API-set name because swdevice.dll is absent on this build.
class SwDev2
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

    [DllImport("api-ms-win-devices-swdevice-l1-1-0.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    static extern int SwDeviceCreate(string enumerator, string parent, ref SW_DEVICE_CREATE_INFO info,
                                     CreateCallback cb, IntPtr ctx, out IntPtr hDevice);

    [DllImport("api-ms-win-devices-swdevice-l1-1-0.dll", SetLastError = true)]
    static extern void SwDeviceClose(IntPtr hDevice);

    static CreateCallback keepAlive;

    static IntPtr MultiSz(string s) { return Marshal.StringToHGlobalUni(s + "\0\0"); }

    static int CreateOne(string parent, string instanceId, string hardwareId, string description, out IntPtr handle)
    {
        var info = new SW_DEVICE_CREATE_INFO();
        info.cbSize = (uint)Marshal.SizeOf(typeof(SW_DEVICE_CREATE_INFO));
        info.pszInstanceId = Marshal.StringToHGlobalUni(instanceId);
        info.pszzHardwareIds = MultiSz(hardwareId);
        info.pszzCompatibleIds = MultiSz("SWC\\Generic\0SWD\\GenericRaw\0SWD\\Generic");
        info.pContainerId = IntPtr.Zero;
        info.CapabilityFlags = 0;
        info.pszDeviceDescription = Marshal.StringToHGlobalUni(description);
        info.pszDeviceLocation = Marshal.StringToHGlobalUni("WindowsStudioEffects");
        info.pSecurityDescriptor = IntPtr.Zero;
        return SwDeviceCreate("SWD", parent, ref info, keepAlive, IntPtr.Zero, out handle);
    }

    static int Main(string[] args)
    {
        string parent = args.Length > 0 ? args[0] : null;
        keepAlive = (h, res, ctx, id) =>
        {
            string s = id == IntPtr.Zero ? "(null)" : Marshal.PtrToStringUni(id);
            Console.WriteLine("   callback createResult=0x" + res.ToString("X8") + "  instance=" + s);
        };

        Console.WriteLine("SwDeviceCreate via API set; parent=" + (parent ?? "(default)"));
        var handles = new IntPtr[3];
        int[] hr = new int[3];
        hr[0] = CreateOne(parent, "MEPEffectEngine", @"SWC\MEP_VEN_8086_DEV_B03E", "Windows Studio Effects Driver", out handles[0]);
        hr[1] = CreateOne(parent, "MEPCamera", @"SWC\MEP_CAM&VEN_8086_DEV_B03E", "Windows Camera Effects", out handles[1]);
        hr[2] = CreateOne(parent, "MEPVoiceClarity", @"SWC\MEP_AUD&VEN_8086_VOICEFOCUS_V2", "Windows Studio Effects Voice Clarity", out handles[2]);
        for (int i = 0; i < 3; i++)
            Console.WriteLine("   create[" + i + "] hr=0x" + hr[i].ToString("X8") + " handle=0x" + handles[i].ToInt64().ToString("X"));

        Console.WriteLine("holding for 180 seconds ...");
        Console.Out.Flush();
        Thread.Sleep(180000);
        for (int i = 0; i < 3; i++) if (handles[i] != IntPtr.Zero) SwDeviceClose(handles[i]);
        Console.WriteLine("closed");
        return 0;
    }
}
