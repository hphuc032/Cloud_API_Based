"""Standalone stdlib tests; no Docker, credentials or public network required."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from verify_manifest import GitBlobs, regenerate, verify

MANIFEST = 'evidence/manifest.json'


class ManifestIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='evidence-integrity-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.git('init', '--quiet')
        self.git('config', 'core.autocrlf', 'false')
        self.git('config', 'user.name', 'Evidence Test')
        self.git('config', 'user.email', 'evidence-test@example.invalid')
        (self.root / 'evidence').mkdir()
        (self.root / 'evidence/data.txt').write_bytes(b'original\n')
        self.manifest = {'hash_algorithm': 'sha256', 'files': [
            {'path': 'data.txt', 'bytes': 0, 'sha256': '0' * 64}]}
        self.write_manifest()
        self.git('add', 'evidence')
        regenerate(GitBlobs(self.root, index=True), MANIFEST, 1)
        self.git('add', MANIFEST)
        self.git('commit', '--quiet', '-m', 'Isolated fixture')

    def git(self, *args):
        result = subprocess.run(['git', '-C', str(self.root), *args],
                                capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        return result.stdout

    def write_manifest(self):
        (self.root / MANIFEST).write_text(json.dumps(self.manifest), encoding='utf-8')

    def test_committed_content_ignores_crlf_working_copy(self):
        (self.root / 'evidence/data.txt').write_bytes(b'original\r\n')
        self.assertEqual(verify(GitBlobs(self.root), MANIFEST, 1)['valid'], 1)

    def test_staged_future_differs_from_old_head(self):
        (self.root / 'evidence/data.txt').write_bytes(b'staged-new\n')
        self.git('add', 'evidence/data.txt')
        regenerate(GitBlobs(self.root, index=True), MANIFEST, 1)
        self.git('add', MANIFEST)
        result = verify(GitBlobs(self.root, index=True), MANIFEST, 1)
        self.assertEqual(result['valid'], 1)
        staged = json.loads(GitBlobs(self.root, index=True).read(MANIFEST))
        committed = json.loads(GitBlobs(self.root).read(MANIFEST))
        self.assertNotEqual(staged['files'][0]['sha256'], committed['files'][0]['sha256'])

    def test_index_snapshot_is_stable_after_further_staging(self):
        snapshot = GitBlobs(self.root, index=True)
        (self.root / 'evidence/data.txt').write_bytes(b'future\n')
        self.git('add', 'evidence/data.txt')
        self.assertEqual(verify(snapshot, MANIFEST, 1)['valid'], 1)
        self.assertEqual(verify(GitBlobs(self.root, index=True), MANIFEST, 1)['valid'], 0)

    def test_tampered_manifest_fails(self):
        self.manifest = json.loads(GitBlobs(self.root).read(MANIFEST))
        self.manifest['files'][0]['sha256'] = '0' * 64
        self.write_manifest()
        self.git('add', MANIFEST)
        self.assertEqual(verify(GitBlobs(self.root, index=True), MANIFEST, 1)['valid'], 0)

    def test_untracked_substitute_cannot_supply_missing_blob(self):
        self.git('rm', '--cached', 'evidence/data.txt')
        self.assertTrue((self.root / 'evidence/data.txt').exists())
        with self.assertRaises(ValueError):
            verify(GitBlobs(self.root, index=True), MANIFEST, 1)

    def test_raw_nontext_bytes_remain_unchanged(self):
        raw = b'raw\r\n\x00\xff\n'
        (self.root / 'evidence/data.txt').write_bytes(raw)
        self.git('add', 'evidence/data.txt')
        regenerate(GitBlobs(self.root, index=True), MANIFEST, 1)
        self.assertEqual((self.root / 'evidence/data.txt').read_bytes(), raw)
        doc = json.loads((self.root / MANIFEST).read_text())
        self.assertEqual(doc['files'][0]['sha256'], hashlib.sha256(raw).hexdigest())

    def test_unsafe_paths_and_self_reference_fail(self):
        for path in ['../data.txt', '/data.txt', 'C:/data.txt', 'data\\txt',
                     'data\n.txt', '.git/config', 'manifest.json']:
            with self.subTest(path=path):
                self.manifest['files'][0]['path'] = path
                self.write_manifest()
                self.git('add', MANIFEST)
                with self.assertRaises(ValueError):
                    regenerate(GitBlobs(self.root, index=True), MANIFEST, 1)

    def test_unexpected_count_fails(self):
        with self.assertRaises(ValueError):
            verify(GitBlobs(self.root), MANIFEST, 149)

    def test_duplicate_paths_fail(self):
        self.manifest['files'] *= 2
        self.write_manifest()
        self.git('add', MANIFEST)
        with self.assertRaises(ValueError):
            regenerate(GitBlobs(self.root, index=True), MANIFEST, 2)


if __name__ == '__main__':
    unittest.main(verbosity=2)
