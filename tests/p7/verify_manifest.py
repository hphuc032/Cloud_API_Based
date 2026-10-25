"""Hash exact Git blob content, never platform-dependent checkout bytes."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys

MANIFEST = 'docs/security/final-image-evidence-20261025/manifest.json'
BYTE_SOURCE = 'git-blob-content'


class GitBlobs:
    def __init__(self, root, revision=None, index=False):
        self.root = Path(root).resolve()
        self.git = ['git', '-c', 'safe.directory=' + self.root.as_posix(),
                    '-C', str(self.root)]
        self.index = None
        if index:
            # Resolve one index listing to OIDs before reading any content.
            # Concurrent index edits cannot mix subsequent blob reads.
            self.index = {}
            for record in self.run('ls-files', '--stage', '-z').split(b'\0'):
                if not record:
                    continue
                meta, name = record.split(b'\t', 1)
                mode, oid, stage = meta.split()
                if stage != b'0':
                    raise ValueError('Cannot verify an unmerged index')
                self.index[name.decode('utf-8')] = (mode, oid.decode('ascii'))
            self.target = 'index-snapshot'
        else:
            self.target = self.run('rev-parse', '--verify', '--end-of-options',
                                   (revision or 'HEAD') + '^{tree}').decode().strip()

    def run(self, *args):
        result = subprocess.run(self.git + list(args), capture_output=True)
        if result.returncode:
            raise ValueError('Git command failed: ' + ' '.join(args[:2]))
        return result.stdout

    def read(self, path):
        if self.index is not None:
            if path not in self.index:
                raise ValueError('Missing tracked index path: ' + path)
            mode, oid = self.index[path]
            if mode not in (b'100644', b'100755'):
                raise ValueError('Evidence must be a regular Git file: ' + path)
            return self.run('cat-file', 'blob', oid)
        return self.run('cat-file', 'blob', self.target + ':' + path)


def entries(document, manifest, expected_count):
    if document.get('hash_algorithm') != 'sha256':
        raise ValueError('Only SHA256 content digests are supported')
    rows = document.get('files')
    if not isinstance(rows, list) or len(rows) != expected_count:
        raise ValueError('Unexpected manifest entry count')
    seen = set()
    for row in rows:
        path = row.get('path', '')
        if (not isinstance(path, str) or not path or
                any(c in path for c in '\\\r\n\0:') or
                PurePosixPath(path).is_absolute() or
                any(p in ('', '.', '..', '.git') for p in path.split('/'))):
            raise ValueError('Unsafe evidence path')
        full = (PurePosixPath(manifest).parent / path).as_posix()
        if full == manifest or path in seen:
            raise ValueError('Duplicate or self-referencing manifest entry')
        seen.add(path)
        yield row, full


def verify(blobs, manifest=MANIFEST, expected_count=149):
    document = json.loads(blobs.read(manifest))
    if document.get('byte_source') != BYTE_SOURCE:
        raise ValueError('Manifest must declare git-blob-content semantics')
    failures = []
    for row, full in entries(document, manifest, expected_count):
        content = blobs.read(full)
        if (type(row.get('bytes')) is not int or row['bytes'] != len(content) or
                not isinstance(row.get('sha256'), str) or
                not re.fullmatch(r'[0-9a-f]{64}', row['sha256']) or
                row['sha256'] != hashlib.sha256(content).hexdigest()):
            failures.append(row['path'])
    return {'target': blobs.target, 'byte_source': BYTE_SOURCE,
            'entries': expected_count, 'valid': expected_count - len(failures),
            'failed': failures}


def regenerate(blobs, manifest=MANIFEST, expected_count=149):
    """Preserve membership; recompute from one selected Git tree/index snapshot."""
    previous = json.loads(blobs.read(manifest))
    rows = []
    for row, full in entries(previous, manifest, expected_count):
        content = blobs.read(full)
        rows.append({'path': row['path'], 'bytes': len(content),
                     'sha256': hashlib.sha256(content).hexdigest()})
    document = {'schema_version': 2, 'hash_algorithm': 'sha256',
                'byte_source': BYTE_SOURCE, 'path_base': 'manifest-directory',
                'self_included': False, 'files': rows}
    # This is the only write: existing manifest membership cannot add host files.
    with (blobs.root / manifest).open('w', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(document, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    target = parser.add_mutually_exclusive_group()
    target.add_argument('--revision', default=None, help='Committed revision/tree; default HEAD')
    target.add_argument('--index', action='store_true', help='Read a single stage-0 index snapshot')
    parser.add_argument('--write', action='store_true', help='Regenerate working manifest; stage it afterwards')
    args = parser.parse_args()
    try:
        blobs = GitBlobs(Path(__file__).resolve().parents[2], args.revision, args.index)
        if args.write:
            regenerate(blobs)
            print(json.dumps({'written': MANIFEST, 'source': blobs.target,
                              'next_step': 'Stage manifest, then verify --index before committing'}))
            return 0
        result = verify(blobs)
        print(json.dumps(result, indent=2))
        return 1 if result['failed'] else 0
    except (ValueError, OSError, KeyError, TypeError) as error:
        print(json.dumps({'error': str(error)}), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
