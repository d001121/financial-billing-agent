"""Freeze task capabilities and publish immutable Skill resources."""
from hashlib import sha256
from pathlib import Path
import tempfile
from backend.config.settings import ROOT, RELEASES
from backend.config.transactions import KINDS, read_config, configuration_lock
from backend.infrastructure.repository import repository, dumps
from .skill_versions import _verify_release


def snapshot():
    with configuration_lock(ROOT):
        config = {k: read_config(k) for k in KINDS}
    improvements = repository().get('improvement_registry', 'default', required=False) or {
        'active_version': None, 'versions': []}
    experiences = ([item for item in repository().list('experience', limit=10000)
                   if item.get('status') == 'active']
                   if config['runtime'].get('use_reviewed_experiences', True) else [])
    if not any(s['name'] == 'feedback-improvement' and s.get('enabled', True)
               for s in config['skills']['skills']):
        improvements = {'active_version': None, 'versions': []}
        experiences = []
    files = {}
    for skill in config['skills']['skills']:
        if not skill.get('enabled', True):
            continue
        directory = ROOT / 'skills' / skill['name']
        if not (directory / 'SKILL.md').is_file():
            raise ValueError(f"Skill不完整: {skill['name']}")
        for path in sorted(directory.rglob('*')):
            if path.is_file() and not any(p.startswith('.') or p == '__pycache__' for p in path.relative_to(directory).parts):
                files[path.relative_to(ROOT / 'skills').as_posix()] = path.read_bytes()
    digest = sha256(dumps({'config': config, 'improvements': improvements, 'experiences': experiences}).encode())
    for path, content in files.items():
        digest.update(path.encode())
        digest.update(content)
    version = digest.hexdigest()[:20]
    destination = RELEASES / version / 'skills'
    capability = dict(version=version, config=config, improvements=improvements, experiences=experiences)
    with configuration_lock(ROOT):
        if destination.parent.exists():
            _verify_release(destination, files)
            return capability
    RELEASES.mkdir(parents=True, exist_ok=True)
    # Materialize away from the public version path. Readers can only observe a
    # complete directory, and competing publishers retain their own staging tree.
    with tempfile.TemporaryDirectory(prefix='.snapshot-', dir=RELEASES) as staging_name:
        staging = Path(staging_name)
        (staging / 'skills').mkdir()
        for path, content in files.items():
            target = staging / 'skills' / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        with configuration_lock(ROOT):
            if destination.parent.exists():
                _verify_release(destination, files)
            else:
                # Same-filesystem rename publishes the already complete tree.
                # Existing versions are never replaced or written into.
                staging.rename(destination.parent)
    return capability
