"""Read-only scores from the task's pinned business Skill and current checks."""
from fastapi import APIRouter

from backend.extensions.skill_versions import enabled_skill, function
from backend.hooks.validation import validate
from backend.infrastructure.repository import repository
from backend.tools.artifacts import confidence_payload

from ..responses import response

router = APIRouter(tags=['confidence'])


@router.get('/api/tasks/{task_id}/confidence')
def task_confidence(task_id: str):
    task = repository().get('task', task_id)
    cap = task['capability']
    enabled = any(s['name'] == 'billing-confidence' and s.get('enabled', True)
                  for s in cap['config']['skills']['skills'])
    if not enabled or not enabled_skill('billing-confidence'):
        return response(dict(revision=task['revision'], method='unavailable', calibrated=False,
            score=None, band='unavailable', records=[], blockers=[], eligible_for_quick_confirm=False,
            summary=('该任务固定的能力版本未包含置信度规则；历史结果未被重新评分。' if not enabled
                     else '置信度Skill当前已停用，保留原财务结果。'),
            capability_version=cap['version']))
    # Never trust a stored/model-provided score or write into a historical task.
    payload = confidence_payload(task, validate(task))
    result = function(cap, 'billing-confidence', 'assess_confidence')(payload)
    return response(dict(result, capability_version=cap['version']))
