'use strict';
if(Process.mainModule.name.toLowerCase()!=='workloadssessionhost.exe'||Process.arch!=='x64')throw Error('Wrong target');
const seen=new Set(),runs=new Set(),listeners=[];
function report(event,data){send(Object.assign({event,pid:Process.id},data||{}));}
function bind(p,c){listeners.push(Interceptor.attach(p,c));}
function view(p){try{const n=p.add(8).readU64().toNumber();return n<65536?p.readPointer().readUtf8String(n):'<oversize>';}catch(e){return String(e);}}
function runTrace(api){for(const slot of [9,133,260]){const p=api.add(slot*8).readPointer();if(runs.has(p.toString()))continue;runs.add(p.toString());bind(p,{onEnter(){report('ort_run_enter',{slot});},onLeave(ret){report('ort_run_return',{slot,status:ret.toString()});}});}}
const observer=Process.attachModuleObserver({onAdded(m){
 const name=m.name.toLowerCase();
 if(/session|cacheapi|srdapi|oneocr|onnxruntime|openvino|machinelearning/i.test(name)||(/WindowsApps/i.test(m.path)&&!/^api-ms-|^ext-ms-/i.test(name)))report('module',{name:m.name,path:m.path});
 if(seen.has(m.base.toString()))return;seen.add(m.base.toString());
 if(name==='combase.dll'){
  bind(m.getExportByName('RoRegisterActivationFactories'),{onEnter(args){this.count=args[2].toUInt32();},onLeave(ret){report('activation_factories_registered',{count:this.count,hr:'0x'+ret.toUInt32().toString(16)});}});
  try{bind(m.getExportByName('RoOriginateErrorW'),{onEnter(args){report('winrt_error',{hr:'0x'+args[0].toUInt32().toString(16),message:args[2].isNull()?'':args[2].readUtf16String(Math.min(args[1].toUInt32(),512))});}});}catch(e){}
 }
 if(name==='onnxruntime.dll'){
  const getters=new Set();
  bind(m.getExportByName('OrtGetApiBase'),{onLeave(base){if(base.isNull())return;const get=base.readPointer();if(getters.has(get.toString()))return;getters.add(get.toString());bind(get,{onEnter(args){this.version=args[0].toUInt32();},onLeave(api){if(!api.isNull()&&this.version>=23){runTrace(api);report('ort_api_observed',{version:this.version});}}});}});
 }
 if(name==='oneocr.dll'){
  for(const f of ['CreateOcrPipeline','CreateOcrDocumentPipeline','RunOcrPipeline','AnalyzeOcrDocument','DetectOcrDocumentObjects','RecognizeOcrDocumentObjects','OcrProcessOptionsSetRunBackendModelOnCPU','SetOcrPipelineWorkloadOption']){
   try{bind(m.getExportByName(f),{onEnter(args){report('ocr_api_enter',{name:f,arg1:args[1].toString(),arg2:args[2].toString()});},onLeave(ret){report('ocr_api_return',{name:f,result:ret.toInt32()});}});}catch(e){report('ocr_export_missing',{name:f,error:String(e)});}
  }
 }
 if(name==='textrecognitionsession.dll'){
  for(const [rva,label] of [[0x3f20,'constructor'],[0x2a4b0,'local_recognizer_constructor'],[0x2bed0,'local_recognize'],[0x6760,'session7_text'],[0x6650,'session7_tables']])bind(m.base.add(rva),{onEnter(){report('ocr_session_enter',{name:label});},onLeave(ret){report('ocr_session_return',{name:label,rawReturn:ret.toString()});}});
 }
 if(name==='cacheapi.dll'||name==='srdapi.dll'){
  const cache=name==='cacheapi.dll';
  if(cache&&!/WindowsWorkload\.WinMLShared\.5\.2_1\.2608\.951\.0_x64__/i.test(m.path))throw Error('Unexpected cache DLL version');
  if(!cache&&!/WindowsWorkload\.ScrRegDetection\.Lnl\.1_1\.2608\.951\.0_x64__/i.test(m.path))throw Error('Unexpected SRD DLL version');
  const rva=cache?0x7cb6c:0x5c91c;
  const bytes=Array.from(new Uint8Array(m.base.add(rva-3).readByteArray(3)));
  if(bytes.join(',')!=='137,69,168')throw Error('Device filter bytes mismatch');
  bind(m.base.add(rva),{onEnter(){const local=this.context.rbp.sub(0x58),previous=local.readU32();if(previous!==2){report('device_filter_unexpected',{module:m.name,previous});return;}local.writeU32(0);report('openvino_cpu_selected',{module:m.name,previous,selected:0});}});
  report('cpu_filter_hook_ready',{module:m.name,rva:'0x'+rva.toString(16)});
  if(cache){
   for(const [rva,level] of [[0x4e190,'info'],[0x4ca40,'error']])bind(m.base.add(rva),{onEnter(args){report('cache_log',{level,message:view(args[1])});}});
   for(const [rva,level] of [[0x74b40,'info'],[0x66350,'error']])bind(m.base.add(rva),{onEnter(args){let format='';try{format=args[1].readUtf8String();}catch(e){}report('cache_format',{level,format,arg2:args[2].toString(),arg3:args[3].toString()});}});
  }else{
   bind(m.getExportByName('SrdApiCreate'),{onLeave(object){if(object.isNull())return;try{const fn=object.readPointer().add(9*8).readPointer();bind(fn,{onEnter(args){this.count=args[5];this.capacity=args[3].toUInt32();this.image=args[1];report('srd_inference_enter',{width:this.image.add(4).readU32(),height:this.image.add(8).readU32(),capacity:this.capacity});},onLeave(ret){report('srd_inference_return',{result:ret.toInt32(),regions:ret.toInt32()===0?this.count.readU32():null});}});}catch(e){report('srd_inference_observer_error',{error:String(e)});}}});
   bind(m.base.add(0x5c210),{onEnter(args){try{const api=args[0].add(8).readPointer(),env=args[0].add(16).readPointer();runTrace(api);report('srd_environment',{environment:env.toString()});}catch(e){report('srd_environment_error',{error:String(e)});}}});
   for(const rva of [0x41af0,0x41a00])bind(m.base.add(rva),{onEnter(args){let message='';try{message=args[1].readUtf8String();}catch(e){}report('srd_core_log',{message});}});
  }
 }
}});
rpc.exports={cleanup(){observer.detach();for(const h of listeners)h.detach();return true;}};
report('host_hook_ready');
