'use strict';

// Frida JavaScript API: https://frida.re/docs/javascript-api/
// Exact interface and slot order verified against this computer's windowsudk.winmd.
// Only output BOOLEANs of successful capability queries are changed in this process.
// Original HRESULTs, other classes, unconfigured features, and model APIs are preserved.
const CONFIG = Object.assign({featureOverrides: {'1': true}, copilotPlusOverride: null, enterpriseGateOverride: true}, /*__CONFIG_JSON__*/ {});
const CLASS_NAME = 'WindowsUdk.AI.PlatformCapabilities.AIPlatformCapability';
const IID = 'bd64214c-9545-5ea9-9c65-8934640751e6';
const IID_BYTES = [0x4c,0x21,0x64,0xbd,0x45,0x95,0xa9,0x5e,0x9c,0x65,0x89,0x34,0x64,0x07,0x51,0xe6];
const ENTERPRISE_CLASS = 'WindowsUdk.Management.Update.EnterpriseFeatureControl';
const ENTERPRISE_IID = '82859d1f-647d-5dc4-b5e2-f22665a70f64';
const ENTERPRISE_IID_BYTES = [0x1f,0x9d,0x85,0x82,0x7d,0x64,0xc4,0x5d,0xb5,0xe2,0xf2,0x26,0x65,0xa7,0x0f,0x64];
const allowedNames = new Set(['powershell.exe', 'pwsh.exe', 'clicktodo.exe', 'aicontext.exe', 'explorer.exe']);
if (Process.platform !== 'windows' || Process.arch !== 'x64' || Process.pointerSize !== 8)
    throw new Error('This prototype requires a 64-bit Windows process.');
if (!allowedNames.has(Process.mainModule.name.toLowerCase()))
    throw new Error('Target executable is outside the explicit allowlist.');

const listeners = [];
const hookedFunctions = new Set();
// Retain a COM reference for each tracked interface to avoid stale-pointer reuse.
const trackedInterfaces = new Map();
const iidMemory = Memory.alloc(16);
iidMemory.writeByteArray(IID_BYTES);
const enterpriseIidMemory = Memory.alloc(16);
enterpriseIidMemory.writeByteArray(ENTERPRISE_IID_BYTES);
let factoryInstalled = false;
let moduleObserver = null;

function report(event, data) { send(Object.assign({event: event}, data || {})); }
function hrHex(hr) { return '0x' + (hr >>> 0).toString(16).padStart(8, '0'); }

function hookQuery(address, method, slot) {
    const key = method + ':' + address.toString();
    if (hookedFunctions.has(key)) return;
    const listener = Interceptor.attach(address, {
        onEnter(args) {
            const entry = trackedInterfaces.get(args[0].toString());
            this.tracked = entry !== undefined && entry.kind === (method === 'IsFeatureEnabled' ? 'enterprise' : 'capability');
            if (!this.tracked) return;
            this.feature = method === 'IsFeatureAvailable' ? args[1].toInt32() : (method === 'IsFeatureEnabled' ? args[1].toUInt32() : null);
            this.output = args[method === 'IsCopilotPlusPC' ? 1 : 2];
        },
        onLeave(retval) {
            if (!this.tracked) return;
            const hr = retval.toInt32();
            if (hr < 0 || this.output.isNull()) {
                report('query', {method, id: this.feature, hresult: hr, hresultHex: hrHex(hr), original: null, modified: null, changed: false});
                return;
            }
            const original = this.output.readU8() !== 0;
            let modified = original;
            if (method === 'IsFeatureAvailable' && Object.prototype.hasOwnProperty.call(CONFIG.featureOverrides, String(this.feature)))
                modified = CONFIG.featureOverrides[String(this.feature)];
            else if (method === 'IsCopilotPlusPC' && typeof CONFIG.copilotPlusOverride === 'boolean')
                modified = CONFIG.copilotPlusOverride;
            else if (method === 'IsFeatureEnabled' && this.feature === 56114500 && typeof CONFIG.enterpriseGateOverride === 'boolean')
                modified = CONFIG.enterpriseGateOverride;
            if (modified !== original) this.output.writeU8(modified ? 1 : 0);
            report('query', {method, id: this.feature, hresult: hr, hresultHex: hrHex(hr), original, modified, changed: modified !== original});
        }
    });
    listeners.push(listener);
    hookedFunctions.add(key);
    report('hook-installed', {method, slot, address: address.toString()});
}

