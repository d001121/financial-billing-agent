"""Automatic history retrieval: pure domain checks, no database or model."""
import importlib.util
from copy import deepcopy
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location('history_skill', Path(__file__).parents[1] / 'scripts/skill.py')
skill = importlib.util.module_from_spec(spec)
spec.loader.exec_module(skill)


def charge(**more):
    return dict(charge_id='c1', source_id='invoice', reference_no='INV-1',
                charge_item='THC', amount='100', currency='USD', issuer='Carrier',
                recipient='Client', creditor='Carrier', debtor='Client',
                evidence=[dict(source_id='invoice', anchor='p1', quote='THC USD 100', verified=True)], **more)


def saved(task_id='old', **more):
    row = skill.reconcile_charges(dict(charges=[charge()], existing_records=[],
        accounting_entity='Client', revision=1))['records'][0]
    return dict(id=task_id, revision=1, accounting_entity='Client', status='completed',
        updated_at='2026-10-23T01:00:00Z', validation=dict(ok=True, revision=1),
        records=[row], **more)


def task(**more):
    return dict(id='new', revision=1, accounting_entity='Client',
                history_mode='automatic', charges=[charge()], **more)


def retrieve(current, rows):
    assert callable(getattr(skill, 'retrieve_history', None)), 'automatic history retrieval is missing'
    return skill.retrieve_history(dict(task=current, historical_tasks=rows))


def test_history_automatically_distinguishes_create_and_duplicate():
    current = task()
    before = deepcopy(current)
    empty = retrieve(current, [])
    assert skill.reconcile_charges({**current, **empty})['records'][0]['operation'] == 'CREATE'
    found = retrieve(current, [saved()])
    result = skill.reconcile_charges({**current, **found})
    assert result['records'][0]['operation'] == 'NO_CHANGE'
    assert found['history_lookup']['candidate_count'] == 1
    assert result['records'][0]['history_match']['task_id'] == 'old'
    assert current == before


@pytest.mark.parametrize('change', [dict(accounting_entity='Other'), dict(status='running'),
    dict(deleted_at='2026-10-23'), dict(validation=dict(ok=False, revision=1)),
    dict(validation=dict(ok=True, revision=0)), dict(approval=dict(decision='reject'))])
def test_history_rejects_unusable_or_other_entity_tasks(change):
    history = saved()
    history.update(change)
    assert not retrieve(task(), [history])['existing_records']


def test_self_missing_entity_and_same_named_multiple_rows():
    own = saved('new')
    assert not retrieve(task(), [own])['existing_records']
    current = task()
    current['accounting_entity'] = None
    assert retrieve(current, [saved()])['history_lookup']['status'] == 'waiting_entity'
    result = retrieve(task(), [saved('a'), saved('b')])
    assert len(result['existing_records']) == 2
    checked = skill.reconcile_charges({**task(), **result})
    assert checked['records'][0]['operation'] == 'PENDING_REVIEW'
    assert any(i['code'] == 'AMBIGUOUS_MATCH' for i in checked['issues'])


def test_amount_update_keeps_other_values_and_latest_lineage():
    old = saved()
    old['records'][0]['charge_details']['payment_term'] = 'CC'
    current = task()
    current['charges'][0]['amount'] = '120'
    current['charges'][0]['evidence'][0]['quote'] = 'THC USD 120'
    found = retrieve(current, [old])
    denied = skill.reconcile_charges({**current, **found})
    assert denied['records'][0]['operation'] == 'PENDING_REVIEW'
    updated = skill.reconcile_charges({**current, **found, 'update_instructions': [
        dict(reference_no='INV-1', charge_item='THC', changes=dict(amount='120'))]})
    row = updated['records'][0]
    assert row['operation'] == 'UPDATE', updated['issues']
    assert row['charge_details']['payment_term'] == 'CC'
    newer = saved('updated')
    newer.update(records=[row], updated_at='2026-10-23T02:00:00Z')
    latest = retrieve(current, [newer, old])
    assert len(latest['existing_records']) == 1
    assert str(latest['existing_records'][0]['amount']) == '120'
    assert latest['existing_records'][0]['history_source']['task_id'] == 'updated'
    duplicate = saved('duplicate')
    duplicate['records'][0].update(operation='NO_CHANGE')
    assert len(retrieve(current, [newer, old, duplicate])['existing_records']) == 1


def test_history_uses_all_matching_tiers_and_normalized_names():
    current = task()
    current['charges'][0].update(reference_no=None, bill_of_lading='BL1')
    old = saved()
    old['records'][0]['bill_of_lading'] = 'BL1'
    assert retrieve(current, [old])['history_lookup']['candidate_count'] == 1
    current['charges'][0].update(bill_of_lading=None, booking_no='BK1')
    old['records'][0]['booking_no'] = 'BK1'
    assert retrieve(current, [old])['history_lookup']['candidate_count'] == 1
    current['charges'][0].update(booking_no=None, container_no='BOX1', document_date='2026-10-01')
    old['records'][0].update(container_no='BOX1')
    old['records'][0]['document_info']['document_date'] = '2026-10-01'
    assert retrieve(current, [old])['history_lookup']['candidate_count'] == 1


def test_missing_or_stale_history_cannot_pass_matching_gate():
    current = task()
    current['existing_records'] = []
    assert not skill.validate_matching(current)['valid']
    found = retrieve(current, [])
    current.update(found)
    current['current_history_lookup'] = retrieve(current, [saved()])['history_lookup']
    assert any(i['code'] == 'HISTORY_STALE' for i in skill.validate_matching(current)['issues'])


def test_no_first_hundred_cutoff_and_unrelated_rows_do_not_enter_context():
    rows = []
    for index in range(125):
        row = saved(str(index))
        row['records'][0]['document_info']['reference_no'] = f'OTHER-{index}'
        rows.append(row)
    rows.append(saved('wanted'))
    result = retrieve(task(), rows)
    assert result['history_lookup']['scanned_tasks'] == 126
    assert len(result['existing_records']) == 1
    assert result['existing_records'][0]['history_source']['task_id'] == 'wanted'


def test_history_links_are_derived_and_multiple_new_lines_cannot_reuse_one_old_row():
    current = task()
    current['charges'][0].update(history_identity='forged', history_match=dict(task_id='other'))
    result = skill.reconcile_charges({**current, **retrieve(current, [])})
    assert 'history_identity' not in result['records'][0]
    current['charges'].append(deepcopy(current['charges'][0]))
    current['charges'][1].update(charge_id='c2', line_id='line2')
    found = retrieve(current, [saved()])
    checked = skill.reconcile_charges({**current, **found})
    assert all(r['operation'] == 'PENDING_REVIEW' for r in checked['records'])
    assert any(i['code'] == 'MATCH_REUSED' for i in skill.validate_matching({**current, **found})['issues'])


def test_competing_updates_remain_ambiguous_instead_of_last_writer_winning():
    current = task()
    baseline = saved()
    found = retrieve(current, [baseline])
    siblings = []
    for index, amount in enumerate(('120', '140')):
        result = skill.reconcile_charges({**current, **found, 'update_instructions': [
            dict(reference_no='INV-1', charge_item='THC', changes=dict(amount=amount))]})
        row = saved(f'branch-{index}')
        row['records'] = result['records']
        siblings.append(row)
    latest = retrieve(current, [baseline, *siblings])
    assert len(latest['existing_records']) == 2
    assert not skill.validate_matching({**current, **latest})['valid']
