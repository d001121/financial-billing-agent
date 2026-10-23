"""Route existing financial Hook failures to a concrete human question.

This stop check consumes pinned validation facts; it does not infer AR/AP,
parse documents, change financial values, or execute a second agent loop.
"""
from backend.extensions.skill_versions import function, skill_module


def completion_question(task):
    if task.get('status') == 'review_deferred':
        return None
    validation = task.get('validation') or {}
    if validation.get('revision') != task['revision']:
        return None
    if not task.get('accounting_entity'):
        # The entity is a caller parameter, but after candidates are saved the
        # host opens a native conversation_review so the caller can supply it
        # in chat. This is the human-review stop, not an extraction-time block.
        return function(task.get('capability'), 'human-review', 'entity_question')(task)
    issues = [issue for issue in validation.get('issues', [])
              if issue.get('code') in ('POSTING_UNRESOLVED', 'POSTING_CONFLICT')]
    if not issues:
        module = skill_module('human-review', task['capability']['version'])
        return module.automatic_stop_question(task) if hasattr(module, 'automatic_stop_question') else None
    ids = {issue.get('charge_id') for issue in issues}
    records = [record for record in task.get('records', [])
               if None in ids or record['charge_id'] in ids]
    facts = '\n'.join(f'• {r.get("charge_details", {}).get("charge_item") or r["charge_id"]}：'
                      f'材料收款方 {r.get("creditor") or "未明确"}；付款方 {r.get("debtor") or "未明确"}'
                      for r in records)
    reasons = '；'.join(dict.fromkeys(issue['message'] for issue in issues))
    entity = str(task['accounting_entity']).strip().casefold()
    payer_missing = [r for r in records
                     if str(r.get('creditor') or '').strip().casefold() == entity and not r.get('debtor')]
    payee_missing = [r for r in records
                     if str(r.get('debtor') or '').strip().casefold() == entity and not r.get('creditor')]
    if payer_missing and not payee_missing:
        ask = '当前主体已作为收款方；请补充这笔费用的付款方（债务人）是谁。'
    elif payee_missing and not payer_missing:
        ask = '当前主体已作为付款方；请补充这笔费用的收款方（债权人）是谁。'
    else:
        ask = ('请说明本主体在这笔费用中是收款方还是付款方、与上述公司的关系，'
               '或提供正确主体；也可以回复“暂缓”。')
    return dict(action='edit', field='posting_type', source='completion',
        charge_id=records[0]['charge_id'] if len(records) == 1 else None,
        question=f'已保存提取结果，但本次 AR/AP 尚未确定：{reasons}。\n'
                 f'当前记账主体：{task["accounting_entity"]}。\n{facts}\n{ask}收到说明后继续核对。')
