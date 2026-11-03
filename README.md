# nuwa dual-boot toolkit

Build a **separate** Android boot image for the Xiaomi 13 Pro (`nuwa`) with Project Silicium UEFI and Volume Down selection. Normal boot continues into Android. These tools do not flash, reboot, change slots, modify partitions or change `vbmeta`.

## Credits and provenance

This toolkit adapts the kernel entry patching and UEFI handoff from [Project Aloha's DualBootKernelPatcher](https://github.com/Project-Aloha/DualBootKernelPatcher), itself based on the [Surface Duo dual-boot kernel patcher](https://github.com/WOA-Project/SurfaceDuoDualBootKernelImagePatcher). The original Aloha project credits the DuoWoa and AlohaWoa authors; their MIT license and copyright notice are included in `LICENSE`.

The Python builder implements the relevant patching steps; it does **not** invoke the upstream patcher executable. The Volume Down selector and timing are a nuwa-specific adaptation. The UEFI payload is built separately from [Project Silicium's Mu-Silicium](https://github.com/Project-Silicium/Mu-Silicium); no firmware or Android images are included in this repository. Button and SPMI details were informed by the Linux Qualcomm drivers and the nuwa device tree.

## What this is specific to

- Xiaomi 13 Pro (`nuwa`), the current Mu firmware linked for `0xA7100000`, and its 3 MiB FD region. The source reads the PMK8550 Volume Down PON status through the SM8550 v7 SPMI arbiter. It gives a two-second selection window at kernel entry. It does not move the current slot or write recovery.
- An **unpatched**, uncompressed ARM64 EFI-format kernel in an Android **v4** `boot.img` with no boot ramdisk and no v4 GKI boot signature. Other formats are rejected. The selector replaces the EFI/PE header, so the Android kernel in the result cannot also be used as an EFI executable.
- The default boot partition size is `0xC000000`, verified on the test device. Confirm it on your device and after firmware changes. The builder checks the FD size, but that does **not** prove an arbitrary FD was built for nuwa or linked at the required address.
- A footer with an **unsigned** AVB hash is generated. The top-level `vbmeta` is not changed or re-signed; its original boot hash will differ. On the inspected setup its verification flags were disabled. A successful temporary boot does not establish that a different future AVB configuration will accept a flashed image. Never relock the bootloader with modified images.

## Dependencies

Linux host with Python 3, Android platform-tools (`adb`, `fastboot`), `avbtool`, `aarch64-linux-gnu-as`, `aarch64-linux-gnu-objcopy`, and SHA-256 tools. Optional selector tests use `aarch64-linux-gnu-gcc`, `qemu-aarch64` and an AArch64 Linux sysroot (default `/usr/aarch64-linux-gnu`). Set `CROSS_SYSROOT` to override it. Root shell access must be enabled in KernelSU Next for a live backup.

## After an OTA

1. Boot the updated Android and confirm it is the intended build. An OTA may itself boot another slot; these tools do not switch slots. Read the actual current slot and use the matching slot's images. KernelSU Next compatibility and whether it resides in the kernel or ramdisk may change with an OTA; verify the running build and root setup rather than assuming the downloaded ROM contains your current modifications.

2. With the phone connected and authorized for ADB, save its **current** active-slot boot partition to a new directory:

   ```bash
   ./backup-active.sh "$HOME/nuwa/boot-backup-after-ota"
   ```

   The helper checks the slot, reads the partition through `su`, compares its SHA-256 on the phone and computer, and refuses to overwrite an existing backup. A backup of an already dual-boot-patched image is a backup, **not** an unpatched base for the builder. Keep a separate unpatched image matching the current ROM and KernelSU Next configuration. Do not use an old ROM image after an OTA. Do not patch the output twice.

3. Check the matching unpatched base, the actual boot partition size, and the FD. The default FD is `~/nuwa/Mu-Silicium/Build/nuwaPkg/RELEASE_CLANGPDB/FV/SILICIUM_UEFI.fd`. It must be a raw, compatible firmware volume, not `Mu-nuwa.img` or a BootShim wrapper. A firmware update may change the required memory layout and invalidate this selector.

   ```bash
   python3 build.py --boot /path/to/new-unpatched-boot.img \
     --fd "$HOME/nuwa/Mu-Silicium/Build/nuwaPkg/RELEASE_CLANGPDB/FV/SILICIUM_UEFI.fd" \
     --out "$HOME/nuwa/new-dualboot-test.img"
   ```

   The output must not exist. Use `--partition-size 0x...` only with the size read from the bootloader for the current device. Save the printed image hash and boot backup. The optional `--salt` gives reproducible output and must be 64 hex digits; otherwise avbtool supplies a random salt.

4. Boot the **exact output** temporarily, without flashing:

   ```bash
   adb reboot bootloader
   fastboot devices
   fastboot getvar current-slot
   fastboot getvar unlocked
   fastboot boot "$HOME/nuwa/new-dualboot-test.img"
   ```

   Test normal Android startup and KernelSU Next, then repeat with Volume Down during the selection window and release it as UEFI starts. Confirm Linux starts from UEFI. If fastboot rejects the image or the phone hangs, do not replace `boot` with `flash`: reboot normally or hold Power to restart. A working `fastboot boot` does not guarantee a persistent flash will pass AVB or that recovery will work.

5. Consider permanent installation only after both paths pass and you have the matching recovery backup and know how to restore it. Confirm actual current slot and the `boot` partition size in fastboot, verify the image hash again, and flash only that explicitly named slot; do not use `set_active`. Recovery may still depend on the boot kernel despite its separate partition: verify recovery after installation. Keep your computer and matching backup available. An OTA can overwrite the modification.

Keep a verified backup of your own current boot image outside this repository. A backup from an earlier ROM build may not be suitable after an OTA.

## Run the offline checks

```bash
python3 test_builder.py
python3 test_backup.py
./test-selector.sh
```

The first test builds a synthetic image, checks its AVB footer and verifies input preservation, no-overwrite behavior and rejection cases. The second tests the backup helper with a mock ADB device. The third runs the actual selector under QEMU against synthetic memory/registers for released, pressed, delayed-press, missing mapping, wrong version, error and timeout paths. No test accesses the phone or proves behavior on future firmware.
