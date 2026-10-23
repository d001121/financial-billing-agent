"""Native configuration checks and real file transactions; no Agent/model/network.

Official MCP/Skill/tool evidence and pinned versions are recorded in
backend.config.validation. Only application file/reference policy is custom.
"""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from decimal import Decimal
import json
from pathlib import Path
import shutil
import subprocess
import sys
import threading
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
import yaml

from backend.api import app
from backend.config import transactions
from backend.config.validation import validate_configuration
from backend.extensions import snapshots
from backend.infrastructure.repository import Conflict

PROJECT = Path(__file__).resolve().parents[1]


@pytest.fixture
def config_root(tmp_path, monkeypatch):
    shutil.copytree(PROJECT / 'config', tmp_path / 'config',
                    ignore=shutil.ignore_patterns('.write.lock', '*.tmp'))
    shutil.copytree(PROJECT / 'skills', tmp_path / 'skills', ignore=shutil.ignore_patterns('__pycache__', '.*'))
    shutil.copytree(PROJECT / 'agents', tmp_path / 'agents', ignore=shutil.ignore_patterns('__pycache__'))
    monkeypatch.setattr(transactions, 'ROOT', tmp_path)
    monkeypatch.setattr(snapshots, 'ROOT', tmp_path)
    return tmp_path


def read_all():
    return {kind: transactions.read_config(kind) for kind in transactions.KINDS}


def test_current_configs_native_discovery_and_valid_save(config_root):
    config = read_all()
    validate_configuration(config, config_root)
    original = deepcopy(config['runtime'])
    proposed = dict(original, model_timeout=Decimal('12.5'))
    saved = transactions.write_config('runtime', proposed, original['version'])
    assert saved['version'] == original['version'] + 1
    assert saved['model_timeout'] == 12.5
    assert transactions.read_config('runtime') == saved
    assert proposed['version'] == original['version']


def test_experience_usage_switch_persists_without_changing_other_runtime_options(config_root):
    original = transactions.read_config('runtime')
    saved = transactions.write_config('runtime', dict(original, use_reviewed_experiences=False), original['version'])
    assert transactions.read_config('runtime')['use_reviewed_experiences'] is False
    assert {k: v for k, v in saved.items() if k not in ('version', 'use_reviewed_experiences')} == {
        k: v for k, v in original.items() if k not in ('version', 'use_reviewed_experiences')}
    with pytest.raises(ValueError):
        transactions.write_config('runtime', dict(saved, use_reviewed_experiences='false'), saved['version'])
    with pytest.raises(Conflict):
        transactions.write_config('runtime', original, original['version'])


def test_role_prompt_files_are_resolved_and_frozen_in_task_snapshot(config_root, monkeypatch):
    monkeypatch.setattr(snapshots, 'RELEASES', config_root / 'releases')
    monkeypatch.setattr(snapshots, 'repository', lambda: SimpleNamespace(get=lambda *a, **k: None, list=lambda *a, **k: []))
    config_path = config_root / 'config' / 'agents.yaml'
    raw = yaml.safe_load(config_path.read_text(encoding='utf-8'))
    # Exercise a file-backed configuration explicitly; production may validly
    # contain inline prompts saved through the configuration API.
    for agent in raw['agents']:
        agent.pop('prompt', None)
        agent['prompt_file'] = f"agents/{'document' if agent['type'] == 'deep-agent' else 'billing'}/prompt.md"
    config_path.write_text(yaml.safe_dump(raw, allow_unicode=True), encoding='utf-8')
    prompt_path = config_root / 'agents' / 'document' / 'prompt.md'
    original = prompt_path.read_text(encoding='utf-8').strip()
    config = transactions.read_config('agents')
    role = next(agent for agent in config['agents'] if agent['type'] == 'deep-agent')
    assert role['prompt'] == original and 'prompt_file' not in role
    frozen = snapshots.snapshot()
    prompt_path.write_text(original + '\n新增文档提取提示。', encoding='utf-8')
    refreshed = snapshots.snapshot()
    assert refreshed['version'] != frozen['version']
    frozen_role = next(agent for agent in frozen['config']['agents']['agents'] if agent['name'] == role['name'])
    current_role = next(agent for agent in refreshed['config']['agents']['agents'] if agent['name'] == role['name'])
    assert frozen_role['prompt'] == original
    assert current_role['prompt'] == original + '\n新增文档提取提示。'


