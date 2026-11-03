#!/usr/bin/env bash
set -euo pipefail

if [[ $# != 1 ]]; then
  printf 'Usage: %s BACKUP_DIRECTORY\n' "$0" >&2
  exit 2
fi
command -v adb >/dev/null
command -v sha256sum >/dev/null
adb get-state >/dev/null
device=$(adb shell getprop ro.product.device | tr -d '\r')
[[ "$device" == nuwa ]] || { printf 'Expected nuwa, got %s\n' "$device" >&2; exit 1; }
slot=$(adb shell getprop ro.boot.slot_suffix | tr -d '\r')
[[ "$slot" == _a || "$slot" == _b ]] || { printf 'Unknown slot suffix: %s\n' "$slot" >&2; exit 1; }
mkdir -p -- "$1"
out="$1/boot${slot}.img"
[[ ! -e "$out" && ! -L "$out" ]] || { printf 'Refusing to overwrite %s\n' "$out" >&2; exit 1; }
tmp=$(mktemp "$1/.nuwa-boot-backup.XXXXXX")
trap 'rm -f -- "$tmp"' EXIT
remote_hash=$(adb shell su -c "sha256sum /dev/block/by-name/boot${slot}" | tr -d '\r' | awk '{print $1}')
[[ "$remote_hash" =~ ^[0-9a-f]{64}$ ]] || { printf 'Could not read remote hash; enable KernelSU shell access.\n' >&2; exit 1; }
adb exec-out su -c "cat /dev/block/by-name/boot${slot}" > "$tmp"
local_hash=$(sha256sum "$tmp" | awk '{print $1}')
slot_after=$(adb shell getprop ro.boot.slot_suffix | tr -d '\r')
[[ "$slot_after" == "$slot" && "$local_hash" == "$remote_hash" ]] || { printf 'Slot or hash changed; backup discarded.\n' >&2; exit 1; }
ln -- "$tmp" "$out" # fail rather than overwrite if another file appeared
printf 'Verified active-slot backup: %s\nSHA-256: %s\n' "$out" "$local_hash"
printf 'This is the current image; it may already contain the dual-boot patch.\n'
