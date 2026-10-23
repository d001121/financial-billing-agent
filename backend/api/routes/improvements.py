"""HTTP/storage bindings for opt-in Skill candidates and native local evaluations."""
import asyncio
from hashlib import sha256

from fastapi import APIRouter, Request
from psycopg.errors import UniqueViolation

from backend.config import settings
from backend.extensions.skill_versions import function
from backend.extensions.snapshots import snapshot
from backend.infrastructure.repository import repository, dumps, loads, now, Conflict
from backend.extensions.skill_versions import enabled_skill
from backend.harness.dispatch import PolicyDenied

from ..responses import response

router = APIRouter(prefix='/api/improvements', tags=['improvements'])


def require_enabled():
    if not enabled_skill('feedback-improvement'):
        raise PolicyDenied('feedback-improvement Skill已禁用，停止创建、评测和发布新候选')


def builtin_dataset():
    return loads((settings.ROOT / 'evals' / 'datasets' / 'charge-mapping.json').read_text(encoding='utf-8'))


@router.get('/datasets')
def list_datasets():
    data = builtin_dataset()
    builtin = dict(id='builtin', name='内置费用映射样例', enabled=True, revision=1,
                   synthetic=data['synthetic'], case_count=len(data['cases']), labeled_by='项目合成标注')
    records = repository().list('evaluation_dataset')
    return response({'datasets': [builtin, *[{k: v for k, v in r.items() if k != 'dataset'} for r in records]]})


@router.get('/datasets/{dataset_id}')
def get_dataset(dataset_id: str):
    return response(builtin_dataset() if dataset_id == 'builtin'
                    else repository().get('evaluation_dataset', dataset_id)['dataset'])


@router.post('/datasets')
async def import_dataset(request: Request):
    require_enabled()
    body = loads(await request.body())
    if not all(isinstance(body.get(k), str) and body[k].strip() for k in ('name', 'labeled_by')):
        raise ValueError('请填写数据集名称及人工标注人')
    result = function(None, 'feedback-improvement', 'validate_dataset')(body.get('dataset'))
    if not result['valid']:
        return response(result, 422)
    data = body['dataset']
    identity = 'dataset-' + result['dataset_digest'][:24]
    record = repository().get('evaluation_dataset', identity, required=False)
    if record is None:
        try:
            record = repository().create('evaluation_dataset', dict(id=identity, name=body['name'].strip(),
                labeled_by=body['labeled_by'].strip(), enabled=True, dataset=data,
                synthetic=data['synthetic'], case_count=len(data['cases']), digest=result['dataset_digest']))
        except UniqueViolation:
            record = repository().get('evaluation_dataset', identity)
    return response({k: v for k, v in record.items() if k != 'dataset'}, 201)


@router.patch('/datasets/{dataset_id}')
async def toggle_dataset(dataset_id: str, request: Request):
    if dataset_id == 'builtin':
        raise ValueError('内置回归样例保留，只能启停导入的数据集')
    body = loads(await request.body())
    if type(body.get('enabled')) is not bool:
        raise ValueError('enabled须为布尔值')
    if type(body.get('expected_revision')) is not int:
        raise Conflict('请提供当前数据集revision')
    def apply(current):
        current.update(enabled=body['enabled'], revision=current['revision'] + 1)
    record = repository().mutate('evaluation_dataset', dataset_id, apply,
                                expected_revision=body.get('expected_revision'))
    return response({k: v for k, v in record.items() if k != 'dataset'})


@router.get('/mapping')
def current_mapping(accounting_entity: str):
    registry = get_registry()
    mapping = function(None, 'feedback-improvement', 'resolve_mapping')(
        registry, dict(accounting_entity=accounting_entity))
    return response(dict(mapping=mapping, active_version=registry['active_version']))


def get_registry():
    """Initialize only our namespaced registry; no task or Agent state is changed."""
    repo = repository()
    existing = repo.get('improvement_registry', 'default', required=False)
    if existing is not None:
        return existing
    initial = function(None, 'feedback-improvement', 'initial_registry')()
    try:
        return repo.create('improvement_registry', dict(initial, id='default'))
    except UniqueViolation:
        return repo.get('improvement_registry', 'default')


def candidate_view(record, registry):
    view = dict(record['candidate'])
    published = any((version.get('candidate') or {}).get('candidate_id') == view['candidate_id']
                    for version in registry.get('versions', []))
    view.update(id=record['id'], revision=record['revision'], created_at=record.get('created_at'),
                comparison=record.get('comparison'),
                status='published' if published else ('evaluated' if record.get('comparison') else 'candidate'))
    return view


@router.get('/candidates')
def list_candidates():
    registry = get_registry()
    return response(dict(candidates=[candidate_view(record, registry)
        for record in repository().list('improvement_candidate')], registry=registry))


@router.post('/candidates')
async def create_candidate(request: Request):
    require_enabled()
    body = loads(await request.body())
    task = repository().get('task', body['task_id'])
    if body.get('expected_revision') != task['revision']:
        raise Conflict('来源任务revision已变化，请刷新后重新选择反馈')
    registry, cap = get_registry(), snapshot()
    source_fields = {key: task.get(key) for key in ('revision', 'accounting_entity', 'records', 'charges', 'asset_ids')}
    payload = {key: body.get(key) for key in ('opt_in', 'kind', 'scope', 'proposed_by', 'before', 'after')}
    payload.update(source=dict(task_id=task['id'], revision=task['revision'],
        capability_version=task['capability']['version'],
        artifact_digest=sha256(dumps(source_fields).encode()).hexdigest()), base_version=registry['active_version'])
    result = function(cap, 'feedback-improvement', 'prepare_candidate')(payload)
    if not result['valid']:
        return response(result, 422)
    candidate = result['candidate']
    repo = repository()
    record = repo.get('improvement_candidate', candidate['candidate_id'], required=False)
    if record is None:
        try:
            record = repo.create('improvement_candidate', dict(id=candidate['candidate_id'], candidate=candidate,
                                  capability=cap, comparison=None))
        except UniqueViolation:
            record = repo.get('improvement_candidate', candidate['candidate_id'])
    return response(dict(candidate=candidate_view(record, registry)), 201)


