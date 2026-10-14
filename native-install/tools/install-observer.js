'use strict';
// Observe one self-created request probe. Optional, one-call reduction of the
// exact root registry open to real OS-enforced read rights; never force success.
const narrowReadMask = true;
let accessChanges=0;
const seen = new Set();
let active = false;
function stack(ctx) {
  return Thread.backtrace(ctx, Backtracer.ACCURATE).slice(0, 14).map(p => {
    const m=Process.findModuleByAddress(p);
    return m ? m.name+'+0x'+p.sub(m.base).toString(16) : p.toString();
  });
}
function text(p) {try{return p.isNull()?'':p.readUtf16String();}catch(e){return '<unreadable>';}}
function hook(module,name,kind) {
  let p;
  try {p=Process.getModuleByName(module).getExportByName(name);}catch(e){return;}
  if(seen.has(p.toString()))return;
  seen.add(p.toString());
  Interceptor.attach(p,{
    onEnter(args) {
      this.enabled=active;
      if(!this.enabled)return;
      this.s=stack(this.context);
      this.detail={};
      if(kind==='reg')this.detail={key:args[0].toString(),subkey:text(args[1]),access:args[3].toString()};
      if(narrowReadMask && accessChanges<8 && name==='RegOpenKeyExW' &&
         args[0].equals(ptr('0xffffffff80000002')) && text(args[1])==='SOFTWARE' &&
         args[3].toUInt32()===0xf003f){
        const caller=Process.findModuleByAddress(this.returnAddress);
        if(caller && caller.name==='Microsoft.UALite.Plugin.MsixDeployment.dll' &&
           this.returnAddress.sub(caller.base).toUInt32()===0x996e6){
          args[3]=ptr(0x20019);accessChanges++;
          send({event:'narrow-access-request',occurrence:accessChanges,callsite:'MsixDeployment+0x996e6',from:'0xf003f',to:'0x20019',stack:this.s});
        }
      }
      if(kind==='create')this.detail={key:args[0].toString(),subkey:text(args[1]),access:args[5].toString()};
      if(kind==='file')this.detail={path:text(args[0]),access:args[1].toString()};
    },
    onLeave(ret) {
      if(!this.enabled)return;
      const value=ret.toInt32();
      if(kind==='file' && !ret.equals(ptr(-1)))return;
      if(kind==='bool' && value!==0)return;
      if(kind!=='file' && kind!=='bool' && value===0)return;
      if(!this.s.some(x=>x.includes('UALite')||x.includes('ualite')))return;
      send({event:'api-result',name,result:ret.toString(),lastError:this.lastError,detail:this.detail,stack:this.s});
    }
  });
}
hook('advapi32.dll','RegOpenKeyExW','reg');
hook('advapi32.dll','RegCreateKeyExW','create');
hook('advapi32.dll','RegGetValueW','reg');
hook('advapi32.dll','OpenThreadToken','bool');
hook('advapi32.dll','SetThreadToken','bool');
hook('kernelbase.dll','CreateFileW','file');
const gp=Process.getModuleByName('kernel32.dll').getExportByName('GetProcAddress');
Interceptor.attach(gp,{
  onEnter(args) {
    this.name='';this.s=[];
    if(!active)return;
    try{if(args[1].compare(ptr(65535))>0)this.name=args[1].readCString();}catch(e){}
    if(/^(SR|Msix|Appx|GetPackages|FindPackages|GetPackage|OpenPackage)/.test(this.name))this.s=stack(this.context);
  },
  onLeave(ret) {
    if(!this.s.length || !this.s.some(x=>x.includes('MsixDeployment')))return;
    send({event:'dynamic-api',name:this.name,address:ret.toString(),stack:this.s});
    if(ret.isNull()||seen.has(ret.toString())||!this.name.startsWith('SR'))return;
    seen.add(ret.toString());
    const n=this.name;
    Interceptor.attach(ret,{onEnter(){this.s=stack(this.context);},onLeave(r){send({event:'state-api-result',name:n,result:r.toString(),stack:this.s});}});
  }
});
Process.attachModuleObserver({onAdded(m){
  if(m.name.toLowerCase()==='microsoft.ualite.plugin.msixdeployment.dll'){
    active=true;send({event:'plugin-loaded',name:m.name,base:m.base.toString()});
  }
}});
send({event:'ready',pid:Process.id});
