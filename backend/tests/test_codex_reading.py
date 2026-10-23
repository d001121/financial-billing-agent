"""Targeted Codex-style reading and native execution checks, no live OCR/LLM."""
import asyncio
from pathlib import Path
import json

from deepagents.backends import StateBackend
from langchain.agents import create_agent
from langchain_core.messages import ToolMessage
import pytest

from backend.extensions.skill_versions import skill_module, skill_state
from backend.middleware.assembly import base_stack
from backend.agents.supervisor.agent import build_supervisor
from backend.agents.billing.agent import build_billing_agent
from backend.tools import skill_bindings
from backend.tests.test_host import host, offline_model, proposed_call


def extraction(task):
    return skill_module('document-extraction', task['capability']['version'])


def materials():
    return [dict(source_id='mail', format='eml', status='ready', blocks=[dict(
        anchor='mail/body', text='Client pay Carrier: H/C $50')]),
        dict(source_id='pdf', format='pdf', status='ready', blocks=[dict(
            anchor='page:1/layout', page=1, text='B/L         BOOKING\nBL-123      BK-987')])]


def test_short_bundle_all_sources_and_real_refs_without_chunk_gate(host):
    _, _, task = host
    module = extraction(task)
    payload = dict(sources=materials())
    read = module.read_materials(payload)
    assert read['mode'] == 'read'
    assert {c['source_id'] for c in read['content']} == {'mail', 'pdf'}
    refs = module.citation_index(payload)
    rid = next(k for k, ref in refs.items() if 'H/C' in ref['quote'])
    checked = module.validate_extraction(dict(payload, chunks=[dict(chunk_id='old-block')],
        result=dict(charges=[dict(charge_item='H/C', amount=50,
            evidence=[dict(ref_id=rid, fields=['charge_item', 'amount'])])])) )
    assert checked['valid'], checked['issues']
    assert checked['coverage'] == []
    assert checked['charges'][0]['source_id'] == 'mail'
    assert {r['field'] for r in checked['charges'][0]['evidence']} == {'charge_item', 'amount'}


def test_long_bundle_search_then_native_grep_and_batch_windows(host, monkeypatch):
    _, _, task = host
    module = extraction(task)
    lines = [f'运输说明行{i}' for i in range(5000)]
    lines[4321] = 'HANDLING USD 135.25'
    payload = dict(sources=[dict(source_id='long', status='ready', blocks=[dict(
        anchor='page:1', text='\n'.join(lines))])])
    summary = module.read_materials(payload)
    assert summary['mode'] == 'search' and summary['content'] == []
    files = module.markdown_files(payload)
    backend = StateBackend()
    from deepagents.middleware.filesystem import FilesystemMiddleware
    def responder(body):
        messages = body['messages']
        if not any(m.get('role') == 'tool' for m in messages):
            return proposed_call('grep', dict(pattern='HANDLING', path='/materials/',
                                            output_mode='content'), 'search')
        assert '135.25' in messages[-1]['content']
        return dict(role='assistant', content='已定位费用行')
    async def run():
        model, client = offline_model(monkeypatch, None, responder)
        try:
            graph = create_agent(model, tools=[], middleware=[FilesystemMiddleware(backend=backend)])
            return await graph.ainvoke(dict(messages=[dict(role='user', content='定位HANDLING')], files=files))
        finally:
            await client.aclose()
    state = asyncio.run(run())
    assert any(isinstance(m, ToolMessage) and '135.25' in m.content for m in state['messages'])
    read = module.read_materials(dict(payload, windows=[dict(source_id='long', start_line=4321, end_line=4324)]))
    assert 'HANDLING USD 135.25' in read['content'][0]['text']
    assert not read['content'][0]['truncated']
    with pytest.raises(ValueError):
        module.read_materials(dict(payload, windows=[dict(source_id='long', start_line=6000)]))


def test_empty_source_and_truncation_are_explicit(host):
    _, _, task = host
    module = extraction(task)
    empty = module.read_materials(dict(sources=[dict(source_id='empty', blocks=[])]))
    assert empty['content'][0]['text'] == ''
    assert empty['materials'][0]['total_lines'] == 0
    payload = dict(sources=materials(), max_chars=1000)
    payload['sources'][0]['blocks'][0]['text'] = 'x' * 1100
    result = module.read_materials(dict(payload, windows=[dict(source_id='mail')]))
    assert result['content'][0]['truncated'] and result['content'][0]['next_line'] == 1


