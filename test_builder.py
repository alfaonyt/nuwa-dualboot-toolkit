#!/usr/bin/env python3
"""Offline checks using synthetic images. Never accesses a device."""
import hashlib
from pathlib import Path
import struct
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent


def main():
    with tempfile.TemporaryDirectory(prefix='nuwa-toolkit-test-') as td:
        d = Path(td)
        fd = d / 'fd.bin'
        fd.write_bytes(b'F' * 0x300000)
        h = bytearray(4096)
        h[:8] = b'ANDROID!'
        struct.pack_into('<I', h, 8, 0x11000)
        struct.pack_into('<I', h, 20, 1584)
        struct.pack_into('<I', h, 40, 4)
        k = bytearray(0x11000)
        k[:2] = b'MZ'
        struct.pack_into('<I', k, 4, 0x14000001)
        k[56:60] = b'ARMd'
        struct.pack_into('<I', k, 60, 0x40)
        k[0x40:0x44] = b'PE\0\0'
        struct.pack_into('<HH', k, 0x44, 0xaa64, 1)
        struct.pack_into('<H', k, 0x54, 0xa0)
        struct.pack_into('<I', k, 0x40 + 24 + 0xa0 + 20, 0x10000)
        base = d / 'source.img'
        base.write_bytes(h + k)
        before = hashlib.sha256(base.read_bytes()).hexdigest()

        def build(source, out, firmware=fd, expected=0):
            cmd = [sys.executable, str(HERE / 'build.py'), '--boot', str(source), '--fd', str(firmware), '--out', str(out), '--partition-size', '0x800000', '--salt', '12' * 32]
            p = subprocess.run(cmd, capture_output=True, text=True)
            if (p.returncode == 0) != (expected == 0):
                raise AssertionError(f'{cmd}: {p.returncode}\n{p.stdout}\n{p.stderr}')
            return p

        out = d / 'result.img'
        build(base, out)
        data = out.read_bytes()
        assert len(data) == 0x800000
        assert struct.unpack_from('<I', data, 8)[0] == len(k) + 0x300000
        assert data[4096 + len(k):4096 + len(k) + len(fd.read_bytes())] == fd.read_bytes()
        assert hashlib.sha256(base.read_bytes()).hexdigest() == before
        out_hash = hashlib.sha256(data).hexdigest()
        build(base, out, expected=1)
        assert hashlib.sha256(out.read_bytes()).hexdigest() == out_hash
        build(out, d / 'double.img', expected=1)
        badfd = d / 'badfd'
        badfd.write_bytes(b'bad')
        build(base, d / 'badfd.img', firmware=badfd, expected=1)
        for name, offset in [('signature', 1580), ('ramdisk', 12)]:
            changed = bytearray(base.read_bytes())
            struct.pack_into('<I', changed, offset, 1)
            bad = d / (name + '.img')
            bad.write_bytes(changed)
            build(bad, d / (name + '-out.img'), expected=1)
            assert not (d / (name + '-out.img')).exists()
        print('PASS: valid build, hash/footer verification, preserved input, no overwrite, double patch, bad firmware, signature and ramdisk rejection')


if __name__ == '__main__':
    main()
