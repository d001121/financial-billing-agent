"""Validate compiled specialists' final output without another model request."""
import asyncio
import json
import re
from typing import Any, Literal, NotRequired

from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from backend.extensions.skill_versions import skill_module
from backend.infrastructure.repository import repository
from .delegation import Text, delegated_envelope


class Proposal(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    charge_id: str | None
    field: Text
    value: Any


class Issue(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    code: Text
    message: Text


class SpecialistReport(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    status: Literal['done', 'blocked']
    summary: Text
    saved: bool
    proposals: list[Proposal] = Field(max_length=100)
    issues: list[Issue] = Field(max_length=100)
    evidence_refs: list[str] = Field(max_length=200)


class HandoffState(AgentState):
    structured_response: NotRequired[dict]


class ExpertHandoff(AgentMiddleware):
    state_schema = HandoffState

    def __init__(self, task_id, revision, cap, scope):
        self.task_id, self.revision, self.cap, self.scope = task_id, revision, cap, scope

    async def abefore_agent(self, state, runtime):
        # Native isolated delegation deliberately excludes the parent's pin
        # state. Pin the specialist's own extraction instructions once so its
        # gated reading/save tools are available on the first useful call.
        spec = next(s for s in self.cap['config']['agents']['agents'] if s['name'] == self.scope['role'])
        pinned = {m.additional_kwargs.get('skill', {}).get('name') for m in state.get('messages', [])
                  if getattr(m, 'additional_kwargs', {}).get('lc_source') == 'pinned_skill'}
        names = [name for name in spec.get('skills', []) if name == 'document-extraction' and name not in pinned]
        if names:
            return dict(pinned_skills=names)

    async def aafter_agent(self, state, runtime):
        envelope = delegated_envelope(state)
        issues = []
        last = next((m for m in reversed(state.get('messages', [])) if getattr(m, 'type', None) == 'ai'), None)
        text = last.text.strip() if last else ''
        blocks = re.findall(r'```(?:json)?\s*(.*?)\s*```', text, re.S)
        try:
            report = SpecialistReport.model_validate_json(blocks[0] if len(blocks) == 1 else text).model_dump()
        except (ValidationError, TypeError, ValueError):
            report = dict(status='blocked', summary='专家未返回可验收的结构化结果', saved=False,
                          proposals=[], issues=[], evidence_refs=[])
            issues.append(dict(code='INVALID_HANDOFF', message='结果格式不合法；未为格式修复追加模型调用，主控请核对现有产物'))
        host = (envelope or {}).get('host') or {}
        contract = (envelope or {}).get('contract') or {}
        if (host.get('task_id') != self.task_id or host.get('revision') != self.revision or
                host.get('capability_version') != self.cap['version'] or host.get('role') != self.scope['role']):
            issues.append(dict(code='DELEGATION_STALE', message='委派身份或版本不匹配，不能接受结果'))
        repo = repository()
        task = await asyncio.to_thread(repo.get_fields, 'task', self.task_id,
            ['sources', 'usage', 'dispatch_history']) if hasattr(repo, 'get_fields') else await asyncio.to_thread(
                repo.get, 'task', self.task_id)
        if task['revision'] != self.revision:
            issues.append(dict(code='DELEGATION_STALE', message='任务revision已变化，专家旧提案不能提交'))
        allowed_sources = set(contract.get('source_ids', []))
        module = skill_module('document-extraction', self.cap['version'])
        refs = module.citation_index(dict(sources=[s for s in task.get('sources', [])
            if s['source_id'] in allowed_sources]))
        if any(ref not in refs for ref in report['evidence_refs']):
            issues.append(dict(code='CITATION_UNKNOWN', message='交接引用不属于当前委派原文；不能视为已核验依据'))
        if report['proposals'] and not report['evidence_refs']:
            issues.append(dict(code='CITATION_REQUIRED', message='字段修改建议必须附带真实原文引用'))
        owned = set(contract.get('charge_ids', []))
        if owned and any(p['charge_id'] not in owned for p in report['proposals']):
            issues.append(dict(code='PROPOSAL_OUT_OF_SCOPE', message='修改建议超出委派费用范围'))
        history = task.get('dispatch_history') or {}
        actual_saved = history.get('revision') == self.revision and history.get('run_id') == self.scope['id'] and any(
            e.get('tool') == 'save_document_extraction' and e.get('status') == 'done' and
            e.get('role') == self.scope['role'] and e.get('delegation_id') == host.get('delegation_id')
            for e in history.get('attempts', {}).values())
        if report['saved'] and not actual_saved:
            issues.append(dict(code='UNSAVED_CLAIM', message='专家声称已保存，但没有对应成功保存回执'))
        report['saved'] = actual_saved
        if issues:
            report['status'] = 'blocked'
            report['issues'].extend(issues)
        usage = task.get('usage') or {}
        run = usage.get('run_budget') or {}
        report.update(task_id=self.task_id, revision=self.revision, capability_version=self.cap['version'],
            delegation_id=host.get('delegation_id'), scope=contract,
            resource_usage=dict(task_model_calls=usage.get('model_calls', 0),
                task_tool_calls=usage.get('tool_calls', 0),
                role_run_model_calls=run.get('experts', {}).get(self.scope['role'], 0)),
            evidence_sources={ref: {k: refs[ref].get(k) for k in ('source_id', 'anchor', 'page', 'sheet', 'row')}
                for ref in report['evidence_refs'] if ref in refs})
        await asyncio.to_thread(repo.event, self.task_id, 'specialist_handoff',
            revision=self.revision, delegation_id=host.get('delegation_id'), role=self.scope['role'],
            status=report['status'], saved=actual_saved,
            issue_codes=[i['code'] for i in report['issues']], resource_usage=report['resource_usage'])
        # Deep Agents serializes structured_response from CompiledSubAgent.
        # No jump_to, second agent, format retry, or model-generated receipt.
        return dict(structured_response=report)
