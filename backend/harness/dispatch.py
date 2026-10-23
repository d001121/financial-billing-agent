"""Task dispatch checks at the native model and tool boundaries."""
from backend.config.transactions import read_config
from backend.extensions.skill_versions import enabled_skill
from backend.infrastructure.repository import repository


class PolicyDenied(RuntimeError):
    pass


def check(task_id, *, revision=None, skill=None, mcp=None, allow_paused=False, policy_only=False):
    if not task_id:
        return None
    repo = repository()
    # Policy-only checks avoid transferring the full task payload (which can
    # include several hundred KB of OCR material); callers that keep the
    # returned task still receive the complete record.
    task = (repo.get_fields('task', task_id, ['control', 'deleted_at', 'revision'])
            if policy_only and hasattr(repo, 'get_fields') else repo.get('task', task_id))
    if task.get('deleted_at'):
        raise PolicyDenied('账单已从工作台删除，停止新派发')
    if task.get('control') in ('paused', 'cancelled', 'pausing') and not allow_paused:
        raise PolicyDenied(f"任务已{task['control']}，停止新派发")
    if revision is not None and task['revision'] != revision:
        raise PolicyDenied('任务revision已变化；旧提案不能覆盖新版本')
    if skill and not enabled_skill(skill):
        raise PolicyDenied(f'Skill已禁用: {skill}')
    current_hooks = {h['name']: h for h in read_config('hooks')['hooks']}
    if not all(current_hooks.get(name, {}).get('enabled') for name in ('capability', 'budget')):
        raise PolicyDenied('必需的启用状态/预算Hook已禁用，不能派发')
    if mcp:
        server = next((s for s in read_config('mcp')['servers'] if s['id'] == mcp), None)
        if not server or not server.get('enabled', True):
            raise PolicyDenied(f'MCP已禁用: {mcp}')
    return task
