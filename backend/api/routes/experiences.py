"""Storage/model bindings for reviewed advice; domain behavior stays in the Skill."""
from hashlib import sha256
from uuid import uuid4

from fastapi import APIRouter, Request
from langsmith import tracing_context
from psycopg.errors import UniqueViolation

from backend.extensions.skill_versions import function, skill_module
from backend.infrastructure.models import make_model
from backend.infrastructure.repository import Conflict, dumps, loads, now, repository
from ..responses import response
from .improvements import require_enabled

router = APIRouter(prefix='/api/improvements/experiences', tags=['experiences'])


def source_task(task_id):
    task = repository().get('task', task_id)
    if task.get('deleted_at'):
        raise ValueError('来源账单已删除，请选择可查看的真实账单')
    return task


def operator(request):
    # The local workspace has no authenticated identity provider.
    return dict(kind='local_workspace', identity=None)


@router.get('')
def list_experiences():
    repo = repository()
    return response(dict(experiences=repo.list('experience', limit=10000),
                         references=repo.list('experience_use', limit=10000)))


@router.post('/summarize')
async def summarize(request: Request):
    require_enabled()
    body = loads(await request.body())
    task = source_task(body['task_id'])
    if task['revision'] != body.get('expected_revision'):
        raise Conflict('来源账单已更新，请刷新后重新总结')
    note = body.get('note') or ''
    if not isinstance(note, str) or len(note) > 2000:
        raise ValueError('补充说明最多2000字')
    module = skill_module('feedback-improvement')
    context = module.summary_context(task, note)
    if not (context['corrections'] or context['source_refs'] or context['note']):
        raise ValueError('当前没有纠错记录或可引用材料，请先核对账单，或补充一句希望总结的内容')
    digest = sha256(dumps(dict(context=context, prompt=module.EXPERIENCE_PROMPT)).encode()).hexdigest()
    repo = repository()
    job_id = 'summary-' + digest[:24]
    job = repo.get('experience_summary', job_id, required=False)
    if job is None:
        try:
            job = repo.create('experience_summary', dict(id=job_id, status='pending', usage={'model_calls': 0}))
        except UniqueViolation:
            job = repo.get('experience_summary', job_id)
    if job['status'] == 'success':
        return response(dict(experience=repo.get('experience', job['experience_id']), reused=True))
    if job['status'] == 'running':
        raise Conflict('这次总结正在进行，请稍后刷新，重复点击不会新增模型调用')
    if job['status'] == 'error' and body.get('retry_failed') is not True:
        return response(dict(message='上次总结失败；点击明确重试后才会再次调用模型', retry_available=True), 422)

    def start(current):
        if current['status'] not in {'pending', 'error'}:
            raise Conflict('总结状态已变化，请刷新')
        current.update(status='running', attempt_calls=0, started_at=now(), revision=current['revision'] + 1)
    job = repo.mutate('experience_summary', job_id, start, expected_revision=job['revision'])

    def guard():
        def count(current):
            require_enabled()
            if current['status'] != 'running' or current.get('attempt_calls', 0) >= 1:
                raise ValueError('本次经验总结已达到1次模型调用上限')
            current['attempt_calls'] = current.get('attempt_calls', 0) + 1
            current.setdefault('usage', {})['model_calls'] = current['usage'].get('model_calls', 0) + 1
        repo.mutate('experience_summary', job_id, count)

    model_client = None
    try:
        model, model_client = make_model(runtime=dict(model_timeout=45, max_tokens=1600), request_guard=guard)
        # Native schema parsing only; no additional agent loop, OCR or auto retry.
        with tracing_context(enabled=False, parent=False):
            result = await model.with_structured_output(module.ExperienceDraft,
                method='function_calling', include_raw=True).ainvoke([
                    dict(role='system', content=module.EXPERIENCE_PROMPT),
                    dict(role='user', content=dumps(context))])
        raw = result.get('raw')
        usage = getattr(raw, 'usage_metadata', None) or {}
        repo.mutate('experience_summary', job_id, lambda current: current['usage'].update(usage))
        if result.get('parsing_error') or result.get('parsed') is None:
            raise ValueError('模型没有返回完整经验卡片')
        parsed = module.ExperienceDraft.model_validate(result['parsed'])
        current_task = source_task(task['id'])
        if current_task['revision'] != task['revision']:
            raise Conflict('总结期间账单已修改，请依据最新版本重新总结')
        card = dict(id='experience-' + uuid4().hex[:24], **parsed.model_dump(),
            status='draft', accounting_entity=task.get('accounting_entity'),
            source=dict(task_id=task['id'], revision=task['revision'], title=task.get('title'),
                capability_version=(task.get('capability') or {}).get('version'),
                artifact_digest=digest), source_refs=context['source_refs'],
            summary_id=job_id, created_by=operator(request), review=None)
        checked = module.validate_experience(card)
        if not checked['valid']:
            raise ValueError('模型返回的经验内容不完整')
        card = repo.create('experience', card)
        repo.mutate('experience_summary', job_id, lambda current: current.update(
            status='success', experience_id=card['id'], completed_at=now()))
        return response(dict(experience=card, reused=False), 201)
    except Exception as exc:
        repo.mutate('experience_summary', job_id, lambda current: current.update(
            status='error', error_type=type(exc).__name__, completed_at=now()))
        if isinstance(exc, Conflict):
            raise
        # Keep request URLs, API details and credentials out of client diagnostics.
        return response(dict(message='AI总结未完成，未创建经验；可以明确重试。', retry_available=True), 422)
    finally:
        if model_client is not None:
            await model_client.aclose()


