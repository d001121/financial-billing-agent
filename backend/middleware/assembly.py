"""Shared native middleware ordering for the supervisor and specialists."""

import httpx
from deepagents.middleware.filesystem import FilesystemMiddleware
from deepagents.middleware.skills import SkillsMiddleware
from langchain.agents.middleware import (
    ClearToolUsesEdit,
    ContextEditingMiddleware,
    HumanInTheLoopMiddleware,
    ModelCallLimitMiddleware,
    ModelRetryMiddleware,
    ToolCallLimitMiddleware,
    ToolRetryMiddleware,
)
from openai import (
    APIConnectionError,
    APITimeoutError,
    InternalServerError,
    RateLimitError,
)

from backend.extensions.skill_versions import configured_tools

from .dispatch import DispatchPolicy
from .feedback import RevisionFeedback
from .conversation import ConversationReplies
from .mcp_tools import MCPTools
from .outcome import TaskOutcome
from .question import AskUserPolicy
from .recovery import InvalidToolCallRecovery, ToolArgNormalization, ToolCallIdNormalization
from .reply_decision import ReplyDecisionMiddleware


def base_stack(task_id, revision, cap, backend, business, names=None,
               mcp_tools=None, provenance=None, outcome=False, *, scope=None, allowed_tools=None, call_limits=None):
    limits = call_limits or cap['config']['runtime']
    extensions, owners = configured_tools(cap, names)
    if allowed_tools is not None:
        extensions = [t for t in extensions if t.name in allowed_tools]
        mcp_tools = [t for t in mcp_tools or [] if t.name in allowed_tools]
    stack = [
        MCPTools(mcp_tools or [], provenance or {}),
        ToolCallIdNormalization(),
        AskUserPolicy(task_id),
        HumanInTheLoopMiddleware(
            interrupt_on={'ask_user': {'allowed_decisions': ['respond', 'reject']}},
            interrupt_mode='per_call',
        ),
        ModelRetryMiddleware(
            max_retries=1,
            retry_on=(httpx.TimeoutException, httpx.NetworkError, APITimeoutError,
                      APIConnectionError, RateLimitError, InternalServerError),
        ),
        ToolRetryMiddleware(
            max_retries=1,
            retry_on=(httpx.TimeoutException, httpx.NetworkError,
                      TimeoutError, ConnectionError),
        ),
        DispatchPolicy(task_id, revision, provenance, owners, scope=scope, allowed_tools=allowed_tools),
        RevisionFeedback(task_id, revision),
        InvalidToolCallRecovery(),
        ToolArgNormalization(),
        # One counter instance: LangChain rejects duplicate middleware names and
        # two limit instances would each increment the same state counters.
        # The run limit bounds a repair loop inside one run; the task budget in
        # `consume` stays the authoritative cross-run limit. `end` lets
        # after_agent persist and report the partial result.
        ModelCallLimitMiddleware(
            thread_limit=limits['model_calls'],
            run_limit=limits.get('run_model_calls')
            or max(1, limits['model_calls'] - limits['turn_model_calls']),
            exit_behavior='end',
        ),
        # Native context editing: clear older tool outputs (intake/read_file)
        # while keeping the latest validation and the material files.
        ContextEditingMiddleware(
            edits=[ClearToolUsesEdit(
                trigger=int(limits.get('context_edit_trigger', 8000)),
                keep=int(limits.get('context_edit_keep', 3)),
                exclude_tools=('save_document_extraction', 'prepare_export', 'ask_user'),
                placeholder='[已清理较早的工具输出；材料仍在 /materials 和任务产物中，可重新读取]',
            )],
        ),
        ToolCallLimitMiddleware(
            thread_limit=limits['tool_calls'], exit_behavior='error',
        ),
        FilesystemMiddleware(backend=backend, tools=['read_file', 'ls', 'glob', 'grep']),
        SkillsMiddleware(
            backend=backend, sources=['/skills/'], tools=[*business, *extensions],
        ),
    ]
    if outcome:
        conversation = ConversationReplies(task_id, revision, cap)
        stack.append(TaskOutcome(task_id, revision))
        stack.append(conversation)
        stack.append(ReplyDecisionMiddleware(task_id, revision, cap, conversation.record_tool))
    return stack
