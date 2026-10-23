"""Application asset references, independent of the checkout directory."""
from pathlib import Path

from backend.config import settings


def asset_file(record):
    """Resolve a saved asset reference, including pre-portability records."""
    relative = record.get('storage_path')
    if relative is None:
        original = Path(record['path'])
        if original.is_absolute() and original.resolve().is_relative_to(settings.ASSETS.resolve()):
            relative = original.resolve().relative_to(settings.ASSETS.resolve())
        else:
            # Old records saved absolute Windows paths. Preserve the path beneath
            # the application's data/assets directory after moving the package.
            parts = original.parts
            matches = [i for i in range(len(parts) - 1)
                       if parts[i].lower() == 'data' and parts[i + 1].lower() == 'assets']
            if not matches:
                raise ValueError('原件没有可迁移的任务材料引用')
            relative = Path(*parts[matches[-1] + 2:])
    target = (settings.ASSETS / relative).resolve()
    if not target.is_relative_to(settings.ASSETS.resolve()):
        raise ValueError('原件不在任务材料目录')
    return target


def add_storage_references(value):
    """Keep the original diagnostic path and add a portable storage reference."""
    if isinstance(value, dict):
        if isinstance(value.get('path'), str):
            try:
                value['storage_path'] = asset_file(value).relative_to(settings.ASSETS.resolve()).as_posix()
            except ValueError:
                pass  # Non-asset metadata paths are not application file handles.
        for item in value.values():
            add_storage_references(item)
    elif isinstance(value, list):
        for item in value:
            add_storage_references(item)
    return value
