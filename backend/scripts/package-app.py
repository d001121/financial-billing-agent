"""Package the Windows app and its real private Python runtime using stdlib only.

This is a deployment utility, not an agent runner. State is opt-in. SQLite uses
its backup API rather than copying a live WAL database. No directory is deleted.
"""
from argparse import ArgumentParser
from collections import Counter
from contextlib import closing
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
from uuid import uuid4
from zipfile import ZIP_DEFLATED, ZipFile


BACKEND_ROOT = Path(__file__).resolve().parents[1]
ROOT = BACKEND_ROOT.parent
DIRECTORIES = ('backend/bishi1', 'backend/src', 'backend/skills', 'backend/hooks',
               'backend/config', 'backend/tests', 'backend/evals', 'backend/examples',
               'backend/scripts', 'backend/data/samples', 'frontend', 'docs')
ROOT_FILES = ('AGENT.md', 'AGENTS.md', 'README.md', 'start.cmd', 'backend/README.md',
              'backend/.env', 'backend/python.cmd', 'backend/start.cmd',
              'backend/langgraph.json', 'backend/requirements.txt',
              'backend/requirements.lock.txt')
EXCLUDED_PARTS = {'.build', 'delivery', 'node_modules', '__pycache__',
                  '.pytest_cache', '.git', 'sample-check', '.sample-check'}
REQUIRED = ('backend/bishi1/python.exe', 'backend/bishi1/python313._pth',
            'backend/.env', 'README.md', 'frontend/dist/index.html',
            'backend/src/backend/agents.py', 'backend/langgraph.json',
            'backend/requirements.lock.txt', 'AGENT.md', 'backend/python.cmd',
            'backend/start.cmd', 'start.cmd', 'docs/portable-environment.md')
DEV_METADATA = Path('backend/.langgraph_api/.langgraph_ops.pckl')
DATABASE = Path('backend/data/checkpoints.sqlite')


def selected_files(include_state=False):
    """Use a reviewable top-level allowlist; exclude caches at every depth."""
    files = set()
    for name in DIRECTORIES:
        directory = ROOT / name
        if directory.is_dir():
            for parent, directories, filenames in directory.walk():
                directories[:] = [part for part in directories if part not in EXCLUDED_PARTS]
                files.update(parent / name for name in filenames)
    files.update(ROOT / name for name in ROOT_FILES if (ROOT / name).is_file())
    if include_state:
        for name in ('backend/data/assets', 'backend/data/releases'):
            directory = ROOT / name
            if directory.is_dir():
                for parent, directories, filenames in directory.walk():
                    directories[:] = [part for part in directories if part not in EXCLUDED_PARTS]
                    files.update(parent / name for name in filenames)
        if (ROOT / DEV_METADATA).is_file():
            files.add(ROOT / DEV_METADATA)
    result = []
    for path in files:
        relative = path.relative_to(ROOT)
        if any(part in EXCLUDED_PARTS for part in relative.parts):
            continue
        if path.name == '.write.lock' or (relative.parts[:2] == ('backend', 'config') and path.suffix == '.tmp'):
            continue
        if path.suffix.lower() in {'.zip', '.pyc', '.pyo', '.tsbuildinfo'}:
            continue
        if not path.resolve().is_relative_to(ROOT):
            raise ValueError(f'Included file resolves outside this project: {relative}')
        result.append((relative.as_posix(), path))
    return sorted(result)


def backup_sqlite(source):
    """Read committed WAL state through SQLite; return a single complete DB."""
    stage = BACKEND_ROOT / '.build'
    stage.mkdir(exist_ok=True)
    with tempfile.NamedTemporaryFile(prefix='delivery-checkpoint-', suffix='.sqlite',
                                     dir=stage, delete=False) as temporary:
        target = Path(temporary.name)
    try:
        with closing(sqlite3.connect(source.as_uri() + '?mode=ro', uri=True)) as reader:
            with closing(sqlite3.connect(target)) as writer:
                reader.backup(writer)
                assert writer.execute('PRAGMA quick_check').fetchone() == ('ok',)
        return target
    except BaseException:
        target.unlink(missing_ok=True)
        raise


def main(argv=None):
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path,
                        default=Path('delivery/harbor-bishi1-windows-x64.zip'))
    parser.add_argument('--include-state', action='store_true',
                        help='Include assets, frozen Skill releases, consistent checkpoints and saved dev metadata')
    parser.add_argument('--dry-run', action='store_true', help='Only show the inclusion summary; do not build a ZIP')
    args = parser.parse_args(argv)
    files = selected_files(args.include_state)
    names = {name for name, _ in files}
    missing = [name for name in REQUIRED if name not in names]
    if args.include_state:
        missing.extend(str(path).replace('\\', '/') for path in (DATABASE, DEV_METADATA)
                       if not (ROOT / path).is_file())
    manifest = dict(created_at=datetime.now(timezone.utc).isoformat(),
        target='Windows x64', python='3.13.16', include_state=args.include_state,
        includes_user_authorized_env=True, missing_required=missing,
        files_by_root=dict(sorted(Counter(name.split('/')[0] for name, _ in files).items())),
        input_file_count=len(files), input_bytes=sum(path.stat().st_size for _, path in files),
        excluded=sorted(EXCLUDED_PARTS) + ['*.zip', '*.pyc', '*.pyo', '*.tsbuildinfo', '.write.lock', 'backend/config/*.tmp'],
        state_contract={
            'business_store': 'GaussDB remains external; the ZIP does not export or replace its business records',
            'checkpoints': 'sqlite3.backup includes committed WAL state' if args.include_state else 'Fresh local checkpoints',
            'dev_metadata': 'Last saved .langgraph_ops.pckl; official dev flush interval is 10 seconds' if args.include_state else 'Fresh dev metadata',
            'boundary': 'Pause tasks and wait for metadata flush before snapshotting; files and remote GaussDB are not an atomic cross-store snapshot',
        })
    if args.dry_run or missing:
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
        return 1 if missing else 0

    output = args.output if args.output.is_absolute() else ROOT / args.output
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    partial = output.with_name(output.name + '.' + uuid4().hex + '.partial')
    backup = None
    try:
        if args.include_state:
            backup = backup_sqlite(ROOT / DATABASE)
            manifest['checkpoint_backup_bytes'] = backup.stat().st_size
        with ZipFile(partial, 'w', compression=ZIP_DEFLATED, compresslevel=6, allowZip64=True) as archive:
            for name, path in files:
                archive.write(path, name)
            if backup is not None:
                archive.write(backup, DATABASE.as_posix())
            archive.writestr('delivery-manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2))
        with ZipFile(partial) as archive:
            corrupted = archive.testzip()
            if corrupted is not None:
                raise RuntimeError(f'ZIP CRC verification failed: {corrupted}')
            manifest['archive_entries'] = len(archive.infolist())
        partial.replace(output)
        manifest.update(archive=str(output), archive_bytes=output.stat().st_size,
                        archive_sha256=sha256(output.read_bytes()).hexdigest(), zip_crc='ok')
        report_path = output.with_suffix('.package.json')
        report_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
    finally:
        partial.unlink(missing_ok=True)
        if backup is not None:
            backup.unlink(missing_ok=True)
    return 0


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    raise SystemExit(main())
