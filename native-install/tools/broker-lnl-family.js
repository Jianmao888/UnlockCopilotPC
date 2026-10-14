'use strict';
// Same mechanism as the verified phase15 experiment, retargeted to the Intel (Lnl) OCR
// session family: that package carries lnl.txt (local recognizer) and oneocr.dll, while the
// .365 package carries 365.txt and delegates to the (absent) HybridCompute backend.
const host=Process.getModuleByName('WSAIFabricHost.dll'),start=Date.now(),ole=Process.getModuleByName('oleaut32.dll');
const allocString=new NativeFunction(ole.getExportByName('SysAllocString'),'pointer',['pointer'],'win64');
const freeString=new NativeFunction(ole.getExportByName('SysFreeString'),'void',['pointer'],'win64');
function emit(event,data={}){send({event,pid:Process.id,elapsedMs:Date.now()-start,...data});}
function text(p){try{return p.isNull()?'':p.readUtf16String();}catch{return '<unreadable>';}}
const expected='Microsoft.Windows.AI.Imaging.TextRecognizer';
const originalFamily='WindowsWorkload.TextRecognition.1_8wekyb3d8bbwe';
const selected='WindowsWorkload.TextRecognition.Lnl.1_8wekyb3d8bbwe';
Interceptor.attach(host.base.add(0x71210),{
 onEnter(args){this.path=text(args[1]);this.api=text(args[2]);this.out=args[4];this.track=this.api===expected;},
 onLeave(hr){
  if(!this.track)return;
  if(hr.toInt32()<0 || this.out.isNull()){emit('broker-session-family',{path:this.path,api:this.api,hr:'0x'+hr.toUInt32().toString(16),modified:false});return;}
  const old=this.out.readPointer(),family=text(old);
  let modified=false;
  if(family===originalFamily){
   const next=allocString(Memory.allocUtf16String(selected));
   if(!next.isNull()){this.out.writePointer(next);freeString(old);modified=true;}
  }
  emit('broker-session-family',{path:this.path,api:this.api,original:family,selected:modified?selected:family,hr:'0x'+hr.toUInt32().toString(16),modified});
 }
});
emit('broker-route-ready',{host:host.path,scope:'OCR session family to Lnl (local oneocr path)'});
