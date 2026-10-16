'use strict';
const listeners=[],models=new Map(),counts={},sessions=new Map(),tables=new Set(),engines=new Set();
function read(p,w=false){try{return p.isNull()?null:(w?p.readUtf16String():p.readUtf8String());}catch(_){return null;}}
function emit(event,fields={}){send({event,...fields});}
function hook(address,callbacks){const l=Interceptor.attach(address,callbacks);listeners.push(l);return l;}
function normalize(s){return s.replace(/^\\\\\?\\/,'').replace(/\//g,'\\').toLowerCase();}
const expected=normalize(profile.driverDirectory),cameraExpected=normalize(profile.cameraDirectory);
const kb=Process.getModuleByName('kernelbase.dll'),nt=Process.getModuleByName('ntdll.dll');
function redirected(name){if(!name)return null;const base=name.split('\\').pop().toLowerCase();return /^(openvino_intel_cpu_plugin|openvino_ir_frontend)\.dll$/.test(base)?profile.runtimeDirectory+'\\'+base:null;}
for(const item of profile.models){const data=File.readAllBytes(item.path),p=Memory.alloc(data.byteLength);p.writeByteArray(data);models.set(item.originalSize,{...item,p,size:data.byteLength});}
function redirectLibrary(args,wide){const path=read(args[0],wide),target=redirected(path);if(target){this.path=wide?Memory.allocUtf16String(target):Memory.allocUtf8String(target);args[0]=this.path;}}
for(const name of ['LoadLibraryExW','LoadLibraryW','LoadLibraryExA','LoadLibraryA']){const p=kb.findExportByName(name);if(p)hook(p,{onEnter(a){redirectLibrary.call(this,a,name.endsWith('W'));}});}
hook(nt.getExportByName('LdrLoadDll'),{onEnter(a){const name=read(a[2].add(8).readPointer(),true),target=redirected(name);if(target){this.buf=Memory.allocUtf16String(target);this.us=Memory.alloc(16);this.us.writeU16(target.length*2);this.us.add(2).writeU16(target.length*2+2);this.us.add(8).writePointer(this.buf);a[2]=this.us;}}});
hook(kb.getExportByName('CreateFileW'),{onEnter(a){const target=redirected(read(a[0],true));if(target){this.path=Memory.allocUtf16String(target);a[0]=this.path;}}});
for(const name of ['FindFirstFileW','FindFirstFileExW']){const p=kb.findExportByName(name);if(p)hook(p,{onEnter(a){const pattern=read(a[0],true);if(pattern&&normalize(pattern).startsWith(expected+'\\')&&pattern.slice(expected.length+1).indexOf('\\')===-1&&pattern.includes('*')){this.pattern=Memory.allocUtf16String(profile.runtimeDirectory+'\\'+pattern.split('\\').pop());a[0]=this.pattern;}}});}
function matches(pointer,hex){const b=new Uint8Array(pointer.readByteArray(hex.length/2));for(let i=0;i<b.length;i++)if(b[i]!==parseInt(hex.slice(i*2,i*2+2),16))return false;return true;}
function bindEngine(m){
 if(normalize(m.path)!==expected+'\\perceptioncore.dll'){emit('unsupported_engine',{path:m.path});return;}
 const identity=String(m.base);if(engines.has(identity))return;engines.add(identity);
 const getBase=m.base.add(0x2484a8).readPointer(),ps=getBase.sub(0x29770);if(ps.readU16()!==0x5a4d)throw Error('ORT base validation failed');
 const base=new NativeFunction(getBase,'pointer',[])(),table=new NativeFunction(base.readPointer(),'pointer',['uint'])(17);
 if(table.isNull())throw Error('ORT API 17 unavailable');if(tables.has(String(table)))return;tables.add(String(table));
 const error=new NativeFunction(table.add(16).readPointer(),'pointer',['pointer']);
 function result(kind,status,fields={}){if(!status.isNull())emit(kind,{...fields,error:read(error(status)),status:String(status)});}
 hook(table.add(216*8).readPointer(),{onEnter(a){if(read(a[1])!=='OpenVINO')return;this.k=Memory.allocUtf8String('device_type');this.v=Memory.allocUtf8String('CPU');this.keys=Memory.alloc(8);this.values=Memory.alloc(8);this.keys.writePointer(this.k);this.values.writePointer(this.v);a[2]=this.keys;a[3]=this.values;a[4]=ptr(1);emit('provider_cpu');},onLeave(r){result('provider_error',r);}});
 hook(table.add(68*8).readPointer(),{onEnter(a){if(!/OpenVINO|NPU/i.test(read(a[0])||''))return;this.name=Memory.allocUtf8String('Cpu');a[0]=this.name;a[1]=ptr(1);a[2]=ptr(0);a[3]=ptr(0);}});
 hook(table.add(131*8).readPointer(),{onLeave(r){result('allocator_error',r);}});
 hook(table.add(8*8).readPointer(),{onEnter(a){this.out=a[4];this.originalSize=a[2].toUInt32();const model=models.get(this.originalSize);if(model&&matches(a[1],model.originalHead)&&matches(a[1].add(this.originalSize-model.originalTail.length/2),model.originalTail)){a[1]=model.p;a[2]=ptr(model.size);this.model=model.name;emit('model_replaced',{model:this.model});}},onLeave(r){if(r.isNull()){const session=String(this.out.readPointer());sessions.set(session,this.model||'unconverted:'+this.originalSize);emit('session_ready',{model:sessions.get(session)});}else result('session_error',r,{model:this.model||'unconverted:'+this.originalSize});}});
 for(const [slot,api] of [[9,'Run'],[133,'RunWithBinding']])hook(table.add(slot*8).readPointer(),{onEnter(a){this.session=String(a[0]);},onLeave(r){const model=sessions.get(this.session)||'unknown';if(r.isNull()){counts[model]=(counts[model]||0)+1;if(counts[model]===1||counts[model]%300===0)emit('inference',{api,model,count:counts[model]});}else result('inference_error',r,{api,model});}});
 emit('engine_bound',{path:m.path,api:17});
}
Process.attachModuleObserver({onAdded(m){if(m.name.toLowerCase()==='perceptioncore.dll')try{bindEngine(m);}catch(e){emit('agent_error',{error:String(e)});}},onRemoved(m){if(m.name.toLowerCase()==='perceptioncore.dll')engines.delete(String(m.base));}});
rpc.exports={health(){return {pid:Process.id,counts};}};
emit('armed',{pid:Process.id});
