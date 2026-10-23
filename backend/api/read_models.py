"""Read-only UI projections of stored business facts; no scoring or reconciliation."""

TASK_FIELDS = ('id', 'title', 'accounting_entity', 'status', 'control', 'revision', 'created_at',
               'updated_at', 'thread_id', 'run_id', 'asset_ids', 'summary', 'usage', 'run_status', 'approval', 'auto_review', 'review_request')


def bill_projection(task):
    """One submission is one bill bundle. Never merge submissions by filename/number."""
    result = {key: task.get(key) for key in TASK_FIELDS}
    records = task.get('records') or []
    sources = task.get('sources') or []
    issues = list(task.get('issues') or []) + list(task.get('intake_issues') or [])
    issues.extend((task.get('validation') or {}).get('issues') or [])
    for record in records:
        issues.extend(record.get('issues') or [])
    unique = {}
    for issue in issues:
        key = (issue.get('code'), issue.get('message'), issue.get('charge_id'), issue.get('source_id'), issue.get('field'))
        unique.setdefault(key, issue)
    result.update(record_count=len(records), issue_count=len(unique),
        bill=dict(id=task['id'], material_count=len(sources) or len(task.get('asset_ids') or []),
            references=list(dict.fromkeys(r.get('document_info', {}).get('reference_no') for r in records
                                          if r.get('document_info', {}).get('reference_no'))),
            parties=list(dict.fromkeys(p for r in records for p in
                (r.get('transaction_party', {}).get('issuer'), r.get('transaction_party', {}).get('recipient')) if p)),
            # These are individual saved amounts, not a cross-currency sum.
            amounts=[dict(amount=r.get('charge_details', {}).get('amount'),
                          currency=r.get('charge_details', {}).get('currency')) for r in records],
            attention=list(unique.values()),
            materials=[{k: s.get(k) for k in ('source_id', 'name', 'parent_source_id', 'status', 'format')}
                       for s in sources]))
    return result


def call_path(state):
    """Project native checkpoint tool calls with their actual subgraph task."""
    rows = []
    def visit(current, namespace, parent_task_id=None):
        values = current.get('values') or {}
        for message in values.get('messages', []):
            for call in message.get('tool_calls', []):
                rows.append(dict(call_id=call.get('id'), tool=call.get('name'), namespace=namespace,
                    parent_task_id=parent_task_id,
                    agent=(call.get('args') or {}).get('subagent_type') if call.get('name') == 'task' else None))
        for task in current.get('tasks', []):
            child = task.get('state')
            if isinstance(child, dict) and 'values' in child:
                visit(child, namespace + [task.get('name', 'subgraph')], task.get('id'))
    visit(state, [])
    return rows
