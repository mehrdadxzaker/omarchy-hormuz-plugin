#!/usr/bin/env bash
set -euo pipefail

PLUGIN_ID="io.hormuz.optimizer"
SOURCE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
# Override only for a disposable installer test; Omarchy normally scans HOME.
PLUGIN_ROOT="${HORMUZ_OMARCHY_PLUGIN_ROOT:-$HOME/.config/omarchy/plugins}"
DESTINATION="$PLUGIN_ROOT/$PLUGIN_ID"
STAGING=""

cleanup() { if [[ -n $STAGING && -d $STAGING ]]; then rm -rf -- "$STAGING"; fi; }
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

[[ $(uname -s) == Linux && $EUID -ne 0 ]] || { echo "Install as your normal user in an Omarchy Linux session." >&2; exit 1; }
for dependency in omarchy omarchy-shell python3 timeout; do
  command -v "$dependency" >/dev/null || { echo "Missing dependency: $dependency" >&2; exit 1; }
done
[[ ! -e $DESTINATION && ! -L $DESTINATION ]] || { echo "Plugin folder already exists: $DESTINATION" >&2; exit 1; }

mkdir -p -- "$PLUGIN_ROOT"
STAGING="$(mktemp -d "$PLUGIN_ROOT/.hormuz-install.XXXXXXXX")"
for file in manifest.json BarWidget.qml Panel.qml Service.qml Model.js Metric.qml ActionButton.qml README.md LICENSE QA.md; do
  cp -- "$SOURCE_DIR/$file" "$STAGING/$file"
done
mkdir -- "$STAGING/scripts"
cp -- "$SOURCE_DIR/scripts/hormuz_plugin.py" "$SOURCE_DIR/scripts/install.sh" "$STAGING/scripts/"
timeout 15s omarchy plugin validate "$STAGING"
mv -T -- "$STAGING" "$DESTINATION"
STAGING=""

# Installation is complete even if the shell is not currently running.
# Keep the validated folder available for a later rescan/enable in that case.
if ! OMARCHY_SHELL_IPC_TIMEOUT=5 timeout 10s omarchy-shell shell rescanPlugins; then
  echo "Copied plugin to $DESTINATION. Start the Omarchy shell, then rescan and enable $PLUGIN_ID." >&2
  exit 1
fi
# The shell returns before its asynchronous catalog scan finishes. Wait for the
# validated id to appear rather than racing the first enable operation.
registered=false
for attempt in {1..6}; do
  if OMARCHY_SHELL_IPC_TIMEOUT=3 timeout 5s omarchy-shell shell listPlugins |
    python3 -c 'import json, sys; sys.exit(not any(p.get("id") == sys.argv[1] for p in json.load(sys.stdin)))' "$PLUGIN_ID"; then
    registered=true
    break
  fi
  sleep 0.5
done
if [[ $registered != true ]]; then
  echo "Copied plugin to $DESTINATION, but the shell catalog is not ready. Rescan and enable $PLUGIN_ID when it is ready." >&2
  exit 1
fi
timeout 15s omarchy plugin enable "$PLUGIN_ID"
echo "Installed $PLUGIN_ID. Open its bar widget; see $DESTINATION/README.md for profile setup."