@pytest.mark.parametrize(('change', 'error'), [
    (lambda value: None, '配置必须是对象'),
    (lambda value: [], '配置必须是对象'),
    (lambda value: dict(value, agents=None), 'agents必须是Agent配置对象列表'),
    (lambda value: dict(value, agents={}), 'agents必须是Agent配置对象列表'),
    (lambda value: dict(value, agents=[1]), 'agents必须是Agent配置对象列表'),
    (lambda value: {key: item for key, item in value.items() if key != 'agents'}, 'Field required'),
    (lambda value: dict(value, agents=[dict(value['agents'][0], prompt_file='agents/document/prompt.md')]), '只能提供一个'),
    (lambda value: dict(value, agents=[{key: item for key, item in dict(value['agents'][0],
        prompt_file='../outside.md').items() if key != 'prompt'}]), 'agents目录内的文件'),
    (lambda value: dict(value, agents=[{key: item for key, item in dict(value['agents'][0],
        prompt_file=str(PROJECT / 'agents' / 'document' / 'prompt.md')).items() if key != 'prompt'}]), '相对路径'),
])
def test_invalid_agent_prompt_configuration_is_value_error_and_http_422(config_root, change, error):
    config = read_all()
    previous = (config_root / 'config' / 'agents.yaml').read_bytes()
    version = config['agents']['version']
    proposed = change(deepcopy(config['agents']))
    with pytest.raises(ValueError, match=error):
        validate_configuration(dict(config, agents=proposed), config_root)
    with pytest.raises(ValueError, match=error):
        transactions.write_config('agents', proposed, version)
    result = TestClient(app).put('/api/config/agents', json={'config': proposed, 'expected_version': version})
    assert result.status_code == 422
    assert result.json()['error'] == 'INVALID_INPUT'
    assert (config_root / 'config' / 'agents.yaml').read_bytes() == previous
    assert not list((config_root / 'config').glob('*.tmp'))


def test_role_prompt_file_can_be_saved_through_extension_api(config_root):
    path = config_root / 'config' / 'agents.yaml'
    proposed = yaml.safe_load(path.read_text(encoding='utf-8'))
    for agent in proposed['agents']:
        agent.pop('prompt', None)
        agent['prompt_file'] = f"agents/{'document' if agent['type'] == 'deep-agent' else 'billing'}/prompt.md"
    expected_version = proposed['version']
    result = TestClient(app).put('/api/config/agents', json={
        'config': proposed, 'expected_version': expected_version})
    assert result.status_code == 200, result.text
    saved = result.json()
    assert saved['version'] == expected_version + 1
    for raw, resolved in zip(proposed['agents'], saved['agents'], strict=True):
        assert resolved['name'] == raw['name']
        assert resolved['prompt'] == (config_root / raw['prompt_file']).read_text(encoding='utf-8').strip()
        assert 'prompt_file' not in resolved
    assert transactions.read_config('agents') == saved


