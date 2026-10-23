"""Check live task policy and shared budgets at each native dispatch boundary."""

import asyncio
import json
import time
from hashlib import sha256
from uuid import uuid4

import httpx
from langgraph.errors import GraphInterrupt

from langchain.agents.middleware import AgentMiddleware, ModelResponse, hook_config
from langchain.messages import AIMessage, ToolMessage

from backend.config.transactions import read_config
from backend.harness.budget import consume
from backend.harness.dispatch import PolicyDenied, check
from backend.harness.timing import active_async
from backend.harness.stopping import RepairStop, RunBudgetStop, active_stop, stop_task, run_budget_reason
from backend.infrastructure.repository import repository
from backend.tools.skill_bindings import TOOL_SKILLS
from .delegation import canonical_description, prepare_delegation, constrain_child_call, delegated_envelope


class DispatchPolicy(AgentMiddleware):
    # Read-only searches can legitimately be repeated after context editing.
    # These expensive/mutating operations must instead demonstrate new facts.
    progress_tools = {'task', 'intake_documents', 'read_document_sources', 'save_document_extraction'}
    progress_fields = ['charges', 'documents', 'totals', 'accounting_entity',
                       'feedback', 'update_instructions', 'candidate_digests', 'asset_ids']

    def __init__(self, task_id, revision, provenance=None, owners=None, *, scope=None, allowed_tools=None):
        self.task_id, self.revision = task_id, revision
        self.provenance = provenance or {}
        self.owners = owners or {}
        self.attempts = {}
        self.scope, self.allowed_tools = scope, allowed_tools

    def progress_digest(self, task):
        return sha256(json.dumps({k: task.get(k) for k in self.progress_fields},
            sort_keys=True, default=str, ensure_ascii=False).encode()).hexdigest()

    async def progress_transaction(self, transform):
        repo = repository()
        if hasattr(repo, 'mutate_fields'):
            return await asyncio.to_thread(repo.mutate_fields, 'task', self.task_id,
                ['dispatch_history', 'dispatch_budget_id', *self.progress_fields], transform,
                expected_revision=self.revision)
        return await asyncio.to_thread(repo.mutate, 'task', self.task_id, transform,
                                       expected_revision=self.revision)

    async def claim_progress(self, request):
        name = request.tool_call['name']
        if not self.task_id or name not in self.progress_tools:
            return None
        args = dict(request.tool_call.get('args') or {})
        if name == 'read_document_sources':
            args.pop('reason', None)  # Rephrasing a reason is not new evidence.
        if name == 'intake_documents':
            args.pop('asset_ids', None)  # The host always owns the material set.
        if name == 'task':
            args['description'] = canonical_description(args.get('description'))
        identity = sha256(json.dumps([self.scope.get('role') if self.scope else 'supervisor', name, args],
            sort_keys=True, default=str, ensure_ascii=False).encode()).hexdigest()
        token = str(uuid4())
        def claim(task):
            run_id = (self.scope or {}).get('id') or task.get('dispatch_budget_id')
            history = task.get('dispatch_history') or {}
            if history.get('revision') != self.revision or history.get('run_id') != run_id:
                history = dict(revision=self.revision, run_id=run_id, attempts={})
            previous = history['attempts'].get(identity) or {}
            facts = self.progress_digest(task)
            if previous.get('status') == 'running':
                raise PolicyDenied('相同工具调用仍在执行或结果未知，未重复派发；请核对已有运行回执')
            if previous.get('status') == 'interrupted' and previous.get('call_id') != request.tool_call.get('id'):
                raise PolicyDenied('相同子任务仍有待恢复的原生中断，请恢复原调用')
            if previous.get('status') in {'done', 'failed'} and previous.get('facts') == facts:
                raise RepairStop('NO_PROGRESS', '相同工具与事实已经处理，没有新增证据，停止重复执行并转待办核对')
            history['attempts'][identity] = dict(token=token, status='running', facts=facts,
                tool=name, call_id=request.tool_call.get('id'),
                role=(self.scope or {}).get('role', 'supervisor'),
                delegation_id=((delegated_envelope(request.state) or {}).get('host') or {}).get('delegation_id'))
            task['dispatch_history'] = history
        await self.progress_transaction(claim)
        return identity, token

    async def finish_progress(self, claim, status):
        if claim is None:
            return
        identity, token = claim
        def finish(task):
            entry = ((task.get('dispatch_history') or {}).get('attempts') or {}).get(identity)
            if entry and entry.get('token') == token:
                entry.update(status=status, facts=self.progress_digest(task))
        await self.progress_transaction(finish)

    async def stop(self, code, message):
        if self.task_id:
            await asyncio.to_thread(repository().mutate, 'task', self.task_id,
                lambda t: stop_task(t, code, message, self.scope), expected_revision=self.revision)

    async def context(self, fields):
        repo = repository()
        if hasattr(repo, 'get_fields'):
            return await asyncio.to_thread(repo.get_fields, 'task', self.task_id, fields)
        return await asyncio.to_thread(repo.get, 'task', self.task_id)

    async def termination_message(self, stop, reason):
        message = stop['message'] if stop else reason
        if self.scope and self.scope.get('role') != 'supervisor':
            # The parent receives a truthful structured result even when the
            # child exhausted its allowance before generating a final answer.
            content = '```json\n' + json.dumps(dict(status='blocked', saved=False,
                summary=message, proposals=[], issues=[dict(code=(stop or {}).get('code', 'EXPERT_BUDGET'),
                message=message)], evidence_refs=[]), ensure_ascii=False) + '\n```'
        else:
            if not stop:
                await self.stop('RUN_BUDGET', message)
            content = '本轮自动处理已停止：' + message + '。已保留候选与原文证据，未完成项目请在待办中核对。'
        return AIMessage(content=content)

    @hook_config(can_jump_to=['end'])
    async def abefore_model(self, state, runtime):
        if not self.task_id:
            return
        task = await self.context(['automatic_stop', 'usage', 'capability'])
        stop = active_stop(task, self.scope)
        reason = run_budget_reason(task, self.scope)
        if stop or reason:
            return dict(jump_to='end', messages=[await self.termination_message(stop, reason)])

    async def awrap_model_call(self, request, handler):
        await asyncio.to_thread(check, self.task_id, revision=self.revision, policy_only=True)
        started = time.perf_counter()
        status, usages = 'error', []
        try:
            async with active_async(self.task_id):
                result = await handler(request)
            status = 'success'
            usages = [m.usage_metadata for m in getattr(result, 'result', []) if getattr(m, 'usage_metadata', None)]
            return result
        except RunBudgetStop as exc:
            status = 'stopped'
            return ModelResponse(result=[await self.termination_message(None, str(exc))])
        finally:
            if self.task_id:
                await asyncio.to_thread(repository().event, self.task_id, 'model_round_receipt',
                    revision=self.revision, status=status,
                    elapsed_seconds=round(time.perf_counter() - started, 3),
                    input_tokens=sum(u.get('input_tokens', 0) for u in usages),
                    output_tokens=sum(u.get('output_tokens', 0) for u in usages),
                    cache_read_tokens=sum(u.get('input_token_details', {}).get('cache_read', 0) for u in usages))

    async def awrap_tool_call(self, request, handler):
        name = request.tool_call['name']
        call_id = request.tool_call.get('id')
        claim = None
        try:
            key = (name, json.dumps(request.tool_call.get('args') or {},
                                    sort_keys=True, default=str, ensure_ascii=False))
        except (TypeError, ValueError):
            key = None
        if name not in self.progress_tools and key is not None and self.attempts.get(key, {}).get('failed'):
            if name == 'save_document_extraction':
                await self.stop('NO_PROGRESS', '相同候选没有进展，请转人工复核')
            return ToolMessage(
                content='该工具已用完全相同的参数失败过，未再次执行；请修改参数或改用其他方式，不要原样重试。',
                tool_call_id=call_id, name=name, status='error',
            )
        try:
            if self.allowed_tools is not None and name not in self.allowed_tools:
                raise PolicyDenied('该专家只可使用已授权的只读核验工具，请返回建议交主控处理')
            if self.task_id:
                task = await self.context(['automatic_stop'])
                if active_stop(task, self.scope):
                    raise PolicyDenied('本轮自动处理已停止，保留结果并转待办核对')
            await asyncio.to_thread(
                check, self.task_id, revision=self.revision,
                skill=self.owners.get(name, TOOL_SKILLS.get(name)),
                mcp=self.provenance.get(name),
                policy_only=True,
            )
            if name == 'task':
                role = request.tool_call.get('args', {}).get('subagent_type')
                if not any(
                    agent['name'] == role and agent.get('enabled', True)
                    for agent in read_config('agents')['agents']
                ):
                    raise PolicyDenied(f'子Agent已禁用: {role}')
            claim = await self.claim_progress(request)
            if name == 'task' and self.task_id:
                task = await self.context(['capability', 'sources', 'charges', 'accounting_entity', 'usage'])
                args = prepare_delegation(task, request.tool_call.get('args') or {}, call_id, self.scope)
                request = request.override(tool_call=dict(request.tool_call, args=args))
            if self.scope and self.scope.get('role') != 'supervisor':
                request = constrain_child_call(request)
            await asyncio.to_thread(consume, self.task_id, 'tool_calls')
        except PolicyDenied as exc:
            await self.finish_progress(claim, 'failed')
            if isinstance(exc, RepairStop):
                await self.stop(exc.code, str(exc))
            if self.task_id:
                await asyncio.to_thread(
                    repository().event, self.task_id, 'dispatch_denied',
                    tool=name, message=str(exc),
                )
            return ToolMessage(
                content=str(exc), tool_call_id=call_id, name=name, status='error',
            )
        started = time.perf_counter()
        try:
            async with active_async(self.task_id):
                result = await handler(request)
        except PolicyDenied as exc:
            await self.finish_progress(claim, 'failed')
            if isinstance(exc, RepairStop):
                await self.stop(exc.code, str(exc))
            if key is not None:
                self.attempts[key] = {'failed': True}
            if self.task_id:
                await asyncio.to_thread(
                    repository().event, self.task_id, 'tool_blocked',
                    tool=name, message=str(exc),
                )
            return ToolMessage(
                content=str(exc), tool_call_id=call_id, name=name, status='error',
            )
        except ValueError as exc:
            await self.finish_progress(claim, 'failed')
            # A tool's argument/business validation error is feedback for the
            # model, not a reason to abort the whole run.
            if key is not None:
                self.attempts[key] = {'failed': True}
            if self.task_id:
                await asyncio.to_thread(
                    repository().event, self.task_id, 'tool_error',
                    tool=name, message=str(exc),
                )
            return ToolMessage(
                content=f'工具参数或业务校验失败：{exc}', tool_call_id=call_id,
                name=name, status='error',
            )
        except GraphInterrupt:
            await self.finish_progress(claim, 'interrupted')
            raise
        except (httpx.TimeoutException, httpx.NetworkError, TimeoutError, ConnectionError):
            await self.finish_progress(claim, 'retryable')
            raise
        except BaseException:
            # LangGraph interrupts retain their native control-flow semantics.
            raise
        await self.finish_progress(claim, 'failed' if getattr(result, 'status', 'success') == 'error' else 'done')
        if key is not None:
            self.attempts[key] = {
                'failed': getattr(result, 'status', 'success') == 'error',
            }
        flush_seconds, flush_status, flush_error = 0.0, None, None
        if self.task_id:
            repo = repository()
            if hasattr(repo, 'flush'):
                flush_started = time.perf_counter()
                try:
                    await asyncio.to_thread(repo.flush, self.task_id)
                    flush_status = 'success'
                except Exception as exc:  # stay dirty so the next stage retries
                    flush_status = 'error'
                    flush_error = f'{type(exc).__name__}: {exc}'
                flush_seconds = round(time.perf_counter() - flush_started, 3)
        if self.task_id:
            receipt = dict(tool=name, call_id=call_id, revision=self.revision,
                           status=getattr(result, 'status', 'success'),
                           elapsed_seconds=round(time.perf_counter() - started, 3),
                           flush_seconds=flush_seconds)
            if flush_status:
                receipt['flush_status'] = flush_status
            if flush_error:
                receipt['flush_error'] = flush_error
            await asyncio.to_thread(repository().event, self.task_id, 'tool_receipt', **receipt)
        return result
