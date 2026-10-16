using System;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;

// devcon-style software-device creator: creates PnP devices whose hardware ID is
// SWC\MEP_... so the already staged Windows Studio Effects INFs match and install.
class MepDev
{
    [StructLayout(LayoutKind.Sequential)]
    struct SP_DEVINFO_DATA
    {
        public uint cbSize;
        public Guid ClassGuid;
        public uint DevInst;
        public IntPtr Reserved;
    }

    [DllImport("setupapi.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    static extern IntPtr SetupDiCreateDeviceInfoList(ref Guid classGuid, IntPtr hwndParent);

    [DllImport("setupapi.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    static extern bool SetupDiCreateDeviceInfo(IntPtr set, string deviceName, ref Guid classGuid,
        string description, IntPtr hwndParent, uint creationFlags, ref SP_DEVINFO_DATA data);

    [DllImport("setupapi.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    static extern bool SetupDiSetDeviceRegistryProperty(IntPtr set, ref SP_DEVINFO_DATA data,
        uint property, byte[] buffer, uint size);

    [DllImport("setupapi.dll", SetLastError = true)]
    static extern bool SetupDiRegisterDeviceInfo(IntPtr set, ref SP_DEVINFO_DATA data,
        uint flags, IntPtr compareProc, IntPtr compareContext, IntPtr dupData);

    [DllImport("setupapi.dll", SetLastError = true)]
    static extern bool SetupDiDestroyDeviceInfoList(IntPtr set);

    [DllImport("newdev.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    static extern bool UpdateDriverForPlugAndPlayDevices(IntPtr hwndParent, string hardwareId,
        string fullInfPath, uint installFlags, out bool rebootRequired);

    const uint DICD_GENERATE_ID = 0x00000001;
    const uint SPDRP_HARDWAREID = 0x00000001;
    const uint INSTALLFLAG_FORCE = 0x00000001;
    static readonly Guid SoftwareComponentClass = new Guid("5c4c3332-344d-483c-8739-259e934c9cc8");

    static string FindInf(string marker)
    {
        foreach (var f in Directory.GetFiles(@"C:\Windows\INF", "oem*.inf"))
        {
            try
            {
                string t = File.ReadAllText(f);
                if (t.IndexOf(marker, StringComparison.OrdinalIgnoreCase) >= 0) return f;
            }
            catch { }
        }
        return null;
    }

    static byte[] MultiSzBytes(string s)
    {
        return Encoding.Unicode.GetBytes(s + "\0\0");
    }

    static int CreateOne(string instanceName, string hardwareId, string description)
    {
        Console.WriteLine("== " + hardwareId);
        Guid cls = SoftwareComponentClass;
        IntPtr set = SetupDiCreateDeviceInfoList(ref cls, IntPtr.Zero);
        if (set == new IntPtr(-1)) { Console.WriteLine("   CreateDeviceInfoList failed " + Marshal.GetLastWin32Error()); return -1; }

        var data = new SP_DEVINFO_DATA();
        data.cbSize = (uint)Marshal.SizeOf(typeof(SP_DEVINFO_DATA));
        if (!SetupDiCreateDeviceInfo(set, instanceName, ref cls, description, IntPtr.Zero, DICD_GENERATE_ID, ref data))
        {
            Console.WriteLine("   CreateDeviceInfo failed " + Marshal.GetLastWin32Error());
            SetupDiDestroyDeviceInfoList(set); return -1;
        }

        var hw = MultiSzBytes(hardwareId);
        if (!SetupDiSetDeviceRegistryProperty(set, ref data, SPDRP_HARDWAREID, hw, (uint)hw.Length))
            Console.WriteLine("   SetHardwareId failed " + Marshal.GetLastWin32Error());

        if (!SetupDiRegisterDeviceInfo(set, ref data, 0, IntPtr.Zero, IntPtr.Zero, IntPtr.Zero))
            Console.WriteLine("   RegisterDeviceInfo failed " + Marshal.GetLastWin32Error() + " (already exists is OK)");
        else
            Console.WriteLine("   registered, DevInst=" + data.DevInst);

        string inf = FindInf(hardwareId);
        Console.WriteLine("   matching staged INF: " + (inf ?? "(none)"));
        if (inf != null)
        {
            bool reboot = false;
            bool ok = UpdateDriverForPlugAndPlayDevices(IntPtr.Zero, hardwareId, inf, INSTALLFLAG_FORCE, out reboot);
            Console.WriteLine("   UpdateDriver: " + ok + " err=" + Marshal.GetLastWin32Error() + " reboot=" + reboot);
        }
        SetupDiDestroyDeviceInfoList(set);
        return 0;
    }

    static int Main()
    {
        int rc = 0;
        rc |= CreateOne("MEP_VEN_8086_DEV_B03E", @"SWC\MEP_VEN_8086_DEV_B03E",
                        "Windows Studio Effects Driver");
        rc |= CreateOne("MEP_CAM_VEN_8086_DEV_B03E", @"SWC\MEP_CAM&VEN_8086_DEV_B03E",
                        "Windows Camera Effects");
        rc |= CreateOne("MEP_AUD_VEN_8086_VOICEFOCUS_V2", @"SWC\MEP_AUD&VEN_8086_VOICEFOCUS_V2",
                        "Windows Studio Effects Voice Clarity APO");
        Console.WriteLine("MEPDEV-DONE rc=" + rc);
        return 0;
    }
}
