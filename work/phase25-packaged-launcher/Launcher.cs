using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Security.Cryptography;
using System.Security.Principal;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using System.Web.Script.Serialization;
using System.Windows.Forms;

static class ClickToDoLauncher {
 const string ManifestSha256="__MANIFEST_SHA256__";
 static readonly string Root=AppDomain.CurrentDomain.BaseDirectory.TrimEnd(Path.DirectorySeparatorChar);
 static readonly JavaScriptSerializer Json=new JavaScriptSerializer();
 static Dictionary<string,object> Config;
 static string ConfigString(string key){return (string)Config[key];}
 static string Hash(string path){using(var sha=SHA256.Create())using(var f=File.OpenRead(path))return BitConverter.ToString(sha.ComputeHash(f)).Replace("-","").ToLowerInvariant();}
 static void Verify(){
  string manifest=Path.Combine(Root,"manifest.json");
  if(Hash(manifest)!=ManifestSha256)throw new Exception("启动器文件清单发生变化，请重新核对版本。");
  var items=Json.Deserialize<List<Dictionary<string,string>>>(File.ReadAllText(manifest,Encoding.UTF8));
  foreach(var item in items){
   string path=Path.GetFullPath(Path.Combine(Root,item["path"]));
   if(!path.StartsWith(Root+Path.DirectorySeparatorChar,StringComparison.OrdinalIgnoreCase)||Hash(path)!=item["sha256"])throw new Exception("启动文件缺失或已被修改："+item["path"]);
  }
  Config=Json.Deserialize<Dictionary<string,object>>(File.ReadAllText(Path.Combine(Root,"config.json"),Encoding.UTF8));
 }
 static string Quote(string value){
  if(value.IndexOf('"')>=0||value.EndsWith("\\"))throw new ArgumentException("Unexpected quoted path");
  return "\""+value+"\"";
 }
 sealed class Child:IDisposable {
  public Process Process;
  FileStream Output,Error;
  Task OutTask,ErrTask;
  public Child(string exe,string args,string logName){
   string logs=Path.Combine(Root,"logs");Directory.CreateDirectory(logs);
   Output=new FileStream(Path.Combine(logs,logName+".stdout.txt"),FileMode.Create,FileAccess.Write,FileShare.ReadWrite);
   Error=new FileStream(Path.Combine(logs,logName+".stderr.txt"),FileMode.Create,FileAccess.Write,FileShare.ReadWrite);
   var start=new ProcessStartInfo(exe,args){UseShellExecute=false,CreateNoWindow=true,WindowStyle=ProcessWindowStyle.Hidden,RedirectStandardOutput=true,RedirectStandardError=true,WorkingDirectory=Root};
   Process=System.Diagnostics.Process.Start(start);
   OutTask=Process.StandardOutput.BaseStream.CopyToAsync(Output);
   ErrTask=Process.StandardError.BaseStream.CopyToAsync(Error);
  }
  public int Wait(){Process.WaitForExit();Task.WaitAll(OutTask,ErrTask);return Process.ExitCode;}
  public void Dispose(){Output.Dispose();Error.Dispose();Process.Dispose();}
 }
 static string PsArgs(string script,string extra){return "-NoLogo -NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File "+Quote(script)+" "+extra;}
 static int RunPs(string script,string extra,string log){using(var child=new Child(ConfigString("PowerShellExe"),PsArgs(script,extra),log))return child.Wait();}
 static int Admin(string label,int seconds){
  if(!new WindowsPrincipal(WindowsIdentity.GetCurrent()).IsInRole(WindowsBuiltInRole.Administrator))throw new Exception("后台宿主控制器需要管理员权限。");
  if(!System.Text.RegularExpressions.Regex.IsMatch(label,"^[a-z0-9-]+$")||seconds<120||seconds>1800)throw new Exception("Invalid bounded session arguments");
  string host=Path.Combine(Root,"runtime","phase21-host-ifeo");
  string stop=Path.Combine(host,label+"-stop.signal");
  using(var arm=new Child(ConfigString("PowerShellExe"),PsArgs(Path.Combine(host,"Arm-HostStartupProbe.ps1"),"-Label "+label+" -Mode patch -DurationSeconds "+seconds),label+"-admin")){
   Child models=null;
   try{
    var deadline=DateTime.UtcNow.AddSeconds(20);
    while(!File.Exists(Path.Combine(host,label+"-ready.signal"))){if(arm.Process.HasExited)throw new Exception("后台控制器启动失败，请查看 logs。");if(DateTime.UtcNow>deadline)throw new TimeoutException("Arming timeout");Thread.Sleep(100);}
    models=new Child(ConfigString("PythonWindowlessExe"),Quote(Path.Combine(host,"attach-real-hosts.py"))+" --label "+label+" --duration-seconds "+seconds,label+"-models");
    while(!arm.Process.WaitForExit(250)){
     if(models.Process.HasExited){File.WriteAllText(stop,"model controller exited");break;}
    }
    return arm.Wait();
   }finally{
    File.WriteAllText(stop,"stop");
    if(!arm.Process.WaitForExit(10000))throw new Exception("后台清理尚未完成，请查看日志。");
    if(models!=null){models.Process.WaitForExit(6000);models.Dispose();}
   }
  }
 }
 [STAThread] static int Main(string[] args){
  try{
   Verify();
   string mode=args.Length==0?"--open":args[0];
   string manual=Path.Combine(Root,"runtime","phase24-manual-test");
   if(mode=="--selfcheck"){
    File.WriteAllText(Path.Combine(Root,"selfcheck.json"),Json.Serialize(new {TimeUtc=DateTime.UtcNow.ToString("o"),ManifestValid=true,NoHookStarted=true,PowerShellExists=File.Exists(ConfigString("PowerShellExe")),PythonWindowlessExists=File.Exists(ConfigString("PythonWindowlessExe"))}),Encoding.UTF8);return 0;
   }
   if(mode=="--process-check"){
    using(var child=new Child(ConfigString("PowerShellExe"),"-NoLogo -NoProfile -NonInteractive -WindowStyle Hidden -Command \"exit 0\"","process-check"))return child.Wait();
   }
   if(mode=="--controller")return RunPs(Path.Combine(manual,"Start-ManualHookSession.ps1"),"-DurationSeconds 900","controller");
   if(mode=="--admin")return Admin(args[1],Int32.Parse(args[2]));
   if(mode!="--open"&&mode!="--stop"&&mode!="--warm")throw new Exception("Unknown launcher mode");
   int code=RunPs(Path.Combine(Root,"Dispatch.ps1"),"-Action "+(mode=="--stop"?"Stop":mode=="--warm"?"Warm":"Open"),"dispatch-"+DateTime.Now.ToString("yyyyMMdd-HHmmss-fff"));
   if(code!=0)throw new Exception("启动或关闭失败。详细原因已写入启动器目录的 logs。");
   return code;
  }catch(Exception error){
   try{Directory.CreateDirectory(Path.Combine(Root,"logs"));File.AppendAllText(Path.Combine(Root,"logs","launcher-errors.txt"),DateTime.Now.ToString("o")+" "+error+Environment.NewLine,Encoding.UTF8);}catch{}
   if(args.Length==0||args[0]=="--open"||args[0]=="--stop")MessageBox.Show(error.Message,"单击以执行（实验版）",MessageBoxButtons.OK,MessageBoxIcon.Information);
   return 1;
  }
 }
}
