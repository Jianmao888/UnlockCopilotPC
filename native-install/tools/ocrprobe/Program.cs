using System;
using System.Runtime.InteropServices;
using System.Threading;

// Standalone TextRecognizer readiness probe: no package identity, no app.
class OcrProbe
{
    [DllImport("combase.dll")] static extern int RoInitialize(uint kind);
    [DllImport("combase.dll")] static extern int WindowsCreateString([MarshalAs(UnmanagedType.LPWStr)] string s, uint len, out IntPtr h);
    [DllImport("combase.dll")] static extern int WindowsDeleteString(IntPtr h);
    [DllImport("combase.dll")] static extern int RoGetActivationFactory(IntPtr cls, ref Guid iid, out IntPtr fac);

    static readonly Guid IActivationFactory = new Guid("00000035-0000-0000-C000-000000000046");
    static readonly Guid ITextRecognizerStatics = new Guid("3788c2fd-e496-53ab-85a7-e54a135824e9");

    static IntPtr Slot(IntPtr o, int i) { return Marshal.ReadIntPtr(Marshal.ReadIntPtr(o), i * IntPtr.Size); }
    static string H(int hr) { return "0x" + unchecked((uint)hr).ToString("X8"); }

    [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate int GetReadyStateFn(IntPtr self, out int state);
    [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate int EnsureReadyFn(IntPtr self, out IntPtr op);
    [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate int GetStatusFn(IntPtr self, out int st);
    [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate int GetProgressFn(IntPtr self, out double p);
    [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate int GetErrorCodeFn(IntPtr self, out int e);
    [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate int CreateFn(IntPtr self, out IntPtr op);
    [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate int GetResultsFn(IntPtr self, out IntPtr result);

    static int Main()
    {
        // when launched as a packaged app there is no visible console: mirror everything to a file
        try
        {
            var sw = new System.IO.StreamWriter(
                @"C:\Users\jianm\Code\DeepseekHarness\native-install\probe-out.txt", false, System.Text.Encoding.UTF8);
            sw.AutoFlush = true;
            Console.SetOut(sw);
        }
        catch { }

        Console.WriteLine("packaged identity probe: " + DateTime.Now.ToString("o"));
        Console.WriteLine("RoInitialize      : " + H(RoInitialize(1)));

        IntPtr cls;
        int hr = WindowsCreateString("Microsoft.Windows.AI.Imaging.TextRecognizer",
            (uint)"Microsoft.Windows.AI.Imaging.TextRecognizer".Length, out cls);
        Console.WriteLine("WindowsCreateString: " + H(hr));
        if (hr < 0) return 1;

        Guid af = IActivationFactory;
        IntPtr fac;
        hr = RoGetActivationFactory(cls, ref af, out fac);
        WindowsDeleteString(cls);
        Console.WriteLine("RoGetActivationFactory: " + H(hr) + "  factory=0x" + fac.ToInt64().ToString("X"));
        if (hr < 0) { Console.WriteLine("=> activation blocked (package identity or capability?)"); return 2; }

        Guid si = ITextRecognizerStatics;
        IntPtr iface;
        hr = Marshal.QueryInterface(fac, ref si, out iface);
        Console.WriteLine("QI(ITextRecognizerStatics): " + H(hr));
        if (hr < 0) return 3;

        var getReady = Marshal.GetDelegateForFunctionPointer<GetReadyStateFn>(Slot(iface, 6));
        int state = -1;
        hr = getReady(iface, out state);
        Console.WriteLine("GetReadyState     : hr=" + H(hr) + "  state=" + state + "   (0=Ready 1=NotReady 5=NotSupported)");
        // continue regardless of GetReadyState: the service-side platform patch shows up in Ensure/Create

        Console.WriteLine();
        Console.WriteLine("calling EnsureReadyAsync (slot 7) ...");
        var ensure = Marshal.GetDelegateForFunctionPointer<EnsureReadyFn>(Slot(iface, 7));
        IntPtr op;
        hr = ensure(iface, out op);
        Console.WriteLine("EnsureReadyAsync  : hr=" + H(hr) + "  op=0x" + op.ToInt64().ToString("X"));
        if (hr < 0 || op == IntPtr.Zero) return 5;

        var getStatus = Marshal.GetDelegateForFunctionPointer<GetStatusFn>(Slot(op, 7));
        var getProgress = Marshal.GetDelegateForFunctionPointer<GetProgressFn>(Slot(op, 15));
        var getErrorCode = Marshal.GetDelegateForFunctionPointer<GetErrorCodeFn>(Slot(op, 8));

        for (int i = 1; i <= 15; i++)
        {
            int st = -1, ec = 0; double pr = -1;
            int h1 = getStatus(op, out st);
            int h2 = getProgress(op, out pr);
            int h3 = getErrorCode(op, out ec);
            Console.WriteLine(string.Format("  t={0,2}s status={1} progress={2} errcode={3}   (hr {4}/{5}/{6})",
                i * 2, st, pr, H(ec), H(h1), H(h2), H(h3)));
            if (st != 0) { Console.WriteLine("  => async finished with status " + st); break; }
            Thread.Sleep(2000);
        }
        Console.WriteLine();
        Console.WriteLine("(status: 0=Started 1=Completed 2=Canceled 3=Error)");

        Console.WriteLine();
        Console.WriteLine("calling CreateAsync (slot 8) -- this is what the platform patch affects ...");
        var create = Marshal.GetDelegateForFunctionPointer<CreateFn>(Slot(iface, 8));
        IntPtr cop;
        int hrc = create(iface, out cop);
        Console.WriteLine("CreateAsync       : hr=" + H(hrc) + "  op=0x" + cop.ToInt64().ToString("X"));
        if (hrc >= 0 && cop != IntPtr.Zero)
        {
            var cStatus = Marshal.GetDelegateForFunctionPointer<GetStatusFn>(Slot(cop, 7));
            var cErr = Marshal.GetDelegateForFunctionPointer<GetErrorCodeFn>(Slot(cop, 8));
            var cResults = Marshal.GetDelegateForFunctionPointer<GetResultsFn>(Slot(cop, 13));
            for (int i = 1; i <= 20; i++)
            {
                int st = -1, ec = 0;
                int h1 = cStatus(cop, out st);
                int h2 = cErr(cop, out ec);
                Console.WriteLine(string.Format("  create t={0,2}s status={1} errcode={2}  (hr {3}/{4})", i * 2, st, H(ec), H(h1), H(h2)));
                if (st != 0) { Console.WriteLine("  => create finished, status=" + st); break; }
                Thread.Sleep(2000);
            }
            IntPtr res;
            int hr3 = cResults(cop, out res);
            Console.WriteLine("CreateAsync GetResults: hr=" + H(hr3) + "  object=0x" + res.ToInt64().ToString("X"));
        }
        return 0;
    }
}
