'use strict';
// Execute the two applications' existing registration operations on their own
// UI threads. No keyboard hooks and no synthesized keyboard or mouse input.
const CONFIG=/*__CONFIG__*/ {};
if(Process.id!==CONFIG.pid||Process.mainModule.name.toLowerCase()!==CONFIG.name)throw Error('Wrong native target');
const user=Process.getModuleByName('user32.dll');
const hwnd=ptr(CONFIG.hwnd),token=ptr(CONFIG.token);
const getProc=new NativeFunction(user.getExportByName('GetWindowLongPtrW'),'pointer',['pointer','int']);
const owner=new NativeFunction(user.getExportByName('GetWindowThreadProcessId'),'uint32',['pointer','pointer']);
const pidOut=Memory.alloc(4);const thread=owner(hwnd,pidOut);
if(pidOut.readU32()!==Process.id)throw Error('Window does not belong to selected process');
const proc=getProc(hwnd,-4);
if(proc.isNull())throw Error('No native window procedure');
const register=new SystemFunction(user.getExportByName('RegisterHotKey'),'int',['pointer','int','uint32','uint32']);
const unregister=new SystemFunction(user.getExportByName('UnregisterHotKey'),'int',['pointer','int']);
const post=new SystemFunction(user.getExportByName('PostMessageW'),'int',['pointer','uint32','pointer','pointer']);
let pending=null;
const listener=Interceptor.attach(proc,{onEnter(args){
 if(!pending||!args[0].equals(hwnd)||args[1].toUInt32()!==0||!args[2].equals(token))return;
 const request=pending;pending=null;
 const result=request.action==='register'?register(hwnd,CONFIG.hotkeyId,0x4008,0x51):unregister(hwnd,CONFIG.hotkeyId);
 send({event:'native-registration-result',pid:Process.id,thread:Process.getCurrentThreadId(),expectedThread:thread,
       sequence:request.sequence,action:request.action,id:CONFIG.hotkeyId,success:!!result.value,lastError:result.lastError});
}});
send({event:'registration-observer-ready',pid:Process.id,hwnd:hwnd.toString(),windowProcedure:proc.toString(),thread});
rpc.exports={
 action(action,sequence){
  if(pending)throw Error('An operation is already pending');
  if(action!=='register'&&action!=='unregister')throw Error('Unexpected operation');
  pending={action,sequence};const result=post(hwnd,0,token,ptr(0));
  if(!result.value){pending=null;throw Error('Could not wake owner thread: '+result.lastError);}
  return true;
 },
 cleanup(){pending=null;listener.detach();return true;}
};