@router.post('/candidates/{candidate_id}/evaluate')
async def evaluate_candidate(candidate_id: str, request: Request):
    require_enabled()
    raw = await request.body()
    body = loads(raw) if raw else {}
    if not isinstance(body, dict) or set(body) - {'dataset_id'}:
        return response(dict(valid=False, issues=[dict(code='MEASURED_EVALUATION_ONLY',
            message='评测仅接受可选dataset_id，分数由服务器运行原生LangSmith及实际业务函数产生', severity='error')]), 422)
    repo = repository()
    record = repo.get('improvement_candidate', candidate_id)
    cap = record['capability']
    dataset_id = body.get('dataset_id') or 'builtin'
    dataset = builtin_dataset()
    if dataset_id != 'builtin':
        selected = repo.get('evaluation_dataset', dataset_id)
        if not selected.get('enabled', True):
            raise PolicyDenied('此评测数据集已禁用')
        dataset = selected['dataset']
    get_registry()
    measured = {}
    def evaluate_locked(registry):
        if any((version.get('candidate') or {}).get('candidate_id') == candidate_id
               for version in registry.get('versions', [])):
            raise Conflict('已发布候选不可重新评测，请创建新的候选版本')
        result = function(cap, 'feedback-improvement', 'evaluate_mapping')(
            dict(candidate=record['candidate'], registry=registry, dataset=dataset),
            reconcile=function(cap, 'billing-reconciliation', 'reconcile_charges'),
            link_evidence=function(cap, 'evidence-linking', 'link_evidence'),
            validate_amounts=function(cap, 'billing-reconciliation', 'validate_amounts'))
        comparison = result['comparison']
        comparison['capability_version'] = cap['version']
        comparison['dataset_id'] = dataset_id
        measured.update(result)
        if comparison.get('final_evaluated'):
            registry.setdefault('final_uses', {})[comparison['dataset_digest']] = record['candidate']['content_digest']
            for key in comparison.get('final_case_keys', []):
                registry.setdefault('final_cases', {})[key] = record['candidate']['content_digest']
        registry.setdefault('evaluation_history', []).append(dict(candidate_id=candidate_id,
            baseline_version=registry['active_version'], dataset_digest=comparison.get('dataset_digest'),
            final_evaluated=comparison.get('final_evaluated', False), passed=comparison['passed'], at=now()))
        registry['revision'] += 1
    # The local deterministic experiment performs no model/network/financial calls.
    # Locking the registry also serializes final-set exposure and baseline release.
    registry = await asyncio.to_thread(repo.mutate, 'improvement_registry', 'default', evaluate_locked)
    def store(current):
        current.update(comparison=measured['comparison'], evaluated_at=now(), revision=current['revision'] + 1)
    record = repo.mutate('improvement_candidate', candidate_id, store, expected_revision=record['revision'])
    return response(dict(candidate=candidate_view(record, registry), comparison=measured['comparison']),
                    200 if measured['valid'] else 422)


@router.post('/candidates/{candidate_id}/publish')
async def publish_candidate(candidate_id: str, request: Request):
    require_enabled()
    body = loads(await request.body())
    repo, result = repository(), {}
    record = repo.get('improvement_candidate', candidate_id)
    get_registry()
    def publish_locked(registry):
        measured = repo.get('improvement_candidate', candidate_id)
        outcome = function(record['capability'], 'feedback-improvement', 'publish_candidate')(
            dict(candidate=measured['candidate'], comparison=measured.get('comparison') or {}, registry=registry,
                 expected_active_version=body.get('expected_active_version'),
                 review=dict(approved=body.get('approved'), reviewer=body.get('reviewer'), reason=body.get('reason'),
                             candidate_id=candidate_id)))
        result.update(outcome)
        if outcome['valid']:
            registry.update(outcome['registry'])
            registry['revision'] += 1
    registry = repo.mutate('improvement_registry', 'default', publish_locked)
    if not result['valid']:
        return response(result, 409 if any(i['code'] == 'RELEASE_CONFLICT' for i in result['issues']) else 422)
    return response(dict(candidate=candidate_view(record, registry), registry=registry,
                         published_version=result['published_version']))


@router.post('/rollback')
async def rollback_candidate(request: Request):
    body = loads(await request.body())
    result = {}
    get_registry()
    def rollback_locked(registry):
        # Recovery remains available even when the Skill is excluded from new runs.
        outcome = function(None, 'feedback-improvement', 'rollback_candidate')(
            dict(registry=registry, target_version=body.get('target_version'),
                 expected_active_version=body.get('expected_active_version'),
                 review={key: body.get(key) for key in ('approved', 'reviewer', 'reason')}))
        result.update(outcome)
        if outcome['valid']:
            registry.update(outcome['registry'])
            registry['revision'] += 1
    registry = repository().mutate('improvement_registry', 'default', rollback_locked)
    if not result['valid']:
        return response(result, 409 if any(i['code'] == 'RELEASE_CONFLICT' for i in result['issues']) else 422)
    return response(dict(registry=registry))
