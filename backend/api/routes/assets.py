"""Material uploads, sample browsing, and original-file downloads."""
import asyncio
from copy import deepcopy
from hashlib import sha256
import mimetypes
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
import httpx

from backend.config import settings
from backend.infrastructure.assets import asset_file
from backend.infrastructure.repository import loads, repository
from backend.extensions.skill_versions import enabled_skill, function
from backend.harness.dispatch import PolicyDenied

from ..responses import response

router = APIRouter(tags=['assets'])


def display_source(source):
    """Attach a presentation-only Office PDF without mutating the task snapshot."""
    result = deepcopy(source)
    if str(source.get('format', '')).lower() in ('xls', 'xlsx', 'doc', 'docx'):
        preview = source.get('metadata', {}).get('office_preview') or {}
        if not preview.get('sha256'):
            if not enabled_skill('document-intake'):
                raise PolicyDenied('Skill已禁用: document-intake；不能生成新的Office预览')
            preview = function(None, 'document-intake', 'render_office_preview')(dict(
                path=str(asset_file(source)), output_dir=str(settings.ASSETS / '_source_previews'),
                doc_converter=settings.office_converter()))
            result.setdefault('metadata', {})['office_preview'] = preview
    return result


@router.get('/api/samples')
def samples():
    return response([dict(id=str(i), name=p.name, sample_path=p.relative_to(settings.SAMPLES).as_posix(),
                         path=p.relative_to(settings.SAMPLES).as_posix(), size=p.stat().st_size,
                         media_type=mimetypes.guess_type(p.name)[0] or 'application/octet-stream')
                     for i, p in enumerate(sorted(settings.SAMPLES.rglob('*'))) if p.is_file()])


def store_asset(name, content, source_url=None):
    asset_id = str(uuid4())
    filename = Path(name).name
    directory = settings.ASSETS / asset_id
    directory.mkdir()
    target = directory / filename
    target.write_bytes(content)
    return repository().create('asset', dict(id=asset_id, name=filename, size=len(content),
        sha256=sha256(content).hexdigest(), relative_path=target.relative_to(settings.ASSETS).as_posix(),
        media_type=mimetypes.guess_type(filename)[0] or 'application/octet-stream', source_url=source_url,
        content_url=f'/api/assets/{asset_id}/content'))


@router.post('/api/assets')
async def add_asset(request: Request):
    content_type = request.headers.get('content-type', '')
    if 'multipart/form-data' in content_type:
        form = await request.form()
        file = form.get('file')
        if not file or not hasattr(file, 'read'):
            raise ValueError('请提供file文件')
        content = await file.read(100 * 1024 * 1024 + 1)
        if len(content) > 100 * 1024 * 1024:
            raise ValueError('单个材料超过100MB')
        return response(await asyncio.to_thread(store_asset, file.filename, content, form.get('source_url')), 201)
    body = loads(await request.body())
    if body.get('sample_path'):
        target = (settings.SAMPLES / body['sample_path']).resolve()
        if not target.is_relative_to(settings.SAMPLES.resolve()) or not target.is_file():
            raise ValueError('样本路径不在材料目录中')
        return response(await asyncio.to_thread(store_asset, target.name, target.read_bytes(), body.get('source_url')), 201)
    if body.get('url'):
        url = httpx.URL(body['url'])
        if url.scheme not in ('http', 'https'):
            raise ValueError('仅接受HTTP(S)下载地址')
        async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
            async with client.stream('GET', url) as fetched:
                fetched.raise_for_status()
                chunks, size = [], 0
                async for chunk in fetched.aiter_bytes():
                    size += len(chunk)
                    if size > 100 * 1024 * 1024:
                        raise ValueError('远程文件超过100MB')
                    chunks.append(chunk)
        return response(await asyncio.to_thread(store_asset, body.get('name') or Path(url.path).name or 'document.pdf',
                                               b''.join(chunks), str(url)), 201)
    raise ValueError('提供file、sample_path或url')