def test_refs_restore_original_pdf_spacing_and_reject_forgery(host):
    _, _, task = host
    module = extraction(task)
    payload = dict(sources=materials())
    refs = module.citation_index(payload)
    rid = next(k for k, r in refs.items() if r['quote'].startswith('BL-123'))
    checked = module.validate_extraction(dict(payload, result=dict(charges=[dict(
        charge_item='TEST', evidence=[dict(ref_id=rid, fields=['bill_of_lading'], quote='forged')])])) )
    ref = checked['charges'][0]['evidence'][0]
    assert ref['quote'] == 'BL-123      BK-987' and ref['page'] == 1
    text = payload['sources'][1]['blocks'][0]['text']
    assert text[ref['quote_start']:ref['quote_end']] == ref['quote']
    forged = module.validate_extraction(dict(payload, result=dict(charges=[dict(
        evidence=[dict(ref_id='r0000000000000000')])])) )
    assert not forged['valid'] and any(i['code'] == 'CITATION_UNKNOWN' for i in forged['issues'])


def test_cross_source_support_without_identity_proof_table(host):
    _, _, task = host
    module = skill_module('evidence-linking', task['capability']['version'])
    payload = dict(sources=[dict(source_id='mail', text='Handling 50'),
        dict(source_id='invoice', text='Currency USD')], charges=[dict(
            charge_id='c', source_id='mail', charge_item='Handling', amount=50, currency='USD',
            evidence=[dict(source_id='mail', anchor='text', quote='Handling 50', field='amount'),
                      dict(source_id='invoice', anchor='text', quote='Currency USD', field='currency')])])
    result = module.link_evidence(payload)
    assert result['valid'], result['issues']
    assert all(r['verified'] for r in result['charges'][0]['evidence'])


def test_feedback_is_bounded_and_deduplicated(host):
    _, _, task = host
    module = extraction(task)
    issues = [dict(code=f'E{i}', message='具体误读', field='amount', checks=['x' * 10000]) for i in range(40)]
    result = module.compact_feedback(dict(ok=False, issues=issues * 3))
    assert len(result['issues']) == 12 and result['issue_count'] == 40
    assert result['more_issues'] == 28 and len(json.dumps(result)) < 2000


@pytest.mark.parametrize('entity', [None, 'Client'])
def test_native_short_extraction_opens_entity_review(host, monkeypatch, entity):
    repo, _, task = host
    def start(t):
        t.update(status='running', accounting_entity=entity, sources=materials(), chunks=[],
                 charges=[], records=[], coverage=[], extraction=None)
    repo.mutate('task', task['id'], start)
    module = extraction(task)
    refs = module.citation_index(dict(sources=materials()))
    rid = next(k for k, r in refs.items() if 'H/C' in r['quote'])
    calls = []
    def respond(body):
        calls.append(body)
        if len(calls) == 1:
            return proposed_call('read_materials', {}, 'read')
        if len(calls) == 2:
            assert 'H/C' in body['messages'][-1]['content'] and 'BK-987' in body['messages'][-1]['content']
            return proposed_call('save_document_extraction', dict(result=dict(charges=[dict(
                line_id='fee1', charge_item='H/C', raw_charge_item='H/C', amount=50, raw_amount='50',
                raw_currency='$', creditor='Carrier', debtor='Client',
                evidence=[dict(ref_id=rid, fields=['charge_item', 'amount', 'creditor', 'debtor'])])])), 'save')
        assert len(body['messages'][-1]['content']) < 6000
        assert len(calls) == 3
        receipt = json.loads(body['messages'][-1]['content'])
        assert receipt['verification']['revision'] == 1
        return dict(role='assistant', content='已提取H/C金额50；币种和记账主体未知，结果可查看修改。')
    async def run():
        model, client = offline_model(monkeypatch, task['id'], respond)
        try:
            common, business = skill_bindings.tools_for(task['id'], task['capability'])
            backend = StateBackend()
            stack = base_stack(task['id'], 1, task['capability'], backend, business, outcome=True)
            graph = build_supervisor(model, common, backend, stack, [])
            return await graph.ainvoke({**skill_state(task['capability'], repo.get('task', task['id'])),
                'messages': [dict(role='user', content='提取本次材料')]},
                config={'recursion_limit': 512})
        finally:
            await client.aclose()
    state = asyncio.run(run())
    saved = repo.get('task', task['id'])
    interrupt = (state.get('__interrupt__') or [None])[0]
    if entity is None:
        assert interrupt and interrupt.value.get('kind') == 'conversation_review'
        assert interrupt.value.get('choices') == ['Carrier', 'Client']
        assert saved['status'] == 'awaiting_input'
    else:
        assert interrupt is None
        assert saved['status'] == 'completed_with_gaps'
        assert saved['export'] is not None
    assert saved['records'][0]['charge_details']['amount'] == 50
    assert saved['records'][0]['charge_details']['currency'] is None
    assert saved['records'][0]['financial_attributes']['posting_type'] == (None if entity is None else 'AP')
    assert saved['records'][0]['financial_attributes']['accounting_entity'] == entity
    assert saved['records'][0]['operation'] == 'PENDING_REVIEW'
    assert len(calls) == 3 and saved['usage']['model_calls'] == 3
    assert [m.name for m in state['messages'] if isinstance(m, ToolMessage)] == [
        'read_materials', 'save_document_extraction']
    assert saved['approval'] is None