@pytest.mark.parametrize('kind,mutate', [
    ('agents', lambda c: c['agents'].append(deepcopy(c['agents'][0]))),
    ('agents', lambda c: c['agents'][0].update(type='custom-loop')),
    ('agents', lambda c: c['agents'][0].update(skills=['missing-skill'])),
    ('agents', lambda c: c['agents'][0].update(enabled='false')),
    ('skills', lambda c: c['skills'].append(deepcopy(c['skills'][0]))),
    ('skills', lambda c: c['skills'][0].update(name='../outside')),
    ('skills', lambda c: c['skills'][0].update(tools=[{'function': 'missing_function'}])),
    ('mcp', lambda c: c['servers'].append({'id': 'bad', 'url': 'file:///tmp/mcp.py'})),
    ('mcp', lambda c: c['servers'].extend([{'id': 'same', 'url': 'http://localhost/mcp'}] * 2)),
    ('mcp', lambda c: c['servers'].append({'id': 'bad', 'transport': {'args': []}})),
    ('mcp', lambda c: c['servers'].append({'id': 'bad', 'url': 'https://example.org', 'transport': {'command': 'python'}})),
    ('mcp', lambda c: c['servers'].append({'id': 'bad', 'transport': {'command': 'python', 'timeout': float('nan')}})),
    ('hooks', lambda c: c['hooks'].pop()),
    ('hooks', lambda c: c['hooks'][0].update(function='does_not_exist')),
    ('hooks', lambda c: c['hooks'][-1].update(native='unknown-native')),
    ('runtime', lambda c: c.update(document_concurrency=0)),
    ('runtime', lambda c: c.update(model_calls=True)),
    ('runtime', lambda c: c.update(model_timeout=float('inf'))),
    ('runtime', lambda c: c.update(active_seconds=float('nan'))),
    ('runtime', lambda c: c.update(repair_rounds=-1)),
    ('runtime', lambda c: c.update(ignored_option='ignored')),
])
def test_invalid_changes_preserve_previous_config(config_root, kind, mutate):
    path = config_root / 'config' / f'{kind}.yaml'
    previous = path.read_bytes()
    proposed = transactions.read_config(kind)
    mutate(proposed)
    with pytest.raises(ValueError):
        transactions.write_config(kind, proposed, proposed['version'])
    assert path.read_bytes() == previous
    assert not list(path.parent.glob('*.tmp'))


def test_skill_missing_files_and_native_frontmatter_rejected(config_root):
    proposed = transactions.read_config('skills')
    package = config_root / 'skills' / 'document-intake'
    source = package / 'SKILL.md'
    source.write_text('Not a Skill frontmatter', encoding='utf-8')
    with pytest.raises(ValueError, match='原生发现'):
        transactions.write_config('skills', proposed, proposed['version'])
    source.unlink()
    with pytest.raises(ValueError, match='SKILL.md'):
        transactions.write_config('skills', proposed, proposed['version'])


def test_valid_new_skill_tool_and_native_mcp_config(config_root):
    directory = config_root / 'skills' / 'extension-demo'
    (directory / 'references').mkdir(parents=True)
    (directory / 'scripts').mkdir()
    (directory / 'SKILL.md').write_text('---\nname: extension-demo\ndescription: Demo extension\nmetadata:\n  include_tools: example_extension\n---\nUse the extension.', encoding='utf-8')
    (directory / 'scripts' / 'skill.py').write_text('def example_extension(value: str) -> dict:\n    """Return the supplied value."""\n    return {"value": value}\n', encoding='utf-8')
    skill_config = transactions.read_config('skills')
    skill_config['skills'].append(dict(name='extension-demo', version='1.0.0', enabled=True,
                                      tools=[{'function': 'example_extension'}]))
    saved = transactions.write_config('skills', skill_config, skill_config['version'])
    assert saved['skills'][-1]['name'] == 'extension-demo'
    mcp_config = transactions.read_config('mcp')
    mcp_config['servers'] = [dict(id='local-probe', enabled=False,
        transport={'command': sys.executable, 'args': ['server.py'], 'env': {'DEMO': '1'}}),
        dict(id='remote-probe', enabled=False, url='https://example.org/mcp')]
    assert len(transactions.write_config('mcp', mcp_config, mcp_config['version'])['servers']) == 2
    # Schema validation did not start either MCP server or invoke the extension.
    skill_config = transactions.read_config('skills')
    skill_config['skills'][-1]['tools'][0]['name'] = 'read_task_context'
    with pytest.raises(ValueError, match='名称冲突'):
        transactions.write_config('skills', skill_config, skill_config['version'])


def test_stale_or_unversioned_edits_cannot_overwrite(config_root):
    original = transactions.read_config('runtime')
    saved = transactions.write_config('runtime', original, original['version'])
    with pytest.raises(Conflict):
        transactions.write_config('runtime', original)
    with pytest.raises(Conflict):
        transactions.write_config('runtime', {k: v for k, v in saved.items() if k != 'version'})
    assert transactions.read_config('runtime') == saved


