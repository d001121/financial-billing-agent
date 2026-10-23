"""Immutable Skill resources and native callable bindings; no Skill execution engine."""
from functools import lru_cache
import importlib.util
import sys
from backend.config.settings import ROOT, RELEASES
from backend.config.transactions import read_config


def _verify_release(directory, files):
    if not directory.is_dir() or any(not (directory / path).is_file() or
            (directory / path).read_bytes() != content for path, content in files.items()):
        raise ValueError(f'已发布能力快照不完整或已被修改: {directory.parent.name}')


def skill_root(capability):
    return RELEASES / capability['version'] / 'skills' if capability else ROOT / 'skills'


@lru_cache(maxsize=128)
def skill_module(name, version=None):
    directory = RELEASES / version / 'skills' if version else ROOT / 'skills'
    path = directory / name / 'scripts' / 'skill.py'
    module_name = '_business_' + name.replace('-', '_') + '_' + (version or 'development')
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def function(capability, name, entry):
    return getattr(skill_module(name, capability.get('version') if capability else None), entry)


def configured_tools(capability, names=None):
    """Resolve trusted configured Python callables; LangChain handles schema and calls."""
    from langchain.tools import tool
    result, owners = [], {}
    for skill in capability['config']['skills']['skills']:
        if not skill.get('enabled', True) or (names is not None and skill['name'] not in names):
            continue
        for binding in skill.get('tools', []):
            module = skill_module(skill['name'], capability['version'])
            callable_ = getattr(module, binding['function'])
            native_tool = tool(binding.get('name') or callable_.__name__)(callable_)
            result.append(native_tool)
            owners[native_tool.name] = skill['name']
    return result, owners


def skill_files(capability, names=None):
    from deepagents.backends.utils import create_file_data
    directory = skill_root(capability)
    result = {}
    for path in directory.rglob('*'):
        relative = path.relative_to(directory)
        if names is not None and relative.parts[0] not in names:
            continue
        if path.is_file() and path.suffix in ('.md', '.json', '.yaml', '.py', '.txt'):
            result['/skills/' + relative.as_posix()] = create_file_data(path.read_text(encoding='utf-8'))
    return result


def skill_state(capability, task=None, names=None):
    """Official run-input state for SkillsMiddleware.

    Passing `files`, `pinned_skills` and `skills_metadata=None` on invoke is the
    documented way to seed StateBackend skills; no custom seeding middleware.
    """
    enabled = {s['name'] for s in capability['config']['skills']['skills'] if s.get('enabled', True)}
    pins = [n for n in (names if names is not None else ['billing-export']) if n in enabled]
    files = skill_files(capability, names)
    if task is not None and 'document-extraction' in enabled and (
            names is None or 'document-extraction' in names):
        module = skill_module('document-extraction', capability['version'])
        markdown = getattr(module, 'markdown_files', None)
        if markdown:
            if names is None:
                pins = [n for n in ['document-intake', 'document-extraction', 'billing-export']
                        if n in enabled]
            files.update(markdown(task))
    return {'files': files, 'skills_metadata': None, 'pinned_skills': pins}


def enabled_skill(name):
    return any(s['name'] == name and s.get('enabled', True) for s in read_config('skills')['skills'])
