"""Offline OBS host-boundary contracts; all files and credentials are synthetic.

Native tool/middleware evidence: Docs MCP middleware/custom.mdx wrap_tool_call
and Reference MCP AgentMiddleware, verified against LangChain 1.4.6. Network
clients and storage are replaced; native tool invocation and policy stay real.
"""

import asyncio
from hashlib import sha256
import json
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

import httpx
from PIL import Image
import pytest

# Standalone execution must not load real service credentials from the env file.
with patch('dotenv.load_dotenv', return_value=False):
    from backend.tools import skill_bindings
    from test_host import host  # noqa: F401 - registers the shared isolated fixture


class MemoryCache:
    def __init__(self):
        self.values = {}

    def get(self, key):
        return self.values.get(key)

    def setex(self, key, expires, value):
        self.values[key] = value


@pytest.fixture
def obs_host(host, monkeypatch, tmp_path):
    repo, _, task = host
    root = tmp_path / 'assets'
    path = root / 'synthetic-asset' / 'invoice.png'
    path.parent.mkdir(parents=True)
    Image.new('RGB', (30, 20), 'white').save(path)
    monkeypatch.setattr(skill_bindings, 'ASSETS', root)
    monkeypatch.setattr(skill_bindings, 'OCR_URL', 'https://ocr.example.test/process')
    repo.objects['asset', 'synthetic-asset'] = dict(
        id='synthetic-asset', name=path.name,
        relative_path='synthetic-asset/invoice.png',
        sha256=sha256(path.read_bytes()).hexdigest(),
    )
    repo.mutate('task', task['id'], lambda current: current.update(
        asset_ids=['synthetic-asset'], sources=[], intake=[], intake_issues=[]))
    env = dict(
        REDIS_URL='redis://synthetic.invalid:6379/0', OBS_ENABLE='true',
        OBS_ACCESS_KEY_ID='synthetic-access-key', OBS_SECRET_ACCESS_KEY='synthetic-secret-key',
        OBS_SERVER='https://obs.example.test', OBS_BUCKET='synthetic-bucket',
        OBS_SECURITY_TOKEN='synthetic-session-token', OBS_OBJECT_PREFIX='synthetic',
        OBS_SOCKET_TIMEOUT='60', DOC_CONVERTER='', OCR_RESPONSE_FORMAT='text',
    )
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    cache = MemoryCache()
    monkeypatch.setattr(skill_bindings.redis.Redis, 'from_url', lambda *args, **kwargs: cache)
    http = Mock(side_effect=AssertionError('unexpected OCR network dispatch'))
    monkeypatch.setattr(httpx, 'post', http)
    return repo, task, cache, http


def install_intake(monkeypatch, module):
    original = skill_bindings.skill_module
    monkeypatch.setattr(skill_bindings, 'skill_module',
        lambda name, version=None: module if name == 'document-intake' else original(name, version))


def tool_for(task, name):
    common, business = skill_bindings.tools_for(task['id'], task['capability'])
    return next(tool for tool in common + business if tool.name == name)


def result_for(text='Synthetic OCR text'):
    return dict(status='ready', issues=[], artifacts=[], sources=[dict(
        source_id='synthetic-source', name='invoice.png', status='ready', format='image',
        metadata={}, blocks=[dict(anchor='ocr/frame:1', text=text, authoritative=True)],
    )])


def test_intake_returns_a_manifest_without_the_material_body(obs_host, monkeypatch):
    repo, task, _, _ = obs_host
    marker = 'SYNTHETIC-BODY-MARKER'
    install_intake(monkeypatch, SimpleNamespace(OBSPublisher=object,
        intake_document=lambda path, **options: result_for(marker)))
    output = asyncio.run(tool_for(task, 'intake_documents').ainvoke({}))
    reading = output.get('reading') or {}
    assert reading.get('content_returned') is False
    assert 'read_materials' in reading.get('instruction', '')
    assert {m['source_id'] for m in reading.get('materials', [])} == {'synthetic-source'}
    assert marker not in json.dumps(output, ensure_ascii=False)


def test_new_skill_receives_host_credentials_without_exposing_them_to_task_or_model(obs_host, monkeypatch):
    repo, task, _, _ = obs_host
    received = []

    def intake_document(path, **options):
        options['request_guard']()
        received.append(options)
        return result_for()

    install_intake(monkeypatch, SimpleNamespace(OBSPublisher=object, intake_document=intake_document))
    intake = tool_for(task, 'intake_documents')
    output = asyncio.run(intake.ainvoke({}))
    options = received[0]['obs_options']
    assert options['enabled'] is True
    assert options['access_key_id'] == 'synthetic-access-key'
    assert options['secret_access_key'] == 'synthetic-secret-key'
    assert options['security_token'] == 'synthetic-session-token'
    assert received[0]['ocr_response_format'] == 'text'
    assert output['issues'] == []

    schema = set(intake.args_schema.model_fields)
    assert {'asset_ids', 'source_urls', 'ocr_text_pointer', 'include_content'} <= schema
    visible = json.dumps(dict(task=repo.get('task', task['id']), output=output, schema=sorted(schema),
                              context=tool_for(task, 'read_task_context').invoke({})), default=str)
    assert all(secret not in visible for secret in (
        'synthetic-access-key', 'synthetic-secret-key', 'synthetic-session-token'))


