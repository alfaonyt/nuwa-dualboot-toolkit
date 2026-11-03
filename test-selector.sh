#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
for t in aarch64-linux-gnu-as aarch64-linux-gnu-objcopy aarch64-linux-gnu-gcc qemu-aarch64; do
  command -v "$t" >/dev/null || { printf 'Missing test dependency: %s\n' "$t" >&2; exit 1; }
done
tmp=$(mktemp -d)
trap 'rm -rf -- "$tmp"' EXIT
aarch64-linux-gnu-as selector.S -o "$tmp/selector.o"
aarch64-linux-gnu-objcopy -O binary "$tmp/selector.o" "$tmp/selector.bin"
aarch64-linux-gnu-gcc -O2 -pthread test_selector_harness.c -o "$tmp/harness"
sysroot=${CROSS_SYSROOT:-/usr/aarch64-linux-gnu}
for spec in '0:0:released' '1:42:pressed' '2:0:error' '3:0:no-mapping' '4:0:wrong-version' '5:0:timeout' '6:42:delayed-press'; do
  IFS=: read -r mode expected name <<< "$spec"
  result=0
  qemu-aarch64 -L "$sysroot" "$tmp/harness" "$tmp/selector.bin" "$mode" >/dev/null || result=$?
  [[ "$result" == "$expected" ]] || { printf 'FAIL %s (got %s, expected %s)\n' "$name" "$result" "$expected" >&2; exit 1; }
  printf 'PASS %s\n' "$name"
done
printf 'Simulation uses synthetic registers; it does not prove actual hardware behavior.\n'
