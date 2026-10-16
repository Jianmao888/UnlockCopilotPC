using System;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;

class ApiSurvey
{
    [DllImport("combase.dll")] static extern int RoInitialize(uint mode);
    [DllImport("combase.dll", CharSet = CharSet.Unicode)] static extern int WindowsCreateString(string s, uint len, out IntPtr h);
    [DllImport("combase.dll")] static extern int WindowsDeleteString(IntPtr h);
    [DllImport("combase.dll")] static extern int RoGetActivationFactory(IntPtr cls, ref Guid iid, out IntPtr fac);

    static IntPtr Slot(IntPtr o, int i) => Marshal.ReadIntPtr(Marshal.ReadIntPtr(o), i * IntPtr.Size);
    static string H(int hr) => "0x" + unchecked((uint)hr).ToString("X8");

    [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate int GetReadyStateFn(IntPtr self, out int state);
    [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate int EnsureFn(IntPtr self, out IntPtr op);

    static readonly Guid IActivationFactory = new Guid("00000035-0000-0000-C000-000000000046");

    static readonly string[,] Targets = new string[,] {
        { "Microsoft.Windows.AI.Imaging.TextRecognizer",            "3788c2fd-e496-53ab-85a7-e54a135824e9" },
        { "Microsoft.Windows.AI.Imaging.ImageScaler",               "75380c81-9c7f-544b-9337-6e638cfb464a" },
        { "Microsoft.Windows.AI.Imaging.ImageDescriptionGenerator", "5fb50b2a-5700-55a7-b413-6073b4b7f175" },
        { "Microsoft.Windows.AI.Imaging.ImageGenerator",            "38eb37d2-bb6b-5424-a010-58b1d975e6ba" },
        { "Microsoft.Windows.AI.Imaging.ImageObjectExtractor",      "38fa261e-2c33-54cb-9e10-98d50685743d" },
        { "Microsoft.Windows.AI.Imaging.ImageObjectRemover",        "cbcbd7e1-5b81-503f-8fcb-66ae1d6e5b9c" },
        { "Microsoft.Windows.AI.Imaging.ImageForegroundExtractor",  "ffe2e9f1-d6ce-53b7-aaa1-cf1ec9039868" },
        { "Microsoft.Windows.AI.Text.LanguageModel",                "8f18f9af-6095-553b-8d9d-6bcc98026546" },
        { "Microsoft.Windows.AI.Speech.SpeechRecognitionModel",     "cdba31c1-2b5a-58fc-a8e9-deb640372526" },
        { "Microsoft.Windows.AI.Video.VideoScaler",                 "311dd8bb-b7ac-55a7-a3d3-1a6c84430f84" },
    };

    static int Main()
    {
        string outPath = @"C:\Users\jianm\Code\DeepseekHarness\native-install\probe-out.txt";
        var sw = new StreamWriter(outPath, false, new UTF8Encoding(false));
        sw.AutoFlush = true;
        Console.SetOut(sw);

        Console.WriteLine("AI API survey  " + DateTime.Now.ToString("o"));
        Console.WriteLine("RoInitialize: " + H(RoInitialize(1)));
        Console.WriteLine();

        for (int t = 0; t < Targets.GetLength(0); t++)
        {
            string cls = Targets[t, 0];
            string iid = Targets[t, 1];
            Console.WriteLine("== " + cls);
            IntPtr hcls;
            WindowsCreateString(cls, (uint)cls.Length, out hcls);
            Guid g = IActivationFactory;
            IntPtr fac;
            int hr = RoGetActivationFactory(hcls, ref g, out fac);
            WindowsDeleteString(hcls);
            if (hr < 0) { Console.WriteLine("   activation      : " + H(hr)); Console.WriteLine(); continue; }

            Guid sg = new Guid(iid);
            IntPtr iface;
            int h2 = Marshal.QueryInterface(fac, ref sg, out iface);
            if (h2 < 0) { Console.WriteLine("   QI statics      : " + H(h2)); Console.WriteLine(); continue; }

            int st = -1;
            int h3 = Marshal.GetDelegateForFunctionPointer<GetReadyStateFn>(Slot(iface, 6))(iface, out st);
            Console.WriteLine("   GetReadyState   : hr=" + H(h3) + " state=" + st + "   (0=Ready 1=NotReady 5=NotSupported)");

            IntPtr op;
            int h4 = Marshal.GetDelegateForFunctionPointer<EnsureFn>(Slot(iface, 7))(iface, out op);
            Console.WriteLine("   EnsureReadyAsync: hr=" + H(h4) + " op=0x" + op.ToInt64().ToString("X"));
            Console.WriteLine();
            Thread.Sleep(300);
        }
        Console.WriteLine("SURVEY-DONE");
        sw.Close();
        return 0;
    }
}
