"""One validation entry used by tools, revisions, approval and export."""
from backend.extensions.skill_versions import function
from backend.infrastructure.repository import now, repository
from .registry import REQUIRED, registered_hooks
from .guards import validate_native_hook


def validate(task, *, event='artifact', require_approval=False):
    definitions, live, missing_hooks = registered_hooks(task)
    issues, results = [], []
    for missing in sorted(missing_hooks):
        issues.append(dict(code='HOOK_MISSING', message=f'必需校验缺失: {missing}', severity='error'))
    payload = dict(task, current_revision=task['revision'], expected_revision=task['revision'],
                   require_approval=require_approval)
    if task.get('history_mode') == 'automatic':
        from backend.tools.history import prepare_history
        try:
            payload['current_history_lookup'] = prepare_history(task, repository())['history_lookup']
        except Exception as exc:
            issues.append(dict(code='HISTORY_UNAVAILABLE', field='match', severity='error',
                message=f'历史账单检索失败，不能按无匹配放行: {type(exc).__name__}'))
    for hook in sorted(definitions, key=lambda h: h.get('priority', 0)):
        if not live.get(hook['name'], {}).get('enabled', False) or not hook.get('enabled', True):
            if hook['name'] in REQUIRED:
                issues.append(dict(code='HOOK_DISABLED', message=f"必需校验已禁用: {hook['name']}", severity='error'))
            continue
        if 'native' in hook:
            local = validate_native_hook(hook['name'], task)
            issues.extend(local)
            results.append(dict(name=hook['name'], ok=not local, native=hook['native'], issues=local))
            continue
        if hook['name'] == 'approval' and not require_approval:
            continue
        try:
            result = function(task['capability'], hook['skill'], hook['function'])(payload)
            if not isinstance(result, dict):
                raise ValueError('Hook必须返回校验结果对象')
            flags = [result[key] for key in ('valid', 'ok') if key in result]
            accepted = bool(flags) and all(flag is True for flag in flags)
            local = [dict(i, hook=hook['name']) for i in result.get('issues', [])]
            results.append(dict(result, name=hook['name'], ok=accepted))
            issues.extend(local)
            if (hook['name'] in REQUIRED or hook.get('required')) and not accepted and not any(
                    i.get('severity', 'error') == 'error' for i in local):
                issues.append(dict(code='HOOK_REJECTED', hook=hook['name'], severity='error',
                    message=f"必需校验{hook['name']}未通过；不能仅因问题列表为空而放行"))
        except Exception as exc:
            results.append(dict(name=hook['name'], ok=False))
            issues.append(dict(code='HOOK_ERROR', hook=hook['name'],
                               message=f'{type(exc).__name__}: {exc}', severity='error'))
    for item in task.get('intake_issues', []):
        issues.append(dict(item, hook='coverage'))
    result = dict(ok=not any(i.get('severity', 'error') == 'error' for i in issues),
                  revision=task['revision'], issues=issues, checks=results, at=now(), event=event)
    return result
