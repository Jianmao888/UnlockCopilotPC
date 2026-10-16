# Source build

Normal installation uses the supplied executables and does not need a compiler.

For a source build, use MSVC x64, Windows SDK 10.0.26100.0, and the OpenVINO 2025.3.0 C++ headers/libraries:

```powershell
.\Build.ps1 -OpenVinoRoot 'C:\SDK\openvino' -VcToolsRoot 'C:\Path\To\VC\Tools\MSVC\14.xx.xxxxx'
```

After recompiling, run Prepare.ps1 again to regenerate payload hashes and CPU models. Binary offsets and model adaptation are specific to the pinned driver version.
