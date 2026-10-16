"""Exercise export/dedup/restore without original sources, then reject corruption."""
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest


class RecoveryBundleTest(unittest.TestCase):
    def test_roundtrip_and_corruption(self):
        # The only recursive cleanup belongs to this newly-created temp tree.
        with tempfile.TemporaryDirectory(prefix='UnlockCopilotPC-backup-test-') as folder:
            root = pathlib.Path(folder).resolve()
            self.assertTrue(root.is_relative_to(pathlib.Path(tempfile.gettempdir()).resolve()))
            source = root / 'source'
            source.mkdir()
            data = b'original\x00recovery-data'
            (source / 'first.bin').write_bytes(data)
            (source / 'second.bin').write_bytes(data)
            script = pathlib.Path(__file__).resolve().parents[1] / 'tools' / 'recovery_bundle.py'
            bundle = root / 'bundle'

            def invoke(*arguments, expected=0):
                result = subprocess.run([sys.executable, str(script), *map(str, arguments)], capture_output=True)
                self.assertEqual(result.returncode, expected, result.stderr.decode(errors='replace'))
                return result

            mapping = root / 'sources.json'
            mapping.write_text(json.dumps({'test': str(source)}), encoding='utf-8')
            invoke('--plan', '--bundle', bundle, '--source', 'test=' + str(source))
            self.assertFalse(bundle.exists())
            invoke('--export', '--bundle', bundle, '--sources-json', mapping)
            manifest = json.loads((bundle / 'manifest.json').read_text())
            self.assertTrue(manifest['complete'])
            self.assertEqual(len(list((bundle / 'objects').glob('*/*'))), 1)
            source.rename(root / 'source-not-present-at-original-path')
            invoke('--verify', '--bundle', bundle)
            restored = root / 'restored'
            invoke('--restore', '--bundle', bundle, '--destination', restored)
            self.assertEqual((restored / 'test' / 'first.bin').read_bytes(), data)
            self.assertEqual((restored / 'test' / 'second.bin').read_bytes(), data)
            next((bundle / 'objects').glob('*/*')).write_bytes(b'corrupt')
            invoke('--verify', '--bundle', bundle, expected=1)


if __name__ == '__main__':
    unittest.main()
