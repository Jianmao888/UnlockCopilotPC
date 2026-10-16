'use strict';
// Preserve only the existing exact optional URI-argument workaround. Do not hook
// RaiseException/RtlRaiseException or install a native exception handler.
if (Process.mainModule.name.toLowerCase() !== 'clicktodo.exe') throw Error('Wrong target');
const hooks=[];
const observer=Process.attachModuleObserver({onAdded(m){
 if(m.name.toLowerCase()!=='discoveryoverlay.dll')return;
 hooks.push(Interceptor.attach(m.base.add(0x2b130),{onEnter(args){
  const hr=args[1].toUInt32();
  if(hr!==0x80070057||this.returnAddress.sub(m.base).toUInt32()!==0x1bfbbb)return;
  try{
   const line=args[2].readU32(),file=args[2].add(8).readPointer().readCString();
   if(line===2330&&/\\Windows\.Foundation\.h$/i.test(file)){
    args[1]=ptr(0);send({event:'optional-source-miss',original:'0x80070057',forced:0});
   }
  }catch(e){send({event:'optional-source-inspect-failed',message:String(e)});}
 }}));
 send({event:'optional-source-only-ready'});
}});
rpc.exports={cleanup(){observer.detach();hooks.forEach(h=>h.detach());return true;}};
