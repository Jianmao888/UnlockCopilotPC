'use strict';

// Force only the Click to Do support predicate observed in DiscoveryOverlay.dll.
// This is process-local and version-specific; no system file or shared service is changed.
if (Process.platform !== 'windows' || Process.arch !== 'x64' ||
    Process.mainModule.name.toLowerCase() !== 'clicktodo.exe') {
  throw new Error('This hook is restricted to x64 ClickToDo.exe.');
}

const listeners = [];
const observed = new Set();
const supportPredicateRva = 0x2bbe28;
const modelReadinessRva = 0x1bb1c4;

function report(event, data) { send(Object.assign({event}, data || {})); }

const observer = Process.attachModuleObserver({
  onAdded(module) {
    if (module.name.toLowerCase() !== 'discoveryoverlay.dll' ||
        observed.has(module.base.toString())) return;
    observed.add(module.base.toString());
    const address = module.base.add(supportPredicateRva);
    listeners.push(Interceptor.attach(address, {
      onEnter() {
        this.base = module.base.toString();
      },
      onLeave(retval) {
        const original = retval.toInt32();
        retval.replace(1);
        report('support-predicate', {
          module: module.name,
          moduleBase: this.base,
          rva: '0x2bbe28',
          original,
          forced: 1
        });
      }
    }));
    report('support-predicate-hook-installed', {
      module: module.name,
      moduleBase: module.base.toString(),
      address: address.toString(),
      rva: '0x2bbe28'
    });

    const modelAddress = module.base.add(modelReadinessRva);
    listeners.push(Interceptor.attach(modelAddress, {
      onEnter() {
        this.base = module.base.toString();
      },
      onLeave(retval) {
        const original = retval.toInt32();
        retval.replace(1);
        report('model-readiness-predicate', {
          module: module.name,
          moduleBase: this.base,
          rva: '0x1bb1c4',
          original,
          forced: 1
        });
      }
    }));
    report('model-readiness-hook-installed', {
      module: module.name,
      moduleBase: module.base.toString(),
      address: modelAddress.toString(),
      rva: '0x1bb1c4'
    });
  }
});

rpc.exports = {
  cleanup() {
    for (const listener of listeners) listener.detach();
    observer.detach();
    report('support-predicate-cleanup', {restored: true});
    return true;
  }
};