@router.get('/api/assets')
def list_assets():
    return response(repository().list('asset'))


@router.get('/api/assets/{asset_id}/content')
def asset_content(asset_id: str):
    asset = repository().get('asset', asset_id)
    return FileResponse(settings.ASSETS / asset['relative_path'], media_type=asset['media_type'])


@router.get('/api/tasks/{task_id}/sources/{source_id}/content')
def source_content(task_id: str, source_id: str):
    task = repository().get('task', task_id)
    source = next((s for s in task.get('sources', []) if s['source_id'] == source_id), None)
    if not source:
        raise KeyError(source_id)
    path = asset_file(source)
    if not path.is_file():
        raise HTTPException(status_code=404, detail='原件文件缺失，请核对交付包中的backend/data/assets')
    return FileResponse(path)


@router.get('/api/tasks/{task_id}/sources/{source_id}/preview')
def source_preview(task_id: str, source_id: str, anchor: str | None = None,
                   quote: str | None = None, field: str | None = None, value: str | None = None,
                   charge_id: str | None = None):
    if not enabled_skill('evidence-linking'):
        raise PolicyDenied('Skill已禁用: evidence-linking；仍可直接下载已保留的原件')
    task = repository().get('task', task_id)
    source = next((s for s in task.get('sources', []) if s['source_id'] == source_id), None)
    if not source:
        raise KeyError(source_id)
    content_url = f'/api/tasks/{task_id}/sources/{source_id}/content'
    render_error = None
    try:
        source = display_source(source)
    except (ValueError, OSError, RuntimeError) as exc:
        render_error = f'原件预览生成失败: {type(exc).__name__}: {exc}'
    preview_file = source.get('metadata', {}).get('office_preview') or {}
    try:
        original_path = asset_file(preview_file if preview_file.get('sha256') else source)
    except KeyError:
        # Text-only sources (for example an EML body block without a stored
        # asset file) still get a block preview; there is no original file to
        # locate.
        original_path = None
    # A new renderer may be used for old source artifacts without changing the
    # pinned evidence/financial rules. Its version is explicit in the response.
    result = function(None, 'evidence-linking', 'build_preview')(dict(source=source,
        records=task.get('records', []), charges=task.get('charges', []), revision=task['revision'],
        target=dict(anchor=anchor, quote=quote, field=field, value=value, charge_id=charge_id),
        original_path=str(original_path) if original_path else None,
        location_cache_dir=str(settings.ASSETS / '_location_cache')))
    if render_error:
        result['original'] = dict(status='error', locations=[], reason=render_error)
    if result.get('render'):
        result['render']['content_url'] = f'/api/tasks/{task_id}/sources/{source_id}/preview/content'
    return response(dict(result, content_url=content_url, original_url=content_url,
                         capability_version=task['capability']['version']))


@router.get('/api/tasks/{task_id}/sources/{source_id}/preview/content')
def rendered_source_content(task_id: str, source_id: str):
    task = repository().get('task', task_id)
    source = next((s for s in task.get('sources', []) if s['source_id'] == source_id), None)
    if not source:
        raise KeyError(source_id)
    if not enabled_skill('evidence-linking'):
        raise PolicyDenied('Skill已禁用: evidence-linking')
    preview = display_source(source).get('metadata', {}).get('office_preview') or {}
    if preview.get('format') != 'pdf' or not preview.get('sha256'):
        raise HTTPException(status_code=404, detail='该材料尚无可用的Office渲染预览')
    path = asset_file(preview)
    if not path.is_file():
        raise HTTPException(status_code=404, detail='Office渲染文件缺失，可查看结构视图或下载原件')
    if sha256(path.read_bytes()).hexdigest() != preview['sha256']:
        raise HTTPException(status_code=409, detail='Office渲染版本已变化，不能沿用原定位')
    return FileResponse(path, media_type='application/pdf')