function trackFactory(factory, kind) {
    const vtable = factory.readPointer();
    const qi = new NativeFunction(vtable.readPointer(), 'int', ['pointer', 'pointer', 'pointer'], 'win64');
    const output = Memory.alloc(Process.pointerSize);
    output.writePointer(ptr(0));
    const hr = qi(factory, kind === 'enterprise' ? enterpriseIidMemory : iidMemory, output);
    report('query-interface', {iid: kind === 'enterprise' ? ENTERPRISE_IID : IID, hresult: hr, hresultHex: hrHex(hr)});
    if (hr < 0) return;
    const iface = output.readPointer();
    if (iface.isNull()) throw new Error('QueryInterface succeeded with a null interface.');
    const table = iface.readPointer();
    const release = new NativeFunction(table.add(2 * Process.pointerSize).readPointer(), 'uint', ['pointer'], 'win64');
    const key = iface.toString();
    if (trackedInterfaces.has(key)) {
        release(iface);
    } else {
        trackedInterfaces.set(key, {iface, release, kind});
    }
    if (kind === 'enterprise') {
        hookQuery(table.add(6 * Process.pointerSize).readPointer(), 'IsFeatureEnabled', 6);
    } else {
        hookQuery(table.add(6 * Process.pointerSize).readPointer(), 'IsFeatureAvailable', 6);
        hookQuery(table.add(7 * Process.pointerSize).readPointer(), 'IsCopilotPlusPC', 7);
    }
    Interceptor.flush();
}

function installFactoryHook(module) {
    if (factoryInstalled) return;
    const getRawBuffer = new NativeFunction(module.getExportByName('WindowsGetStringRawBuffer'), 'pointer', ['pointer', 'pointer'], 'win64');
    const listener = Interceptor.attach(module.getExportByName('RoGetActivationFactory'), {
        onEnter(args) {
            this.match = false;
            try {
                const length = Memory.alloc(4);
                length.writeU32(0);
                const text = getRawBuffer(args[0], length);
                const count = length.readU32();
                if (!text.isNull() && (count === CLASS_NAME.length || count === ENTERPRISE_CLASS.length)) {
                    const name = text.readUtf16String(count);
                    this.kind = name === CLASS_NAME ? 'capability' : (name === ENTERPRISE_CLASS ? 'enterprise' : null);
                    this.match = this.kind !== null;
                    if (this.match) { this.output = args[2]; this.className = name; }
                }
            } catch (error) {
                report('error', {stage: 'read-class-name', message: String(error)});
            }
        },
        onLeave(retval) {
            if (!this.match) return;
            const hr = retval.toInt32();
            report('activation', {className: this.className, hresult: hr, hresultHex: hrHex(hr)});
            if (hr < 0 || this.output.isNull()) return;
            try {
                const factory = this.output.readPointer();
                if (!factory.isNull()) trackFactory(factory, this.kind);
            } catch (error) {
                report('error', {stage: 'install-vtable-hooks', message: String(error)});
            }
        }
    });
    listeners.push(listener);
    factoryInstalled = true;
    report('ready', {fridaVersion: Frida.version, target: Process.mainModule.name, architecture: Process.arch, config: CONFIG});
}

moduleObserver = Process.attachModuleObserver({
    onAdded(module) {
        if (module.name.toLowerCase() === 'combase.dll') installFactoryHook(module);
    }
});

rpc.exports = {
    cleanup() {
        for (const listener of listeners) listener.detach();
        listeners.length = 0;
        if (moduleObserver !== null) { moduleObserver.detach(); moduleObserver = null; }
        for (const entry of trackedInterfaces.values()) entry.release(entry.iface);
        trackedInterfaces.clear();
        report('cleanup', {restored: true});
        return true;
    }
};
