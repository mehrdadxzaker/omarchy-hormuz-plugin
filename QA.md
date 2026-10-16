# Omarchy runtime qualification

Plugin `io.hormuz.optimizer`, version 0.1.0. Tested on 2026-10-09.
This is a Linux integration preview, with the scope below.

## Exact dependencies

- Omarchy Quattro source: `9d48fc402edf51ae089a7c8c1f7b1a8611744bd8`
  (the source tree identifies itself as `4.0.0.alpha`).
- Quickshell 0.3.2, Hyprland 0.56.2-4, Qt 6.12.0, Python 3.14.0.
- Hormuz 1.8.0 source: `99b0435765c1d4a736c1cf5438216f4c5c434364`.
- Official Codex CLI 0.148.0, x86_64 Linux musl release; SHA-256
  `1a36f762f6b3bef533bb86345ad9517661c2d84d53996a250cf2ca89d2cfee5a`.
- Token counters: tiktoken 0.14.0 with both hash-verified vocabularies.
- GNOME Secret Service with an unlocked disposable collection.

The disposable Lima VM used a Ubuntu 24.04 ARM64 kernel and an isolated Arch
x86_64 userland under Rosetta. The actual Omarchy shell and actual Hyprland
compositor rendered through a VZ virtual DRM device with Mesa software rendering.
Arch systemd cannot boot under this emulator, so the fixture used Ubuntu's
native systemd 255.4 manager and clients, copied UWSM user units, and registered
Rosetta as a valid shell interpreter for Omarchy's terminal-directory detection.
Only this disposable environment was modified. This was not a fresh Omarchy
ISO installation or physical x86 hardware qualification.

## Automated checks

`python3 -m unittest discover -s tests -v` passes **23 provider-free tests** on
macOS and inside the Arch fixture. They cover scalar-only reports, missing
observations, invalid numbers and schemas, literal arguments, bounded output,
timeouts, descendant cleanup, termination, launch locks, private runtime paths,
staged installation, existing-folder refusal, and asynchronous catalog readiness.
The installer waits a bounded number of times before enabling the discovered id.
The Hormuz integration shim also passes 24 tests in the Arch fixture, adding a
real CLI status/On/Off check against a disposable profile without credentials.

The official pinned `omarchy-plugin-validate` accepts the plugin. Native Qt
linting uses the actual `qs` import tree, not mocks. Dynamic properties from
Omarchy's untyped Style objects can produce static-lint warnings; live engine
loading is checked separately. Routine tests use no HTTP, OS keyring, provider
account, or real coding agent.

## Real-agent fixture

A saved direct-mode profile held a synthetic credential in real Secret Service.
The official Codex binary ran in an Omarchy terminal through the plugin's
Launch action. A bounded loopback provider returned a tool call and streamed
completion. Codex ran `rg --files generated` over 48 synthetic files. The
wrapper only selected deterministic `codex exec` arguments; it did not replace
the agent. The fixture had a 15-minute lifetime, four server worker slots, a
12-request budget, explicit socket timeouts, and shutdown/reaping paths.

Off forwarded ordinary tool output. An intentionally missing tokenizer cache
exercised honest On fallback with unknown token estimates. After repairing the
fixture cache path, On produced the lossless `hormuz-path-list-v1` representation
and completed streaming. A fresh On session recorded 2 requests, 1 eligible
request, 1 transformation, 482 locally estimated input tokens avoided, and
2,147 fewer serialized bytes. These numbers describe synthetic test traffic;
they are not provider billing savings or a production benchmark. The fixture
reported zero cache-read tokens; before any observation the panel displayed a dash.

The upstream received the expected synthetic authorization and no private
Hormuz context-format header. The active terminal directory was preserved.
A live plugin launch acquired its advisory lock; another launch was refused
with the documented diagnostic. Closing the popup left the agent session alive;
normal completed sessions released their locks. Unit tests additionally prove
helper termination and timeout cleanup for a SIGTERM-ignoring descendant.

## Desktop evidence

Final native UI results and source-file fingerprints are recorded in
[the runtime record](https://github.com/mehrdadxzaker/omarchy-hormuz-plugin/blob/main/evidence/runtime.json).
Screenshots are from the actual
Omarchy process, inspected before publication. The root preview shows synthetic
measurements and contains no customer content or credentials.

Native mouse input opened the bar widget, toggled Off then On, refreshed, and
dismissed the popup outside it. Focused Wayland keyboard input selected actions,
refreshed with R, and closed with Escape. Invalid executable and profile settings
cleared the measurements and disabled launch/toggle; restoring settings recovered
without restarting the shell. The saved profile and its eight observed requests
survived a clean desktop restart.

The panel was inspected with a vertical bar and an 18-pixel base font. A second
headless Wayland output exercised monitor selection at 800×600; keyboard action
selection scrolled the action row into view. This checks virtual monitor behavior,
not physical display hardware. The unmodified native source loaded with no plugin
QML errors. Inotify/file replacement during fixture development once stalled the
emulated Qt shell; a clean restart recovered. Hot-reload stability under Rosetta is
not claimed.

## Limits

The fixture omitted host portal, PipeWire, UPower, and Polkit services; associated
Omarchy startup warnings are not plugin QML failures. No global Super hotkey,
lock screen, physical multi-monitor, production provider, managed gateway login,
billing benefit, or full Omarchy distribution certification is claimed.
Hormuz's product-wide macOS qualification remains unchanged. Marketplace
submission and maintainer-approved catalog publication are separate stages.
