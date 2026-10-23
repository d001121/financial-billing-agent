"""Raw OCR reuse must preserve each upload's identity and exclude failed responses."""
import importlib.util
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event, Lock

import httpx
from PIL import Image

spec = importlib.util.spec_from_file_location('intake_cache_test', Path(__file__).parents[1] / 'scripts/skill.py')
skill = importlib.util.module_from_spec(spec)
spec.loader.exec_module(skill)


def options(tmp_path, request):
    return dict(ocr_cache_dir=tmp_path/'cache', ocr_request=request,
        ocr_response_format='orderChange', source_url='https://files.test/a.pdf')


def original(tmp_path):
    path = tmp_path/'bill.png'
    Image.new('RGB', (10, 10), 'white').save(path)
    return path


def response():
    return httpx.Response(200, json={'success': True, 'data': {'list': [
        {'chargeList': [{'amount': '245', 'currency': 'USD'}]}]}},
        request=httpx.Request('POST', 'https://ocr.test'))


def test_same_bytes_new_upload_reuses_wire_and_rebinds_source(tmp_path):
    calls, events = [], []
    def request(**kwargs):
        calls.append(kwargs)
        return response()
    path = original(tmp_path)
    first = skill.intake_document(path, output_dir=tmp_path/'one', occurrence_id='upload-one',
        on_progress=events.append, **options(tmp_path, request))
    second = skill.intake_document(path, output_dir=tmp_path/'two', occurrence_id='upload-two',
        on_progress=events.append, **options(tmp_path, request))
    assert first['status'] == second['status'] == 'ready'
    assert len(calls) == 1
    a, b = first['sources'][0], second['sources'][0]
    assert a['source_id'] != b['source_id'] and b['occurrence_id'] == 'upload-two'
    assert all(block['source_id'] == b['source_id'] for block in b['blocks'])
    assert Path(b['blocks'][0]['raw_response']).is_relative_to(tmp_path/'two')
    assert b['metadata']['ocr_requests'][0]['cache_hit'] is True
    assert b['metadata']['ocr_requests'][0]['http_seconds'] == 0
    assert any(e['stage'] == 'cache_hit' for e in events)


def test_concurrent_same_file_has_one_network_call(tmp_path):
    started, release, lock, calls = Event(), Event(), Lock(), []
    def request(**kwargs):
        with lock: calls.append(1)
        started.set()
        assert release.wait(3)
        return response()
    path = original(tmp_path)
    with ThreadPoolExecutor(max_workers=2) as pool:
        one = pool.submit(skill.intake_document, path, output_dir=tmp_path/'one', **options(tmp_path, request))
        assert started.wait(3)
        two = pool.submit(skill.intake_document, path, output_dir=tmp_path/'two', **options(tmp_path, request))
        release.set()
        assert one.result()['status'] == two.result()['status'] == 'ready'
    assert len(calls) == 1


def test_failed_response_is_not_cached_and_endpoint_change_invalidates(tmp_path):
    calls = []
    def request(**kwargs):
        calls.append(kwargs['endpoint'])
        return {'success': False} if len(calls) == 1 else response()
    path = original(tmp_path)
    assert skill.intake_document(path, output_dir=tmp_path/'bad', **options(tmp_path, request))['status'] != 'ready'
    assert skill.intake_document(path, output_dir=tmp_path/'good', **options(tmp_path, request))['status'] == 'ready'
    assert skill.intake_document(path, output_dir=tmp_path/'changed', ocr_endpoint='https://other.test',
        **options(tmp_path, request))['status'] == 'ready'
    assert len(calls) == 3


def test_cache_hit_never_resolves_or_uploads_a_download_url(tmp_path):
    path = original(tmp_path)
    skill.intake_document(path, output_dir=tmp_path/'one', **options(tmp_path, lambda **kw: response()))
    def forbidden(*args, **kwargs):
        raise AssertionError('cache hit must not request a new signed URL or OCR')
    result = skill.intake_document(path, output_dir=tmp_path/'two', url_resolver=forbidden,
        ocr_cache_dir=tmp_path/'cache', ocr_response_format='orderChange', ocr_request=forbidden)
    assert result['status'] == 'ready'


def test_expired_corrupt_receipt_and_service_version_are_misses(tmp_path, monkeypatch):
    cache = skill._cache.OCRResponseCache(tmp_path/'cache', ttl=20)
    key = cache.key('bytes', 'https://ocr.test')
    wire = response().content
    monkeypatch.setattr(skill._cache.time, 'time', lambda: 100)
    cache.write(key, wire)
    assert cache.read(key)[0] == wire
    assert cache.read(cache.key('bytes', 'https://ocr.test', 'new-version')) is None
    monkeypatch.setattr(skill._cache.time, 'time', lambda: 121)
    assert cache.read(key) is None
    monkeypatch.setattr(skill._cache.time, 'time', lambda: 100)
    (cache.directory/(key+'.json')).write_text('{broken', encoding='utf-8')
    assert cache.read(key) is None


def test_cache_write_failure_keeps_successful_task_receipt(tmp_path, monkeypatch):
    def fail(*args):
        raise OSError('synthetic cache disk unavailable')
    monkeypatch.setattr(skill._cache.OCRResponseCache, 'write', fail)
    result = skill.intake_document(original(tmp_path), output_dir=tmp_path/'one',
        **options(tmp_path, lambda **kwargs: response()))
    assert result['status'] == 'ready'
    source = result['sources'][0]
    assert 'OSError' in source['metadata']['ocr_requests'][0]['cache_error']
    assert Path(source['blocks'][0]['raw_response']).is_file()