def test_pause_after_upload_blocks_ocr_but_preserves_successful_upload(obs_host, monkeypatch):
    repo, task, _, http = obs_host
    client = Mock()

    def upload(*args, **kwargs):
        repo.mutate('task', task['id'], lambda current: current.update(control='paused'))
        return SimpleNamespace(status=200, body=SimpleNamespace(etag='synthetic-etag'),
                               requestId='synthetic-upload', errorCode=None)

    client.putFile.side_effect = upload
    client.createSignedUrl.return_value = {'signedUrl': 'https://files.example/scan.png?synthetic=true'}
    sdk = ModuleType('obs')
    sdk.ObsClient = Mock(return_value=client)
    sdk.PutObjectHeader = lambda **kwargs: SimpleNamespace(**kwargs)
    monkeypatch.setitem(sys.modules, 'obs', sdk)
    output = asyncio.run(tool_for(task, 'intake_documents').ainvoke({}))

    client.putFile.assert_called_once()
    http.assert_not_called()
    client.close.assert_called_once()
    saved = repo.get('task', task['id'])
    assert saved['control'] == 'paused'
    assert output['issues']
    assert saved['sources'][0]['status'] != 'ready'
    receipt = saved['sources'][0]['metadata']['obs_objects'][0]
    assert receipt['status'] == 200 and receipt['request_id'] == 'synthetic-upload'


def test_snapshot_without_obs_publisher_keeps_legacy_call_compatible(obs_host, monkeypatch):
    repo, task, _, _ = obs_host
    called = []

    def legacy_intake(path, *, source_url, output_dir, ocr_endpoint, url_resolver,
                      ocr_text_pointer, occurrence_id, pdf_pages_per_slice, doc_converter):
        called.append(path)
        return result_for('Synthetic legacy result')

    install_intake(monkeypatch, SimpleNamespace(intake_document=legacy_intake))
    output = asyncio.run(tool_for(task, 'intake_documents').ainvoke({}))
    assert len(called) == 1
    assert output['issues'] == []
    assert repo.get('task', task['id'])['sources'][0]['blocks'][0]['text'] == 'Synthetic legacy result'


def test_changing_ocr_pointer_reparses_instead_of_reusing_cached_result(obs_host, monkeypatch):
    repo, task, _, _ = obs_host
    parsed_pointers = []

    def intake_document(path, **options):
        pointer = options['ocr_text_pointer']
        parsed_pointers.append(pointer)
        return result_for('Synthetic text selected by ' + pointer)

    install_intake(monkeypatch, SimpleNamespace(OBSPublisher=object, intake_document=intake_document))
    intake = tool_for(task, 'intake_documents')
    asyncio.run(intake.ainvoke({'ocr_text_pointer': '/data/text'}))
    asyncio.run(intake.ainvoke({'ocr_text_pointer': '/data/text'}))
    assert parsed_pointers == ['/data/text']
    asyncio.run(intake.ainvoke({'ocr_text_pointer': '/result/text'}))
    assert parsed_pointers == ['/data/text', '/result/text']
    saved = repo.get('task', task['id'])
    assert saved['ocr_text_pointer'] == '/result/text'
    assert saved['sources'][0]['blocks'][0]['text'] == 'Synthetic text selected by /result/text'


def test_changing_ocr_response_format_invalidates_cached_parser_result(obs_host, monkeypatch):
    repo, task, _, _ = obs_host
    parsed_formats = []

    def intake_document(path, **options):
        response_format = options['ocr_response_format']
        parsed_formats.append(response_format)
        return result_for('Synthetic parser format ' + response_format)

    install_intake(monkeypatch, SimpleNamespace(OBSPublisher=object, intake_document=intake_document))
    intake = tool_for(task, 'intake_documents')
    asyncio.run(intake.ainvoke({}))
    asyncio.run(intake.ainvoke({}))
    assert parsed_formats == ['text']
    monkeypatch.setenv('OCR_RESPONSE_FORMAT', 'orderChange')
    asyncio.run(intake.ainvoke({}))
    assert parsed_formats == ['text', 'orderChange']
    assert repo.get('task', task['id'])['sources'][0]['blocks'][0]['text'] == 'Synthetic parser format orderChange'
