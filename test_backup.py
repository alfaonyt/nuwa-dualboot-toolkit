#!/usr/bin/env python3
"""Test backup helper with a simulated ADB device, entirely offline."""
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent


def main():
    with tempfile.TemporaryDirectory(prefix='nuwa-adb-mock-') as t:
        d = Path(t)
        payload = b'fake-boot-partition-content\n'
        digest = hashlib.sha256(payload).hexdigest()
        fake = d / 'adb'
        fake.write_text('''#!/usr/bin/env python3
import os,sys
a = sys.argv[1:]
if a == ['get-state']: print('device')
elif a == ['shell','getprop','ro.product.device']: print('nuwa')
elif a == ['shell','getprop','ro.boot.slot_suffix']: print('_a')
elif a[:3] == ['shell','su','-c']:
 print(('0'*64 if os.environ.get('BAD_HASH') else os.environ['MOCK_HASH']) + '  /dev/block/by-name/boot_a')
elif a[:3] == ['exec-out','su','-c']: sys.stdout.buffer.write(b'fake-boot-partition-content\\n')
else: sys.exit(2)
''')
        fake.chmod(0o755)
        env = {**os.environ, 'PATH': str(d) + os.pathsep + os.environ['PATH'], 'MOCK_HASH': digest}
        helper = str(HERE / 'backup-active.sh')
        good = d / 'good'
        result = subprocess.run([helper, str(good)], env=env, capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        backup = good / 'boot_a.img'
        assert backup.read_bytes() == payload
        result = subprocess.run([helper, str(good)], env=env, capture_output=True, text=True)
        assert result.returncode != 0 and backup.read_bytes() == payload
        bad = d / 'bad'
        result = subprocess.run([helper, str(bad)], env={**env, 'BAD_HASH': '1'}, capture_output=True, text=True)
        assert result.returncode != 0 and not (bad / 'boot_a.img').exists()
        print('PASS: read-only backup, hash verification, no overwrite, and mismatch rejection (mock ADB)')


if __name__ == '__main__':
    main()
