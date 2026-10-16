# Continuing this investigation

Read `docs/00-现状快照与断点续传.md`, `docs/08-重装前检查与独立复现验收.md`, and
`docs/09-继续研究所需的技术地图.md` before running experiments.

This repository is the handoff. Do not assume access to old chats, the original
user profile, Codex's bundled Python/PowerShell, or the author's temp directories.

- Separate historical observations, present measurements, and hypotheses.
- Do not call package installation, system-file changes, process injection,
  service installation, reboot, or camera capture merely to audit documentation.
- Before using any hard-coded offset, compare the entire pinned file hash.
  A different Windows build/package requires analysis, not a changed hash allowlist.
- Prefer `tools/prepare-product.py`, `native-install/tools/run_install.py`,
  `studio-cpu/Prepare-Runtime.py`, and `studio-cpu/Build-All.ps1` for current flows.
  Other scripts in archive, wse and older native-install download utilities are
  historical probes, not recommended default installers.
- Installation defaults to planning; actual Install requires `--install`.
  Never uninstall shared workload packages as a routine prerequisite.
- Keep the known working Click to Do hooks free of exception-observer hooks.
- Use `tests/cold_rebuild.py` for file/runtime rebuild tests. This does not prove
  installation on a clean OS, UI behavior, or reboot recovery.
- Preserve the user's intended next task: native Win+click tracing, not a global
  keyboard/mouse remapping bridge. System-wide Ready remains unresolved.
- Make failures visible and report significant blockers before long exploration.
