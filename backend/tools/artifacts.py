"""Bind portable Skill proposals to versioned storage and validation."""
from langchain.tools import tool
from backend.extensions.skill_versions import enabled_skill, function
from backend.infrastructure.repository import repository
from backend.harness.dispatch import check


def confidence_payload(task, validation):
    payload = dict(task, validation=validation)
    threshold = task['capability']['config']['runtime'].get('confidence_review_threshold')
    if threshold is not None:
        payload['confidence_options'] = {'review_threshold': threshold}
    return payload


def verification_summary(validation):
    """Project existing Skill results for the Agent and its native tool record."""
    confidence = validation.get('confidence') or {}
    items = confidence.get('review_items') or []
    return dict(revision=validation.get('revision'), ok=validation.get('ok'),
        score=confidence.get('score'), review_score=confidence.get('review_score'),
        calibrated=confidence.get('calibrated', False),
        review_required=confidence.get('review_required'),
        review_items=items[:8], review_item_count=len(items),
        summary=confidence.get('summary'),
        artifact='当前版本完整字段评分与原文定位见账单结果')


def save_fields(task_id, revision, **values):
    """Stage a task update and flush it as one durable stage-end write."""
    def apply(task):
        task.update(values)
    repo = repository()
    result = repo.mutate('task', task_id, apply, expected_revision=revision)
    if hasattr(repo, 'flush'):
        repo.flush(task_id)
    return result


def save_fields_fast(task_id, revision, **values):
    """Stage selected fields in Redis; the tool boundary performs the flush."""
    def apply(task):
        task.update(values)
    repo = repository()
    if hasattr(repo, 'mutate_fields'):
        return repo.mutate_fields('task', task_id, list(values), apply,
                                  expected_revision=revision)
    result = repo.mutate('task', task_id, apply, expected_revision=revision)
    if hasattr(repo, 'flush'):
        repo.flush(task_id)
    return result


def validate_and_store(task_id, task=None):
    from backend.hooks.validation import validate
    task = task or repository().get('task', task_id)
    validation = validate(task)
    cap = task['capability']
    values = dict(validation=validation, issues=validation['issues'])
    if enabled_skill('billing-confidence') and any(s['name'] == 'billing-confidence' and s.get('enabled', True)
           for s in cap['config']['skills']['skills']):
        confidence = function(cap, 'billing-confidence', 'assess_confidence')(confidence_payload(task, validation))
        validation['confidence'] = confidence
    save_fields_fast(task_id, task['revision'], **values)
    repository().event(task_id, 'validation', result=validation)
    return validation


def reconcile_saved(task_id, update_instructions=None):
    task = repository().get('task', task_id)
    cap = task['capability']
    payload = dict(task)
    if cap.get('improvements', {}).get('active_version'):
        check(task_id, skill='feedback-improvement')
        payload['charge_mapping'] = function(cap, 'feedback-improvement', 'resolve_mapping')(
            cap['improvements'], task)
    if update_instructions is not None:
        payload['update_instructions'] = update_instructions
    linked = function(cap, 'evidence-linking', 'link_evidence')(payload)
    payload['charges'] = linked.get('charges', payload.get('charges', []))
    payload['evidence'] = linked
    payload['evidence_issues'] = linked.get('issues', [])
    if task.get('history_mode') == 'automatic':
        from .history import prepare_history
        payload.update(prepare_history(payload, repository()))
    result = function(cap, 'billing-reconciliation', 'reconcile_charges')(payload)
    fields = dict(records=result.get('records', []), reconciliation=result,
                  charges=payload['charges'], documents=linked.get('documents', task.get('documents', [])),
                  evidence=linked, validation=None, approval=None, export=None)
    if task.get('history_mode') == 'automatic':
        fields.update(existing_records=payload['existing_records'], history_lookup=payload['history_lookup'])
    if 'charge_mapping' in payload:
        fields['charge_mapping'] = payload['charge_mapping']
    if update_instructions is not None:
        fields['update_instructions'] = update_instructions
    saved = {**task, **fields}
    save_fields_fast(task_id, task['revision'], **fields)
    validation = validate_and_store(task_id, task=saved)
    return dict(record_count=len(fields['records']), revision=task['revision'], validation=validation,
                verification=verification_summary(validation),
                history_lookup=payload.get('history_lookup'),
                artifact=f'/api/tasks/{task_id}/artifacts')


def validation_tool(task_id):
    @tool
    def validate_task() -> dict:
        """执行统一配置中所有必需Hook，查看错误定位和当前revision，失败不能视为正式结果。"""
        return validate_and_store(task_id)
    return validate_task
