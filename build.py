#!/usr/bin/env python3
"""Build a nuwa boot image offline; never access or write device partitions."""
import argparse
import hashlib
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import tempfile

PAGE = 4096
FD_BASE = 0xA7100000
FD_SIZE = 0x300000
DEFAULT_PARTITION_SIZE = 0xC000000


def require(condition, message):
    if not condition:
        raise ValueError(message)


def run(*args):
    return subprocess.run(args, check=True, text=True, capture_output=True)


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--boot', type=Path, required=True, help='unpatched boot image for the current Android build')
    p.add_argument('--fd', type=Path, default=Path.home() / 'nuwa/Mu-Silicium/Build/nuwaPkg/RELEASE_CLANGPDB/FV/SILICIUM_UEFI.fd', help='raw nuwa Mu firmware volume, not a boot image')
    p.add_argument('--out', type=Path, required=True, help='new output image; existing files are never overwritten')
    p.add_argument('--partition-size', type=lambda n: int(n, 0), default=DEFAULT_PARTITION_SIZE, help='boot partition size in bytes (default: this nuwa 0xC000000)')
    p.add_argument('--salt', help='optional 64-character hexadecimal AVB salt, for reproducible builds')
    args = p.parse_args()

    for tool in ('aarch64-linux-gnu-as', 'aarch64-linux-gnu-objcopy', 'avbtool'):
        require(shutil.which(tool), f'missing required program: {tool}')
    require(args.boot.is_file(), f'boot image not found: {args.boot}')
    require(args.fd.is_file(), f'firmware not found: {args.fd}')
    require(args.out.parent.is_dir(), f'output directory not found: {args.out.parent}')
    require(not args.out.exists(), f'output exists, refusing to overwrite: {args.out}')
    require(args.partition_size > 0 and args.partition_size % PAGE == 0, 'partition size must be positive and a multiple of 4096')
    require(args.salt is None or re.fullmatch(r'[0-9a-fA-F]{64}', args.salt), 'salt must be exactly 64 hex characters')

    with args.boot.open('rb') as f:
        header = bytearray(f.read(PAGE))
        require(len(header) == PAGE and header[:8] == b'ANDROID!', 'not an Android boot image')
        kernel_size, ramdisk_size = struct.unpack_from('<II', header, 8)
        header_size, = struct.unpack_from('<I', header, 20)
        version, = struct.unpack_from('<I', header, 40)
        require(version == 4 and header_size == 1584, 'only Android boot header v4 (size 1584) is supported')
        signature_size, = struct.unpack_from('<I', header, 1580)
        require(ramdisk_size == 0, 'boot image has a ramdisk; unsupported layout')
        require(signature_size == 0, 'boot image has a GKI boot signature; unsupported without re-signing')
        require(0x200 <= kernel_size <= args.partition_size - PAGE, 'invalid or oversized kernel')
        kernel = bytearray(f.read(kernel_size))
    require(len(kernel) == kernel_size, 'truncated boot image')
    require(kernel_size % 16 == 0, 'kernel length must be 16-byte aligned for the UEFI copy')
    require(kernel[:2] == b'MZ' and kernel[56:60] == b'ARMd', 'kernel must be an unpatched, uncompressed ARM64 EFI Image')
    require((struct.unpack_from('<I', kernel, 4)[0] & 0xfc000000) == 0x14000000, 'unsupported ARM64 entry branch')
    pe = struct.unpack_from('<I', kernel, 60)[0]
    require(pe == 0x40 and kernel[pe:pe + 4] == b'PE\0\0', 'unsupported EFI header layout or already patched')
    machine, nsections = struct.unpack_from('<HH', kernel, pe + 4)
    optsize = struct.unpack_from('<H', kernel, pe + 20)[0]
    require(machine == 0xaa64 and 0 < nsections <= 32, 'invalid ARM64 PE section table')
    section_table = pe + 24 + optsize
    require(section_table + 40 * nsections <= len(kernel), 'truncated PE section table')
    offsets = [struct.unpack_from('<I', kernel, section_table + 40*i + 20)[0] for i in range(nsections)]
    offsets = [n for n in offsets if n]
    require(offsets and min(offsets) >= 0x190, 'not enough header space for selector')

    fd = args.fd.read_bytes()
    require(len(fd) == FD_SIZE, f'nuwa FD must be exactly {FD_SIZE} bytes; got {len(fd)}')
    require(not fd.startswith(b'ANDROID!'), 'expected raw FD, not an Android boot image')
    require(kernel_size + len(fd) + PAGE + 65536 <= args.partition_size, 'patched image does not fit boot partition with AVB overhead')
    selector = Path(__file__).resolve().with_name('selector.S')
    require(selector.is_file(), f'selector source missing: {selector}')

    # Preserve boot build properties, if the input has an AVB footer.
    info = subprocess.run(['avbtool', 'info_image', '--image', str(args.boot)], text=True, capture_output=True)
    props = []
    if info.returncode == 0:
        for line in info.stdout.splitlines():
            m = re.fullmatch(r"\s*Prop: (com\.android\.build\.boot\.(?:os_version|fingerprint)) -> '([^']*)'", line)
            if m:
                props += ['--prop', f'{m.group(1)}:{m.group(2)}']
    else:
        print('Note: source has no readable AVB footer; no boot properties copied.', file=sys.stderr)

    with tempfile.TemporaryDirectory(prefix='.nuwa-build-', dir=args.out.parent) as tmp:
        temp = Path(tmp)
        run('aarch64-linux-gnu-as', str(selector), '-o', str(temp / 'selector.o'))
        run('aarch64-linux-gnu-objcopy', '-O', 'binary', str(temp / 'selector.o'), str(temp / 'selector.bin'))
        code = (temp / 'selector.bin').read_bytes()
        require(len(code) == 0x190 and len(code) <= min(offsets), 'unexpected selector size')
        require(code[:0x40] == bytes(0x40), 'unexpected selector header')
        struct.pack_into('<I', kernel, 0, 0x14000010)
        struct.pack_into('<QQQ', kernel, 0x20, FD_BASE, FD_SIZE, kernel_size)
        kernel[0x40:len(code)] = code[0x40:]
        struct.pack_into('<I', header, 8, kernel_size + len(fd))
        target = temp / 'boot.img'
        with target.open('wb') as f:
            f.write(header)
            f.write(kernel)
            f.write(fd)
            f.write(bytes((-f.tell()) % PAGE))
        command = ['avbtool', 'add_hash_footer', '--image', str(target), '--partition_name', 'boot', '--partition_size', str(args.partition_size), '--algorithm', 'NONE', *props]
        if args.salt:
            command += ['--salt', args.salt.lower()]
        run(*command)
        require(target.stat().st_size == args.partition_size, 'unexpected final image size')
        check = run('avbtool', 'verify_image', '--image', str(target))
        require('Successfully verified' in check.stdout, 'AVB verification did not report success')
        # Both paths are on the same filesystem. link() fails if output exists,
        # so a race cannot overwrite another file.
        os.link(target, args.out)

    print(f'Created: {args.out.resolve()}')
    print(f'SHA-256: {digest(args.out)}')
    print(f'Source boot SHA-256: {digest(args.boot)}')
    print(f'Firmware SHA-256: {hashlib.sha256(fd).hexdigest()}')
    print('Temporary fastboot testing is required. The AVB footer is unsigned; top-level vbmeta was not changed.')
    print('This patches the EFI header. The Android kernel in this image is not usable as an EFI executable.')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f'Error: {exc}', file=sys.stderr)
        if isinstance(exc, subprocess.CalledProcessError) and exc.stderr:
            print(exc.stderr, file=sys.stderr)
        sys.exit(1)
