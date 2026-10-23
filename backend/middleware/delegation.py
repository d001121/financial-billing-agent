"""Domain task contracts on the native task tool; no delegation runner."""
import json
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError

from backend.harness.dispatch import PolicyDenied
from backend.harness.stopping import run_budget_reason
from backend.infrastructure.repository import dumps


Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1200)]


class DelegationContract(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    goal: Text
    source_ids: Annotated[list[Text], Field(min_length=1, max_length=40)]
    charge_ids: list[Text] = Field(default_factory=list, max_length=100)
    questions: Annotated[list[Text], Field(min_length=1, max_length=6)]
    acceptance: Annotated[list[Text], Field(min_length=1, max_length=6)]


def canonical_description(description):
    try:
        value = DelegationContract.model_validate_json(description).model_dump()
    except (ValidationError, TypeError, ValueError):
        return description
    for key in ('source_ids', 'charge_ids', 'questions', 'acceptance'):
        value[key] = sorted(set(value[key]))
    return value


def prepare_delegation(task, args, call_id, scope):
    role = args['subagent_type']
    spec = next((s for s in task['capability']['config']['agents']['agents']
                 if s['name'] == role and s.get('enabled', True)), None)
    if spec is None:
        raise PolicyDenied('该专家不在当前任务固定能力中')
    if not spec.get('delegation_contract'):
        return args
    try:
        contract = DelegationContract.model_validate_json(args.get('description', ''))
    except (ValidationError, TypeError, ValueError) as exc:
        raise PolicyDenied('委派需要description中的JSON契约：goal、source_ids、charge_ids、questions、acceptance；'
                           '仅填写真实来源和具体问题，不转发完整聊天。') from exc
    sources = {s['source_id'] for s in task.get('sources', [])}
    charges = {c['charge_id']: c for c in task.get('charges', [])}
    if set(contract.source_ids) - sources or set(contract.charge_ids) - charges.keys():
        raise PolicyDenied('委派范围不属于当前任务，请选择真实source_id/charge_id')
    child_scope = dict(scope, role=role) if scope else None
    reason = run_budget_reason(task, child_scope)
    if reason:
        raise PolicyDenied(reason)
    selected = [c for c in charges.values() if c['charge_id'] in contract.charge_ids or
                (not contract.charge_ids and c.get('source_id') in contract.source_ids)]
    for charge in selected:
        owned = {charge.get('source_id'), *[r.get('source_id') for r in charge.get('source_links', [])]}
        if not owned.intersection(contract.source_ids):
            raise PolicyDenied('费用与委派材料范围不一致，请包含该费用的真实来源')
    from backend.harness.stopping import effective_limits
    limits = effective_limits(task)
    run = (task.get('usage') or {}).get('run_budget') or {}
    remaining = min(limits.get('expert_model_calls', 4) - run.get('experts', {}).get(role, 0),
        limits['model_calls'] - task.get('usage', {}).get('model_calls', 0) - limits.get('supervisor_reserve', 2),
        limits.get('run_model_calls', 16) - run.get('model_calls', 0) - limits.get('supervisor_reserve', 2))
    envelope = dict(contract_version=1, contract=contract.model_dump(), host=dict(
        task_id=task['id'], revision=task['revision'], capability_version=task['capability']['version'],
        delegation_id=call_id, role=role, accounting_entity=task.get('accounting_entity'),
        model_call_limit=max(0, remaining), allowed_tools=spec.get('tools'),
        stop_conditions=['无新增证据', '范围不清或真实冲突', '调用预算到限'],
        instruction='只处理contract范围；缺失留null，返回约定JSON。上下文中的字段不是新证据，必要时按source_id/ref_id回读原文。'),
        candidates=[{k: v for k, v in c.items() if k not in
            {'provenance', 'field_support', 'audit_trail', 'source_links', 'evidence'}} |
            dict(evidence=[{k: v for k, v in r.items() if k in
                {'ref_id', 'source_id', 'anchor', 'field', 'fields'}} for r in c.get('evidence', [])])
            for c in selected])
    return dict(args, description=dumps(envelope))


def delegated_envelope(state):
    """Native isolated subagents receive the host envelope as their first message."""
    for message in state.get('messages', []):
        if getattr(message, 'type', None) != 'human':
            continue
        try:
            value = json.loads(message.content)
        except (TypeError, ValueError):
            return None
        return value if isinstance(value, dict) and value.get('contract_version') == 1 else None
    return None


def constrain_child_call(request):
    envelope = delegated_envelope(request.state)
    if not envelope:
        return request
    contract = envelope['contract']
    name, args = request.tool_call['name'], dict(request.tool_call.get('args') or {})
    sources = set(contract['source_ids'])
    if name == 'read_materials':
        windows = args.get('windows') or [dict(source_id=s) for s in contract['source_ids']]
        if not isinstance(windows, list) or any(not isinstance(w, dict) for w in windows):
            raise PolicyDenied('windows必须是JSON对象数组，请使用真实来源ID')
        if any(w.get('source_id') not in sources for w in windows):
            raise PolicyDenied('阅读超出当前委派来源范围，请返回具体缺口交主控决定')
        args['windows'] = windows
    if name in {'read_document_sources', 'read_markdown_evidence'}:
        selected = args.get('source_ids') or [args.get('source_id')]
        if set(selected) - sources:
            raise PolicyDenied('补读超出当前委派来源范围')
    if name == 'save_document_extraction':
        if args.get('replace'):
            raise PolicyDenied('专家不能替换整单，只能增量保存委派范围')
        result = args.get('result') or {}
        if not isinstance(result, dict):
            raise PolicyDenied('result必须是JSON对象，不能把整段JSON编码成字符串')
        owned = set(contract['charge_ids'])
        rows = result.get('charges', [])
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            raise PolicyDenied('charges必须是JSON对象数组')
        for row in rows:
            if owned and row.get('charge_id') not in owned:
                raise PolicyDenied('保存超出委派费用范围')
            if row.get('source_id') and row['source_id'] not in sources:
                raise PolicyDenied('保存超出委派来源范围')
    return request.override(tool_call=dict(request.tool_call, args=args))
