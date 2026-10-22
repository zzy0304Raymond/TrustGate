"""Verify the English release against the original experiment artifact hashes.

Experiment manifests and measurements retain their original identities. An
explicit release map binds each translated artifact to both its original hash
and its current byte hash. Only exact, listed English revisions are accepted;
unlisted edits are never normalized or ignored.
"""
import hashlib
import json
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / 'docs/english_revision.json'


def actual_sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


@lru_cache(maxsize=1)
def _aliases():
    manifest = json.loads(MANIFEST.read_text())
    if manifest['schema_version'] != 1:
        raise ValueError('Unsupported English revision manifest')
    if actual_sha256(Path(__file__)) != manifest['integrity_helper_sha256']:
        raise ValueError('Release integrity helper differs from its recorded version')
    aliases = {}
    for record in manifest['files']:
        original, translated = record['original_sha256'], record['english_sha256']
        if translated in aliases and aliases[translated] != original:
            raise ValueError('Ambiguous artifact revision')
        aliases[translated] = original
    return aliases


def recorded_digest(actual_digest):
    """Resolve an exact approved English artifact to its recorded experiment hash."""
    return _aliases().get(actual_digest, actual_digest)


def verify_release():
    """Check every approved revision against the actual current file bytes."""
    _aliases()
    manifest = json.loads(MANIFEST.read_text())
    for record in manifest['files']:
        path = (ROOT / record['path']).resolve()
        if not path.is_relative_to(ROOT):
            raise ValueError('Revision path escapes the repository')
        if actual_sha256(path) != record['english_sha256']:
            raise ValueError('English revision differs: ' + record['path'])
    for name, expected in manifest['unchanged_measurements'].items():
        if actual_sha256(ROOT / name) != expected:
            raise ValueError('Original experiment data changed: ' + name)
    return len(manifest['files'])
