"""Local package storage for the native SkillsMiddleware, not a Skill runner.

Docs/API MCP: SkillsMiddleware discovery, skills_metadata invalidation and
include_tools (deepagents 0.7.29). The framework loads instructions and calls
tools; it does not install an uploaded ZIP or transact this app's registry.
"""
from io import BytesIO
from pathlib import PurePosixPath
import shutil
import stat
import tempfile
from zipfile import ZipFile, BadZipFile

from deepagents.backends import FilesystemBackend
from deepagents.middleware.skills import SkillsMiddleware
from langgraph.runtime import Runtime

from backend.config import transactions
from backend.infrastructure.repository import Conflict


def discover(root):
    result = SkillsMiddleware(backend=FilesystemBackend(root_dir=root), sources=['/']).before_agent(
        {'messages': []}, Runtime(), {})
    return result.get('skills_metadata', [])


def catalog():
    root = transactions.ROOT / 'skills'
    registered = {s['name']: s for s in transactions.read_config('skills')['skills']}
    return [dict(name=m['name'], description=m['description'],
                 version=m.get('metadata', {}).get('version', '1.0.0'),
                 registered=m['name'] in registered, config=registered.get(m['name']),
                 files=[p.relative_to(root / m['name']).as_posix()
                        for p in sorted((root / m['name']).rglob('*'))
                        if p.is_file() and not any(part.startswith('.') or part == '__pycache__'
                            for part in p.relative_to(root / m['name']).parts)])
            for m in discover(root)]


def resource(name, path='SKILL.md'):
    root = (transactions.ROOT / 'skills').resolve()
    package = (root / name).resolve()
    target = (package / path).resolve()
    if not package.is_relative_to(root) or package == root or not target.is_relative_to(package):
        raise ValueError('Skill资源路径越界')
    if target.suffix.lower() not in ('.md', '.py', '.json', '.yaml', '.yml', '.txt', '.toml'):
        raise ValueError('此资源不支持文本预览')
    if not target.is_file():
        raise KeyError(path)
    return dict(name=name, path=path, content=target.read_text(encoding='utf-8-sig'))


def install(content, expected_version, tools):
    if len(content) > 20 * 1024 * 1024:
        raise ValueError('Skill ZIP最大20MB')
    with tempfile.TemporaryDirectory(prefix='.skill-import-', dir=transactions.ROOT) as tmp:
        staging = transactions.ROOT / tmp
        try:
            with ZipFile(BytesIO(content)) as archive:
                infos = [i for i in archive.infolist() if not i.is_dir()]
                if not infos or len(infos) > 500 or sum(i.file_size for i in infos) > 40 * 1024 * 1024:
                    raise ValueError('Skill包为空或超过500文件/40MB解压限制')
                names = set()
                for entry in infos:
                    path = PurePosixPath(entry.filename.replace('\\', '/'))
                    if (path.is_absolute() or any(part in ('.', '..') or ':' in part for part in path.parts)
                            or stat.S_ISLNK(entry.external_attr >> 16)):
                        raise ValueError('Skill包包含越界路径或符号链接')
                    identity = path.as_posix().casefold()
                    if identity in names:
                        raise ValueError('Skill包包含重复路径')
                    names.add(identity)
                    target = staging.joinpath(*path.parts)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(archive.read(entry))
        except BadZipFile as exc:
            raise ValueError('请上传有效的Skill ZIP') from exc
        candidates = list(staging.rglob('SKILL.md'))
        if len(candidates) != 1:
            raise ValueError('一次导入一个Skill，包内须有且仅有一个SKILL.md')
        package = candidates[0].parent
        # Native discovery expects a parent containing named package directories.
        import_root = staging / '.discovery'
        import_root.mkdir()
        probe = import_root / 'package'
        shutil.copytree(package, probe, ignore=shutil.ignore_patterns('.discovery'))
        metadata = discover(import_root)
        if len(metadata) != 1:
            raise ValueError('SKILL.md缺少有效的name/description frontmatter')
        info = metadata[0]
        from backend.config.schemas import Skill
        definition = Skill(name=info['name'], enabled=True,
            version=info.get('metadata', {}).get('version', '1.0.0'), tools=tools).model_dump()
        config = transactions.read_config('skills')
        destination = transactions.ROOT / 'skills' / definition['name']
        if destination.exists() or any(s['name'] == definition['name'] for s in config['skills']):
            raise Conflict('同名Skill已安装；请查看现有内容或使用新的包名称，不能覆盖在用包')
        (probe / 'references').mkdir(exist_ok=True)
        (probe / 'scripts').mkdir(exist_ok=True)
        probe.rename(destination)
        try:
            config['skills'].append(definition)
            saved = transactions.write_config('skills', config, expected_version)
        except BaseException:
            shutil.rmtree(destination)
            raise
        return dict(config=saved, skill=definition)
