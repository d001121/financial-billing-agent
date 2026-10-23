"""Skill version metadata must agree across config, manifest, and script constants."""
import ast
from pathlib import Path

import yaml

BACKEND = Path(__file__).resolve().parents[1]
SKILLS = BACKEND / 'skills'


def _manifest_version(name):
    text = (SKILLS / name / 'SKILL.md').read_text(encoding='utf-8')
    assert text.startswith('---\n'), f'{name}/SKILL.md missing frontmatter'
    _, header, _ = text.split('---', 2)
    return yaml.safe_load(header)['metadata']['version']


def _script_versions(name):
    path = SKILLS / name / 'scripts' / 'skill.py'
    if not path.is_file():
        return {}
    tree = ast.parse(path.read_text(encoding='utf-8'))
    versions = {}
    for node in tree.body:
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id in {'VERSION', 'POLICY_VERSION'}
                and isinstance(node.value, ast.Constant)):
            versions[node.targets[0].id] = node.value.value
    return versions


def test_skill_versions_match_config_manifest_and_script():
    from backend.config.transactions import read_config

    configured = {row['name']: row['version'] for row in read_config('skills')['skills']}
    for name, version in configured.items():
        assert _manifest_version(name) == version, f'{name}/SKILL.md'
        for constant, value in _script_versions(name).items():
            assert value == version, f'{name}/{constant}'