def test_replace_failure_keeps_valid_file_and_removes_temporary(config_root, monkeypatch):
    path = config_root / 'config' / 'runtime.yaml'
    previous = path.read_bytes()
    proposed = transactions.read_config('runtime')
    def fail_replace(*args):
        raise OSError('simulated filesystem failure')
    monkeypatch.setattr(transactions.os, 'replace', fail_replace)
    with pytest.raises(OSError, match='simulated'):
        transactions.write_config('runtime', proposed, proposed['version'])
    assert path.read_bytes() == previous
    assert not list(path.parent.glob('*.tmp'))


def test_threads_serialize_compare_and_replace(config_root):
    original = transactions.read_config('runtime')
    barrier = threading.Barrier(2)
    def write(token):
        barrier.wait()
        try:
            return transactions.write_config('runtime', dict(original, max_tokens=token), original['version'])
        except Conflict:
            return 'conflict'
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(write, [111, 222]))
    assert results.count('conflict') == 1
    assert transactions.read_config('runtime')['version'] == original['version'] + 1


def test_independent_processes_share_the_same_version_lock(config_root):
    original = transactions.read_config('runtime')
    code = '''
import json,sys
from pathlib import Path
from backend.config import transactions
from backend.infrastructure.repository import Conflict
transactions.ROOT=Path(sys.argv[1])
proposed=json.loads(sys.argv[2])
try:
    transactions.write_config('runtime',proposed,proposed['version'])
    print('saved')
except Conflict:
    print('conflict')
'''
    commands = [[sys.executable, '-B', '-c', code, str(config_root), json.dumps(dict(original, max_tokens=value))]
                for value in (333, 444)]
    processes = [subprocess.Popen(command, cwd=PROJECT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                 for command in commands]
    outcomes = [process.communicate(timeout=45) for process in processes]
    assert [process.returncode for process in processes] == [0, 0], outcomes
    assert sorted(output.strip() for output, _ in outcomes) == ['conflict', 'saved']
    assert transactions.read_config('runtime')['version'] == original['version'] + 1


def test_concurrent_snapshot_publish_never_exposes_partial_release(config_root, monkeypatch):
    releases = config_root / 'releases'
    monkeypatch.setattr(snapshots, 'RELEASES', releases)
    monkeypatch.setattr(snapshots, 'repository', lambda: SimpleNamespace(get=lambda *a, **k: None, list=lambda *a, **k: []))
    original_write = Path.write_bytes
    both_staging, continue_write = threading.Event(), threading.Event()
    entered, entry_lock = set(), threading.Lock()

    def slow_first_write(path, content):
        result = original_write(path, content)
        stage = next((p for p in path.parents if p.name.startswith('.snapshot-')), None)
        should_wait = False
        if stage:
            with entry_lock:
                if stage not in entered:
                    entered.add(stage)
                    should_wait = True
                    if len(entered) == 2:
                        both_staging.set()
            if should_wait:
                assert continue_write.wait(timeout=10)
        return result

    monkeypatch.setattr(Path, 'write_bytes', slow_first_write)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(snapshots.snapshot) for _ in range(2)]
        try:
            assert both_staging.wait(timeout=10)
            assert len(list(releases.glob('.snapshot-*'))) == 2
            assert not [p for p in releases.iterdir() if not p.name.startswith('.')]
        finally:
            continue_write.set()
        results = [future.result(timeout=10) for future in futures]
    assert results[0] == results[1]
    version = results[0]['version']
    published = releases / version / 'skills'
    expected = {p.relative_to(config_root / 'skills').as_posix(): p.read_bytes()
                for p in (config_root / 'skills').rglob('*') if p.is_file()}
    actual = {p.relative_to(published).as_posix(): p.read_bytes() for p in published.rglob('*') if p.is_file()}
    assert actual == expected
    assert not list(releases.glob('.snapshot-*'))
    unchanged = {p: p.stat().st_mtime_ns for p in published.rglob('*') if p.is_file()}
    assert snapshots.snapshot() == results[0]
    assert unchanged == {p: p.stat().st_mtime_ns for p in published.rglob('*') if p.is_file()}