def test_archived_real_four_source_bundle_reads_once_and_refs_are_exact(host):
    path = Path(__file__).parent / 'reports' / 'codex-reading-source-replay.json'
    if not path.exists():
        pytest.skip('Archived local material is not part of a portable test distribution')
    _, _, task = host
    module = extraction(task)
    payload = json.loads(path.read_text(encoding='utf-8'))
    read = module.read_materials(payload)
    assert read['mode'] == 'read' and len(read['content']) == 4
    assert all(not row['truncated'] for row in read['content'])
    blocks = {(s['source_id'], b['anchor']): b['text'] for s in payload['sources'] for b in s['blocks']}
    refs = module.citation_index(payload)
    assert len(refs) > 300
    assert any('pay' in ref['quote'] and '50' in ref['quote'] for ref in refs.values())
    for ref in refs.values():
        assert blocks[ref['source_id'], ref['anchor']][ref['quote_start']:ref['quote_end']] == ref['quote']


def test_optional_verifier_reads_only_the_delegated_question(host, monkeypatch):
    repo, _, task = host
    seen = []
    def respond(body):
        seen.append(body)
        system = str([m['content'] for m in body['messages'] if m['role'] in ('system', 'developer')])
        if '按需调用的账单核验专家' in system:
            assert 'H/C $50' in str(body['messages'])
            return dict(role='assistant', content='费用为H/C，金额50；裸$无法唯一确定币种，保持null。')
        if body['messages'][-1]['role'] == 'tool':
            assert '裸$' in body['messages'][-1]['content']
            return dict(role='assistant', content='已按原文保留未知币种。')
        return proposed_call('task', dict(subagent_type='billing-specialist',
            description='仅核验候选H/C金额50币种USD。原文Client pay Carrier: H/C $50；判断币种是否有依据。'), 'verify')
    async def run():
        model, client = offline_model(monkeypatch, task['id'], respond)
        try:
            cap = task['capability']
            spec = next(s for s in cap['config']['agents']['agents'] if s['name'] == 'billing-specialist')
            child_backend = StateBackend()
            common, business = skill_bindings.tools_for(task['id'], cap, spec['skills'])
            child = build_billing_agent(model, common,
                base_stack(task['id'], 1, cap, child_backend, business, spec['skills']), spec['prompt'], spec['name'])
            backend = StateBackend()
            parent_common, parent_business = skill_bindings.tools_for(task['id'], cap)
            graph = build_supervisor(model, parent_common, backend,
                base_stack(task['id'], 1, cap, backend, parent_business),
                [dict(name=spec['name'], description=spec['description'], runnable=child)])
            return await graph.ainvoke({**skill_state(cap, repo.get('task', task['id'])),
                'messages': [dict(role='user', content='核验一个具体疑点')]},
                config={'recursion_limit': 512})
        finally:
            await client.aclose()
    state = asyncio.run(run())
    assert not state.get('__interrupt__') and len(seen) == 3
    assert repo.get('task', task['id'])['usage']['model_calls'] == 3
    receipts = [r for r in repo.receipts if r['event'] == 'tool_receipt']
    assert [r['tool'] for r in receipts] == ['task']
