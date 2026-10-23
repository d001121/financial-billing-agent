"""Resolve independent configured checks in priority order."""
from backend.config.transactions import read_config


REQUIRED = {'schema', 'coverage', 'evidence', 'amount', 'matching', 'update', 'posting',
            'revision', 'approval', 'capability', 'budget'}


def registered_hooks(task):
    definitions = task['capability']['config']['hooks']['hooks']
    live = {hook['name']: hook for hook in read_config('hooks')['hooks']}
    missing = REQUIRED - {hook['name'] for hook in definitions}
    return sorted(definitions, key=lambda hook: hook.get('priority', 0)), live, missing
