using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;

// Enumerate Win32 resources in a DLL (the AI workload definitions live in
// Microsoft.Windows.Workloads.Resources.dll) and report which resources mention Lnl / generic.
class ResDump
{
    [DllImport("kernel32", CharSet = CharSet.Unicode, SetLastError = true)]
    static extern IntPtr LoadLibraryExW(string path, IntPtr file, uint flags);
    [DllImport("kernel32")]
    static extern IntPtr FindResourceW(IntPtr h, IntPtr name, IntPtr type);
    [DllImport("kernel32")]
    static extern IntPtr LoadResource(IntPtr h, IntPtr res);
    [DllImport("kernel32")]
    static extern IntPtr LockResource(IntPtr res);
    [DllImport("kernel32")]
    static extern uint SizeofResource(IntPtr h, IntPtr res);
    [DllImport("kernel32")]
    static extern bool FreeLibrary(IntPtr h);

    delegate bool EnumResNameProc(IntPtr hModule, IntPtr lpType, IntPtr lpName, IntPtr lParam);
    [DllImport("kernel32", CharSet = CharSet.Unicode)]
    static extern bool EnumResourceNamesW(IntPtr hModule, IntPtr lpType, EnumResNameProc proc, IntPtr param);

    static readonly List<EnumResNameProc> keep = new List<EnumResNameProc>();
    static IntPtr gModule;
    static List<string> gHits = new List<string>();

    static string NameOf(IntPtr p)
    {
        long v = p.ToInt64();
        if (v >= 0 && v <= 0xFFFF) return "#" + v;
        return Marshal.PtrToStringUni(p) ?? "?";
    }

    static void Dump(IntPtr h, IntPtr type, IntPtr name)
    {
        IntPtr res = FindResourceW(h, name, type);
        if (res == IntPtr.Zero) return;
        uint size = SizeofResource(h, res);
        IntPtr data = LockResource(LoadResource(h, res));
        if (data == IntPtr.Zero || size == 0) return;
        byte[] buf = new byte[size];
        Marshal.Copy(data, buf, 0, (int)size);

        string ascii = Encoding.ASCII.GetString(buf);
        string utf16 = Encoding.Unicode.GetString(buf);
        var marks = new List<string>();
        foreach (var m in new[] { "Lnl", "LNL", "ContentExtraction", "TextRecognition", "365", "ImageSearch", "Analysis" })
        {
            if (ascii.Contains(m) || utf16.Contains(m)) marks.Add(m);
        }
        if (marks.Count > 0)
        {
            gHits.Add(string.Format("    type={0,-8} name={1,-8} size={2,7}  mentions: {3}",
                NameOf(type), NameOf(name), size, string.Join(",", marks)));
        }
    }

    static int Main(string[] args)
    {
        foreach (var path in args)
        {
            Console.WriteLine("=== " + path);
            IntPtr h = LoadLibraryExW(path, IntPtr.Zero, 0x00000002 | 0x00000020); // DATAFILE | IMAGE_RESOURCE
            if (h == IntPtr.Zero) { Console.WriteLine("   load failed err=" + Marshal.GetLastWin32Error()); continue; }
            gModule = h; gHits = new List<string>();
            int total = 0;
            for (int t = 1; t <= 4000; t++)
            {
                IntPtr type = new IntPtr(t);
                EnumResNameProc cb = (mod, ty, nm, prm) => { Dump(mod, ty, nm); return true; };
                keep.Add(cb);
                int before = gHits.Count;
                if (EnumResourceNamesW(h, type, cb, IntPtr.Zero)) total++;
            }
            Console.WriteLine("   numeric resource types tried: " + total);
            Console.WriteLine("   resources mentioning workload names: " + gHits.Count);
            foreach (var s in gHits) Console.WriteLine(s);
            FreeLibrary(h);
            Console.WriteLine();
        }
        return 0;
    }
}