@router.patch('/{experience_id}')
async def edit_experience(experience_id: str, request: Request):
    require_enabled()
    body = loads(await request.body())
    allowed = set(skill_module('feedback-improvement').ExperienceDraft.model_fields)
    if set(body) - allowed - {'expected_revision'}:
        raise ValueError('只能修改经验卡片内容；来源和记账主体由原账单绑定')
    def edit(current):
        if current['status'] == 'active':
            raise Conflict('请先停用，再修改经验并重新确认')
        source_task(current['source']['task_id'])
        current.update({key: body[key] for key in allowed if key in body})
        checked = function(None, 'feedback-improvement', 'validate_experience')(current)
        if not checked['valid']:
            raise ValueError(checked['issues'][0]['message'])
        current.update(status='draft', review=None, revision=current['revision'] + 1)
    if type(body.get('expected_revision')) is not int:
        raise Conflict('请提供当前经验版本')
    saved = repository().mutate('experience', experience_id, edit, expected_revision=body['expected_revision'])
    return response(dict(experience=saved))


@router.post('/{experience_id}/review')
async def review_experience(experience_id: str, request: Request):
    require_enabled()
    body = loads(await request.body())
    if body.get('action') not in {'activate', 'pause'} or type(body.get('expected_revision')) is not int:
        raise ValueError('请提供当前版本和activate/pause操作')
    if body['action'] == 'activate' and body.get('approved') is not True:
        raise ValueError('请明确确认这条经验的内容和适用范围')
    def review(current):
        if body['action'] == 'activate':
            source_task(current['source']['task_id'])
            checked = function(None, 'feedback-improvement', 'validate_experience')(current, activate=True)
            if not checked['valid']:
                raise ValueError(checked['issues'][0]['message'])
        current.setdefault('review_history', []).append(dict(
            action=body['action'], at=now(), operator=operator(request), revision=current['revision']))
        current.update(status='active' if body['action'] == 'activate' else 'paused',
            review=current['review_history'][-1], revision=current['revision'] + 1)
    saved = repository().mutate('experience', experience_id, review, expected_revision=body['expected_revision'])
    return response(dict(experience=saved))
