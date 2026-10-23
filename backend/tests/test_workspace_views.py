"""Business summaries stay separate from financial decisions and native traces."""
from copy import deepcopy
from decimal import Decimal
import asyncio
from types import SimpleNamespace

from fastapi.testclient import TestClient

from backend.api import app
from backend.api.read_models import bill_projection, call_path
from backend.api.routes import observability


def test_list_resolves_real_native_interrupts_without_rewriting_stored_status(monkeypatch):
    stored = [dict(id='t', thread_id='thread', status='processing', control='running')]
    rows = deepcopy(stored)
    class Threads:
        async def get_state(self, thread_id, **kwargs):
            return dict(tasks=[dict(interrupts=[dict(id='question-id', value=dict(name='ask_user', args=dict(question='请确认币种')))])])
        async def search(self, **kwargs):
            assert kwargs['ids'] == ['thread']
            assert kwargs['select'] == ['thread_id', 'status', 'interrupts']
            return [dict(thread_id='thread', status='interrupted', interrupts={'tools:ns': [dict(
                id='question-id', value=dict(name='ask_user', args=dict(question='请确认币种')))]})]
    monkeypatch.setattr(observability, 'sdk', lambda: SimpleNamespace(threads=Threads()))
    result = asyncio.run(observability.live_status(rows))
    assert result[0]['status'] == 'awaiting_input'
    assert result[0]['pending_questions'] == ['请确认币种']
    assert stored[0]['status'] == 'processing'


def test_list_uses_current_checkpoint_question_instead_of_stale_thread_summary(monkeypatch):
    class Threads:
        async def search(self, **kwargs):
            return [dict(thread_id='thread', status='idle', interrupts={'old': [dict(
                id='old', value=dict(args=dict(question='旧主体问题')))]})]
        async def get_state(self, thread_id, **kwargs):
            return dict(tasks=[dict(interrupts=[dict(id='new', value=dict(
                kind='conversation_review', args=dict(question='当前收付款角色问题')))])])
    monkeypatch.setattr(observability, 'sdk', lambda: SimpleNamespace(threads=Threads()))
    result = asyncio.run(observability.live_status([dict(id='t', thread_id='thread', status='awaiting_input')]))
    assert result[0]['pending_questions'] == ['当前收付款角色问题']


def test_current_review_summary_does_not_load_checkpoint_messages(monkeypatch):
    class Threads:
        async def search(self, **kwargs):
            return [dict(thread_id='thread', status='interrupted', interrupts={'ns':[dict(
                id='question', value=dict(request_id='review', revision=2, description='当前问题'))]})]
        async def get_state(self, *args, **kwargs):
            raise AssertionError('current summary must not load full checkpoint messages')
    monkeypatch.setattr(observability, 'sdk', lambda: SimpleNamespace(threads=Threads()))
    result = asyncio.run(observability.live_status([dict(id='t', thread_id='thread', revision=2,
        review_request=dict(id='review', revision=2, state='pending'))]))
    assert result[0]['pending_questions']==['当前问题']


def test_idle_thread_does_not_approve_bill_and_missing_thread_is_visible(monkeypatch):
    class Threads:
        async def search(self, **kwargs):
            return [dict(thread_id='idle', status='idle', interrupts={})]
    monkeypatch.setattr(observability, 'sdk', lambda: SimpleNamespace(threads=Threads()))
    result = asyncio.run(observability.live_status([
        dict(id='a', thread_id='idle', status='processing'), dict(id='b', thread_id='missing', status='processing')]))
    assert result[0]['status'] == 'incomplete'
    assert result[1]['status'] == 'recovery_required'


def test_bill_summary_keeps_one_submission_and_separate_amounts_without_summing():
    task = dict(id='eml-bundle', revision=2, status='awaiting_input', asset_ids=['mail'],
        records=[dict(document_info={'reference_no': 'INV-7'}, transaction_party={'issuer': 'Carrier'},
                      charge_details={'amount': Decimal('10'), 'currency': 'USD'}),
                 dict(document_info={'reference_no': 'INV-7'}, transaction_party={'issuer': 'Carrier'},
                      charge_details={'amount': Decimal('20'), 'currency': 'EUR'})],
        sources=[dict(source_id='mail', format='eml', name='mail.eml'),
                 dict(source_id='pdf', parent_source_id='mail', name='invoice.pdf')],
        issues=[dict(code='MISSING', message='请补充收费关系')],
        validation=dict(issues=[dict(code='MISSING', message='请补充收费关系')]))
    original = deepcopy(task)
    result = bill_projection(task)
    assert task == original
    assert result['bill']['id'] == 'eml-bundle'
    assert result['bill']['references'] == ['INV-7']
    assert result['bill']['material_count'] == 2
    assert result['bill']['materials'][1]['parent_source_id'] == 'mail'
    assert result['record_count'] == 2 and result['issue_count'] == 1
    assert result['bill']['amounts'] == [{'amount': Decimal('10'), 'currency': 'USD'},
                                         {'amount': Decimal('20'), 'currency': 'EUR'}]
    assert 'total' not in result['bill']


def test_native_call_projection_does_not_invent_internal_spans():
    state = dict(values={'messages': [{'tool_calls': [dict(id='delegate', name='task', args={
        'subagent_type': 'document-specialist'})]}]}, tasks=[dict(id='native-node', name='tools',
        state={'values': {'messages': [{'tool_calls': [dict(id='parse', name='intake_documents')]}]}})])
    path = call_path(state)
    assert [call['call_id'] for call in path] == ['delegate', 'parse']
    assert path[0]['agent'] == 'document-specialist'
    assert call_path({'values': {'messages': []}}) == []


def test_trace_metrics_count_manual_corrections_separately_and_never_invent_accuracy(monkeypatch):
    class Store:
        def list_projection(self, *args, **kwargs):
            return [dict(id='corrected', status='awaiting_review'), dict(id='confirmed', status='approved')]
        def event_counts(self, ids):
            return {'corrected': {'human_revision': 2}, 'confirmed': {'approval': 1}}
    monkeypatch.setattr(observability, 'repository', Store)
    data = TestClient(app).get('/api/traces').json()
    assert data['sample_size'] == 2
    assert data['human']['revision_ratio'] == .5
    assert data['human']['confirmation_tasks'] == 1
    assert data['quality']['accuracy'] is None
    assert data['quality']['false_positive_rate'] is None
    assert data['quality']['false_negative_rate'] is None
