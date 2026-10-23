"""Revision-bound stop facts consumed by native middleware, never an agent runner."""
from .dispatch import PolicyDenied


class RepairStop(PolicyDenied):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


class RunBudgetStop(PolicyDenied):
    pass


def effective_limits(task):
    """Cumulative meters stay intact; an explicit human turn has its own ceiling."""
    limits = dict(task['capability']['config']['runtime'])
    grant = (task.get('usage') or {}).get('human_turn') or {}
    limits.update(grant.get('ceilings') or {})
    if grant:
        limits['run_model_calls'] = min(limits.get('run_model_calls', 16), limits['turn_model_calls'])
    return limits


def active_stop(task, scope=None):
    stop = task.get('automatic_stop') or {}
    if stop.get('revision') != task.get('revision'):
        return None
    if scope and stop.get('budget_id') and stop['budget_id'] != scope['id']:
        return None
    return stop or None


def stop_task(task, code, message, scope=None):
    task['automatic_stop'] = dict(code=code, message=message, revision=task['revision'],
                                 budget_id=(scope or {}).get('id'))
    task.update(approval=None, auto_review=None)


def run_budget_reason(task, scope):
    if not scope:
        return None
    if scope['revision'] != task['revision']:
        return '任务revision已变化，停止旧运行'
    usage = task.get('usage') or {}
    limits = effective_limits(task)
    run = usage.get('run_budget') or {}
    grant = usage.get('human_turn') or {}
    if grant and grant['id'] != scope['id']:
        return '旧运行不能使用新一轮人工回复预算'
    if run.get('id') != scope['id']:
        run = {}
    limit = limits.get('run_model_calls', limits['model_calls'] - limits['turn_model_calls'])
    if run.get('model_calls', 0) >= limit:
        return f'本轮共享模型预算 {limit} 已用尽，已保留结果'
    if usage.get('model_calls', 0) >= limits['model_calls']:
        return '共享任务模型预算已用尽，已保留结果'
    if scope.get('role', 'supervisor') != 'supervisor':
        reserve = limits.get('supervisor_reserve', 2)
        if (run.get('model_calls', 0) >= max(0, limit - reserve) or
                usage.get('model_calls', 0) >= max(0, limits['model_calls'] - reserve)):
            return '已预留主控收尾预算，专家停止调用并返回现有发现'
        role_limit = limits.get('expert_model_calls', 4)
        if run.get('experts', {}).get(scope['role'], 0) >= role_limit:
            return f'本轮该专家预算 {role_limit} 已用尽，请返回现有发现'
    return None
