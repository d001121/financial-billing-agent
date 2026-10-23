"""Versioned configuration reads and atomic file transactions."""
from contextlib import contextmanager
import os
from pathlib import Path
import tempfile
from threading import RLock
import yaml
from backend.infrastructure.repository import Conflict
from .settings import ROOT
from .validation import validate_configuration
from .prompts import resolve_agent_prompts

_THREAD_LOCK = RLock()
KINDS = ('agents', 'mcp', 'skills', 'hooks', 'runtime')


@contextmanager
def configuration_lock(root):
    """One OS file lock for version checks and cross-kind references, plus threads."""
    with _THREAD_LOCK:
        path = Path(root) / 'config' / '.write.lock'
        with path.open('a+b') as handle:
            if handle.seek(0, os.SEEK_END) == 0:
                handle.write(b'0')
                handle.flush()
            handle.seek(0)
            try:
                if os.name == 'nt':
                    import msvcrt
                    msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            except OSError as exc:
                raise Conflict('配置正在由其他进程保存，请重试') from exc
            try:
                yield
            finally:
                handle.seek(0)
                if os.name == 'nt':
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def read_config(kind):
    if kind not in KINDS:
        raise KeyError(kind)
    value = yaml.safe_load((ROOT / 'config' / f'{kind}.yaml').read_text(encoding='utf-8'))
    return resolve_agent_prompts(value, ROOT) if kind == 'agents' else value


def write_config(kind, value, expected_version=None):
    if kind not in KINDS:
        raise KeyError(kind)
    if not isinstance(value, dict):
        raise ValueError('配置必须是对象')
    with configuration_lock(ROOT):
        config = {key: read_config(key) for key in KINDS}
        current = config[kind]
        expected = expected_version if expected_version is not None else value.get('version')
        if type(expected) is not int or expected != current['version']:
            raise Conflict('配置版本已过期或未提供，请刷新后修改')
        value = dict(value, version=current['version'] + 1)
        config[kind] = value
        value = validate_configuration(config, ROOT)[kind]
        path = ROOT / 'config' / f'{kind}.yaml'
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', newline='\n',
                    dir=path.parent, prefix=kind + '.', suffix='.tmp', delete=False) as handle:
                temporary = Path(handle.name)
                yaml.safe_dump(value, handle, allow_unicode=True, sort_keys=False)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    return value
