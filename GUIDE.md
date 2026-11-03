# Setup guide: Xiaomi 13 Pro dual boot

This guide is for the **Xiaomi 13 Pro, codename `nuwa`**, with a compatible Project Silicium UEFI port. It builds an Android boot image with a two-second selection window: leave the buttons alone for Android, or press Volume Down during the window for UEFI. Release the button as UEFI starts. Linux must already be prepared separately and bootable from that UEFI.

This is device-specific early-boot code, not a universal Android dual-boot tool. It was tested on one nuwa with a particular ROM and Mu port; hardware, firmware, ROM and bootloader differences matter. The tools make files and backups; the fastboot commands below are manual.

## 1. Check prerequisites

You need:

- A Xiaomi 13 Pro (`nuwa`) that already has an **unlocked bootloader** and supports temporary `fastboot boot`. This guide does not cover unlocking; unlocking can erase data.
- A Linux computer, USB cable, and Android platform-tools (`adb` and `fastboot`). Enable USB debugging and authorize the computer on the phone. Have sufficient battery and keep the cable connected during any flash.
- A working compatible **nuwa Mu-Silicium build** and its raw 3 MiB firmware volume (`SILICIUM_UEFI.fd`). This project does not distribute or build the UEFI port, an Android ROM, a Linux kernel or a root filesystem. Check the [Project Silicium build instructions](https://github.com/Project-Silicium/Mu-Silicium/blob/main/Building.md) and your port's instructions; upstream support and build steps may differ from your local port.
- An **unpatched boot image matching the exact Android build and root setup you intend to run**. KernelSU can be built into the kernel or installed using a separate ramdisk; an image extracted from a ROM does not necessarily include your current root modifications. Keep matching `init_boot`, `vendor_boot`, recovery and other ROM images available for recovery. The toolkit does not modify them.
- Git, Python 3, `avbtool`, the AArch64 GNU assembler and objcopy, and `sha256sum`. Check them with:

  ```bash
  python3 --version
  for tool in git adb fastboot avbtool aarch64-linux-gnu-as aarch64-linux-gnu-objcopy sha256sum; do
    command -v "$tool" || echo "Missing: $tool"
  done
  ```

Install missing tools from trusted sources for your Linux distribution. If `avbtool` is not packaged, see the [Android Verified Boot project](https://android.googlesource.com/platform/external/avb/). You need a working `avbtool` executable on your `PATH`.

The builder supports only a v4 Android `boot.img` with an uncompressed ARM64 EFI-format kernel, no boot ramdisk and no v4 GKI boot signature. It checks these conditions and refuses unsupported inputs. The tested boot partition was `0xC000000` bytes, but confirm your own. The FD must be linked for `0xA7100000` with a `0x300000`-byte region; merely having the right size does not prove this.

**AVB matters:** the output carries an unsigned AVB hash footer. It does not update or re-sign top-level `vbmeta`; that partition may still contain the original boot hash. The tested setup had verification disabled. A locked bootloader or a different verification policy can reject the image, including after `fastboot boot` succeeds. Do not change AVB settings or relock the bootloader as a workaround.

## 2. Get the toolkit and identify the phone

```bash
git clone https://github.com/alfaonyt/nuwa-dualboot-toolkit.git
cd nuwa-dualboot-toolkit
adb devices -l
adb shell getprop ro.product.device
adb shell getprop ro.boot.slot_suffix
adb shell getprop ro.build.version.incremental
```

`adb devices -l` should show a connected `device`; accept the debugging prompt on the phone if it says `unauthorized`. The device property should be `nuwa`; stop if it is not. Record the current slot suffix (`_a` or `_b`) and your ROM build details. The active slot is not a separate Linux slot and the tools do not switch it.

If more than one phone is connected, select the intended device with the `ANDROID_SERIAL` environment variable before running `adb` or `fastboot`. Confirm the serial from `adb devices -l`; do not copy an example serial from someone else.

## 3. Save a matching boot backup

Before changing anything, back up important data and make sure you can get back into bootloader fastboot. With KernelSU root access granted to the ADB shell:

```bash
./backup-active.sh "$HOME/nuwa/boot-backup-before-dualboot"
```

The helper detects the active slot, reads only its `boot` partition, compares SHA-256 hashes on both sides, checks the slot again, and refuses to overwrite a backup. It creates `boot_a.img` or `boot_b.img` in the chosen directory. Use a new directory for each ROM version and keep the printed hash.

The backup is **exactly what is installed now**. If that image already has dual boot, it is still useful to restore the current state, but the builder will reject it as a new base. If ADB root isn't available, use another verified backup method appropriate to your setup or obtain the exact matching ROM image; this helper cannot read the partition without root. Don't assume a stock ROM image includes your current KernelSU changes.

Also keep the ROM's matching companion images and your existing recovery method available. The helper only backs up `boot`; it does not back up `init_boot`, `vendor_boot`, recovery, `vbmeta`, or user data. Recovery may need the boot kernel even on a device with a separate recovery partition.

## 4. Find the two inputs

**Android boot image:** use the exact ROM build and root configuration currently intended for the active slot. Some ROM packages provide `boot.img` directly. Others contain an OTA `payload.bin`; follow the ROM's extraction instructions. [payload-dumper-go](https://github.com/ssut/payload-dumper-go) is one option for extracting partition images; use its documentation, including any requirements for incremental payloads. Extract into a new directory, identify `boot.img`, and check the package's device/build. Do not substitute `init_boot.img`, `vendor_boot.img`, a boot image from another build, or a previous dual-boot output.

**UEFI firmware:** use the raw FD from your known working nuwa port. For the test setup it was:

```text
~/nuwa/Mu-Silicium/Build/nuwaPkg/RELEASE_CLANGPDB/FV/SILICIUM_UEFI.fd
```

Do not pass `Mu-nuwa.img`, the BootShim-prefixed FD, or the compressed file. Confirm the raw FD was built for this nuwa port and its stated memory map. If the UEFI build changes its FD base, size or memory layout, stop and revalidate the selector. A working standalone UEFI image alone does not prove the combined image works.

## 5. Build a separate image

From the toolkit directory, replace both input paths with your own:

```bash
mkdir -p "$HOME/nuwa"
python3 build.py \
  --boot /path/to/matching-unpatched-boot.img \
  --fd /path/to/nuwa/SILICIUM_UEFI.fd \
  --out "$HOME/nuwa/dualboot-test.img"
```

The output directory must already exist and the output filename must be new; existing files are never overwritten. The builder reports hashes for the source image, firmware and output. Save those values. It assembles the selector, creates a full-size image and verifies the generated footer. It does not sign top-level `vbmeta` or change the phone.

`--partition-size 0xC000000` is the default tested size. Use `--partition-size` only with the size actually reported for your current device. To inspect the options, run `python3 build.py --help`.

## 6. Test with fastboot boot

Save your work; the following reboots the phone into its **bootloader fastboot**, not Android's userspace fastbootd:

```bash
adb reboot bootloader
fastboot devices -l
fastboot getvar product
fastboot getvar current-slot
fastboot getvar unlocked
```

Confirm the connected device is `nuwa`, the slot agrees with your backup, and the bootloader reports unlocked. For the current slot, check the corresponding partition size using **one** command:

```bash
# If current-slot is a:
fastboot getvar partition-size:boot_a
# If current-slot is b:
fastboot getvar partition-size:boot_b
```

If the reported size differs from the builder's size, rebuild to a **new filename** with the correct `--partition-size`; do not flash the old output. If any check is missing or unexpected, stop and investigate.

Now temporarily load the output; this command does not flash a partition:

```bash
fastboot boot "$HOME/nuwa/dualboot-test.img"
```

1. First, press no button. Android should start. Confirm the intended ROM, KernelSU Next, and normal operation.
2. Return to bootloader fastboot and run the same `fastboot boot` command again. Press Volume Down during the selector's two-second window. Release it as UEFI starts; verify UEFI controls and that your existing Linux installation boots.
3. Reboot normally. Check that normal Android and the existing recovery entry remain reachable with the installed image. Temporary boot proves neither permanent AVB behavior nor recovery behavior with a flashed modified kernel.

The two-second window starts at **kernel entry**, not necessarily when a logo appears. Holding Volume Down too early on power-on may send the phone to the bootloader's own fastboot mode. Testing the button from a phone already in fastboot avoids relying on that power-on timing.

If `fastboot boot` is unsupported or rejected, stop; do not substitute `fastboot flash`. If the device hangs, hold Power until it restarts and boot normally. UEFI or Linux can write persistent data during their own operation even though `fastboot boot` does not flash the supplied image.

## 7. Optional: install to the current slot

Only consider this after testing **both** paths with the exact output, verifying its hash and size, confirming a matching backup and recovery plan, and checking your device's AVB policy. Your own ROM or bootloader may have additional requirements. Temporary boot success does not guarantee permanent installation.

From bootloader fastboot, repeat `fastboot getvar current-slot` and the matching `partition-size` check. Write **only the current slot**; replace the path with the image you actually tested. Choose exactly one of these commands:

```bash
# Only if current-slot is a:
fastboot flash boot_a "$HOME/nuwa/dualboot-test.img"
# Only if current-slot is b:
fastboot flash boot_b "$HOME/nuwa/dualboot-test.img"
```

Then run `fastboot reboot`. Confirm Android, KernelSU Next, Volume Down → UEFI, Linux and recovery. This changes the chosen `boot` partition; it does not intentionally modify the recovery partition, but a recovery boot can still depend on that kernel. **Do not run `fastboot set_active` or flash both slots.**

## 8. Restore the backup

If the installed image fails and bootloader fastboot is reachable, check `fastboot getvar current-slot` and restore the **verified matching backup for that same slot and ROM**. For example, if the current slot is `a` and the helper saved the backup to the directory above:

```bash
fastboot flash boot_a "$HOME/nuwa/boot-backup-before-dualboot/boot_a.img"
fastboot reboot
```

For slot `b`, use `boot_b` and the matching `boot_b.img` instead. Do not restore an image for a different ROM version or change the slot just to use a backup. If the backup is unavailable, or fastboot itself is unavailable, stop and follow the device/ROM's recovery procedure; this toolkit cannot guarantee recovery from every failure.

## Troubleshooting and tests

- **ADB can't see the phone:** unlock the phone, enable USB debugging, accept its authorization prompt and check the cable. The backup helper additionally requires root shell permission.
- **Builder rejects the image:** check the exact device and build, and read the error. The builder intentionally refuses already-patched images, unsupported v4 signatures, ramdisks and incompatible kernel headers. Don't force it with an older image.
- **Both choices boot Android:** confirm the button was pressed inside the selection window. A PMIC lookup failure, denied transaction or timeout also falls back to Android. A synchronous MMIO fault can still hang before fallback.
- **UEFI appears but Linux doesn't:** check the separate UEFI boot option, Linux kernel, device tree and root filesystem. This project doesn't install them.
- **Root is missing:** check the actual KernelSU Next method and ROM/KMI compatibility. A ROM's stock boot image and your rooted image need not be identical. The selector doesn't install KernelSU.
- **Run offline tests:** `python3 test_builder.py`, `python3 test_backup.py`, and `./test-selector.sh`. The last also needs `aarch64-linux-gnu-gcc`, `qemu-aarch64` and an AArch64 sysroot (`CROSS_SYSROOT`, default `/usr/aarch64-linux-gnu`). The tests use synthetic images, a mock ADB device and synthetic QEMU registers; they do not test a new ROM or hardware configuration.

For quick repeat updates, return to the [post-OTA checklist](README.md#quick-update-after-an-ota). Credits and the upstream license are in the [README](README.md#credits-and-license) and [LICENSE](LICENSE).
