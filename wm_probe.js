// wm_probe.js - probe Microsoft.Windows.Workloads.WorkloadManager
// run under frida attached to a packaged app (AI Dev Gallery has package identity)

const W = "Microsoft.Windows.Workloads";

function u16(s) {
  const b = [];
  for (let i = 0; i < s.length; i++) b.push(s.charCodeAt(i) & 0xff, 0);
  b.push(0, 0);
  return new Uint8Array(b);
}

// RoGetActivationFactory(HSTRING, REFIID, void**)
const RoGetActivationFactory = Module.getExportByName("combase.dll", "RoGetActivationFactory");
const RoGetActivationFactoryFn = new NativeFunction(RoGetActivationFactory, "int32",
  ["pointer", "pointer", "pointer"]);
const RoInitialize = new NativeFunction(Module.getExportByName("combase.dll", "RoInitialize"), "int32", ["uint32"]);
const WindowsCreateString = new NativeFunction(
  Module.getExportByName("combase.dll", "WindowsCreateString"), "int32",
  ["pointer", "uint32", "pointer"]);

function hstring(s) {
  const out = Memory.alloc(Process.pointerSize);
  const buf = Memory.allocUtf16String(s);
  const hr = WindowsCreateString(buf, s.length, out);
  return { hr: hr, h: out.readPointer() };
}

function guidBytes(str) {
  // "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" -> 16 bytes
  const hex = str.replace(/-/g, "");
  const b = [];
  for (let i = 0; i < 32; i += 2) b.push(parseInt(hex.substr(i, 2), 16));
  return new Uint8Array(b);
}

const hr0 = RoInitialize(1);
send({ tag: "RoInitialize", hr: hr0 });

// Try to get the WorkloadManager activation factory.
// We don't know the IID; use IUnknown-clsid trick: RoGetActivationFactory needs an IID.
// Use the standard IActivationFactory IID.
const IID_IActivationFactory = guidBytes("00000035-0000-0000-c000-000000000046");

const names = [
  "Microsoft.Windows.Workloads.WorkloadManager",
  "Microsoft.Windows.Workloads.ApiInfo",
];

for (const n of names) {
  const hs = hstring(n);
  const pout = Memory.alloc(Process.pointerSize);
  const hr = RoGetActivationFactoryFn(hs.h, Memory.alloc(16).writeByteArray(IID_IActivationFactory), pout);
  send({ tag: "RoGetActivationFactory", name: n, hr: hr, ptr: pout.readPointer().toString() });
}

send({ tag: "done" });
