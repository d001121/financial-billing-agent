"""One shared task counter for parent, specialists and retries."""
import time
from backend.infrastructure.repository import repository
from .dispatch import check, PolicyDenied
from .stopping import RunBudgetStop, active_stop, run_budget_reason, effective_limits


def consume(task_id, kind, *, scope=None):
    if not task_id:
        return
    check(task_id, policy_only=True)
    def update(task):
        if task.get('control') != 'running':
            raise PolicyDenied('任务暂停或取消，未派发调用')
        usage = task.get('usage') or {}
        task['usage'] = usage
        limits = effective_limits(task)
        if scope and scope['revision'] != task['revision']:
            raise RunBudgetStop('任务revision已变化，停止旧运行')
        stop = active_stop(task, scope)
        if stop:
            raise RunBudgetStop(stop['message'])
        if usage.get(kind, 0) >= limits[kind]:
            raise PolicyDenied(f'{kind}已达到共享任务预算 {limits[kind]}')
        active = float(usage.get('active_seconds', 0))
        if usage.get('active_since'):
            active += time.time() - float(usage['active_since'])
        if active >= limits['active_seconds']:
            raise PolicyDenied('共享活跃执行时间预算已用尽')
        if kind == 'model_calls' and scope:
            reason = run_budget_reason(task, scope)
            if reason:
                raise RunBudgetStop(reason)
            run = usage.get('run_budget') or {}
            if run.get('id') != scope['id']:
                run = dict(id=scope['id'], revision=task['revision'], model_calls=0, experts={})
                usage['run_budget'] = run
            run['model_calls'] += 1
            if scope.get('role', 'supervisor') != 'supervisor':
                experts = run.setdefault('experts', {})
                experts[scope['role']] = experts.get(scope['role'], 0) + 1
        usage[kind] = usage.get(kind, 0) + 1
    try:
        repo = repository()
        if hasattr(repo, 'mutate_fields'):
            repo.mutate_fields('task', task_id, ['usage', 'control', 'capability', 'automatic_stop'], update)
        else:
            repo.mutate('task', task_id, update)
    except RunBudgetStop:
        raise
    except PolicyDenied as exc:
        repo = repository()
        repo.mutate('task', task_id, lambda t: t.update(status='budget_exhausted', summary=str(exc)))
        if hasattr(repo, 'flush'):
            repo.flush(task_id)
        raise
