# nuwa dual-boot toolkit

Build an Android boot image that lets a **Xiaomi 13 Pro (`nuwa`)** boot Android normally and enter Project Silicium UEFI with **Volume Down**. From UEFI, you can start a separately prepared Linux installation.

**New here? Start with the [complete setup guide](GUIDE.md).** It explains the requirements, where to get the images, backups, testing, installation and recovery. The quick update below is for a setup that already works.

## Quick update after an OTA

1. Boot the updated ROM. Check the **current** slot; an OTA may have changed it on its own. Obtain an **unpatched** `boot.img` matching that exact ROM and your KernelSU setup. An old ROM image or an already dual-boot-patched image is not a suitable base.
2. Save the current active-slot boot image. This requires an authorized ADB connection and root shell access:

   ```bash
   cd nuwa-dualboot-toolkit
   ./backup-active.sh "$HOME/nuwa/boot-backup-after-ota"
   ```

   Use a new backup directory for each update. Keep a separate verified backup for restoring the current build; the helper backs up whatever is currently installed, which may already be patched.
3. Build a new image using your compatible **raw** nuwa Mu-Silicium FD (the default path is shown):

   ```bash
   python3 build.py \
     --boot /path/to/new-unpatched-boot.img \
     --fd "$HOME/nuwa/Mu-Silicium/Build/nuwaPkg/RELEASE_CLANGPDB/FV/SILICIUM_UEFI.fd" \
     --out "$HOME/nuwa/new-dualboot-test.img"
   ```

4. Temporarily boot the exact output. Confirm `nuwa`, the current slot, unlock state and partition size as described in the guide:

   ```bash
   adb reboot bootloader
   fastboot devices -l
   fastboot getvar current-slot
   fastboot boot "$HOME/nuwa/new-dualboot-test.img"
   ```

   Test **both** Android and Volume Down → UEFI, plus KernelSU Next and Linux. Check AVB behavior and the recovery plan before considering a flash. See [test and install](GUIDE.md#6-test-with-fastboot-boot) and [restore](GUIDE.md#8-restore-the-backup). Do not use `set_active`.

The image produced by an OTA can differ in format or root method. **Stop if the builder rejects it**; do not use an older boot image to work around the error. An OTA can overwrite the dual-boot patch.

## Compatibility at a glance

- **Device:** Xiaomi 13 Pro (`nuwa`) only. The Volume Down selector reads the SM8550/PMK8550 button through a device-specific register layout.
- **Android image:** an unpatched, uncompressed ARM64 EFI-format kernel in a v4 `boot.img`, with no boot ramdisk and no v4 GKI boot signature. The builder rejects other formats. It modifies the kernel's PE header, so that Android kernel cannot also be used as an EFI executable.
- **UEFI:** a compatible nuwa Mu-Silicium **raw FD**, 3 MiB and linked for `0xA7100000`. Size alone does not prove an FD is compatible. A different port or firmware layout can require code changes.
- **AVB:** the generated image has an unsigned hash footer; top-level `vbmeta` is not changed or re-signed and its original boot hash differs. The tested device had verification disabled. A different AVB configuration may reject permanent installation, even after a temporary boot succeeds. Never relock the bootloader with modified images.

This toolkit creates and checks files. It **does not** flash the phone, reboot it, switch slots, install Linux or modify recovery or `vbmeta`.

## Tests

```bash
python3 test_builder.py
python3 test_backup.py
./test-selector.sh
```

The first uses synthetic boot images to test the builder and rejection cases. The second tests backup behavior with mock ADB. The third runs the selector against synthetic registers under QEMU. These tests do not access a phone or prove compatibility with future firmware. See the [guide](GUIDE.md#troubleshooting-and-tests) for dependencies and limits.

## Credits and license

The kernel-entry patch and UEFI handoff adapt [Project Aloha's DualBootKernelPatcher](https://github.com/Project-Aloha/DualBootKernelPatcher), itself based on the [Surface Duo dual-boot kernel patcher](https://github.com/WOA-Project/SurfaceDuoDualBootKernelImagePatcher). Thanks to the DuoWoa and AlohaWoa authors; their MIT license and copyright notices are in [LICENSE](LICENSE).

The Python builder implements the relevant patching steps; it does **not** invoke the upstream patcher executable. The button selector is nuwa-specific. The UEFI payload comes from a separate [Project Silicium Mu-Silicium](https://github.com/Project-Silicium/Mu-Silicium) build. Button and SPMI details were informed by the Linux Qualcomm drivers and nuwa device tree. No Android images, firmware or personal backups are included here.
