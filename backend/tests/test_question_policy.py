import asyncio
from types import SimpleNamespace

from langchain.messages import ToolMessage

from backend.middleware import question


class FakeRepository:
    def __init__(self, task):
        self.task = task

    def get(self, kind, task_id):
        return self.task


def ask(task, name='ask_user'):
    seen = []

    async def handler(request):
        seen.append(request)
        return 'ran'

    question.repository = lambda: FakeRepository(task)
    request = SimpleNamespace(tool_call={'name': name, 'id': 'call-1', 'args': {}})
    result = asyncio.run(question.AskUserPolicy('task-1').awrap_tool_call(request, handler))
    return result, seen


def test_missing_entity_blocks_ask_user_and_defers_to_host_review():
    result, seen = ask({'accounting_entity': None, 'records': [{'charge_id': 'c1'}]})
    assert not seen
    assert isinstance(result, ToolMessage) and result.status == 'error'
    assert '保存' in result.content and 'conversation_review' in result.content


def test_question_requires_a_saved_candidate_first():
    result, seen = ask({'accounting_entity': 'Demo Ltd', 'records': []})
    assert not seen
    assert 'save_document_extraction' in result.content


def test_question_is_allowed_after_candidate_with_entity():
    result, seen = ask({'accounting_entity': 'Demo Ltd', 'records': [{'charge_id': 'c1'}]})
    assert result == 'ran' and len(seen) == 1


def test_other_tools_are_untouched():
    result, seen = ask({'accounting_entity': None, 'records': []}, name='read_file')
    assert result == 'ran' and len(seen) == 1
