"""Host-only capability and budget checks; domain checks stay in Skills."""
from backend.extensions.skill_versions import enabled_skill
from backend.harness.stopping import effective_limits


def validate_native_hook(name, task):
    issues = []
    if name == 'capability':
        for skill in ('document-extraction', 'evidence-linking', 'billing-reconciliation', 'human-review', 'billing-export'):
            if not enabled_skill(skill):
                issues.append(dict(code='SKILL_DISABLED', message=f'Skill已禁用: {skill}', severity='error'))
    if name == 'budget':
        usage, limits = task.get('usage', {}), effective_limits(task)
        for key in ('model_calls', 'tool_calls', 'active_seconds'):
            if usage.get(key, 0) > limits[key]:
                issues.append(dict(code='BUDGET_EXCEEDED', message=f'{key}已超出预算', severity='error'))
    return issues
