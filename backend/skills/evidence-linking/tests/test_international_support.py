"""Synthetic no-template shipping values, not real-document accuracy labels."""
from copy import deepcopy
from decimal import Decimal
import importlib.util
from pathlib import Path
import subprocess
import sys

import pytest
import simplejson


PACKAGE = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('_international_evidence', PACKAGE / 'scripts' / 'skill.py')
skill = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(skill)


@pytest.mark.parametrize('repeat', [False, True])
def test_normalized_and_raw_names_at_same_location_are_one_occurrence(repeat):
    text = 'Waybill OCA17 On Carriage Additional - US Em USD 245'
    if repeat:
        text += '\n' + text
    row = dict(charge_item='OCA17 On Carriage Additional - US',
        raw_charge_item='OCA17 On Carriage Additional - US Em', evidence=[dict(
            field='charge_item', verified=True, source_id='s', anchor='line',
            content_sha256='hash', quote_start=0, quote_end=len(text), quote=text)])
    fact = skill.field_support(row, 'charge_item')
    assert fact['status'] == ('ambiguous' if repeat else 'supported')
    if not repeat:
        assert len(fact['targets']) == 1


def payload_for(raw, value, currency='USD', currency_text=None):
    text = f'Amount {currency_text or currency} {raw}'
    return dict(revision=3, sources=[dict(source_id='document', blocks=[dict(
        anchor='line', text=text, page=4, authoritative=True)])], charges=[dict(
            charge_id='c1', source_id='document', line_id='line', amount=Decimal(value),
            currency=currency, raw_currency=(currency_text or currency),
            evidence=[dict(source_id='document', anchor='line', quote=text, field=field)
                      for field in ('amount', 'currency')])])


@pytest.mark.parametrize(('raw', 'value'), [
    ('1.234,56', '1234.56'), ('1,234.56', '1234.56'), ('1 234,56', '1234.56'),
    ('1\u00a0234,56', '1234.56'), ('1\u202f234,56', '1234.56'), ("1'234.56", '1234.56'),
    ('1’234.56', '1234.56'), ('1,23,456.78', '123456.78'), ('12,34,567', '1234567'),
    ('１，２３４．５６', '1234.56'), ('١٬٢٣٤٫٥٦', '1234.56'), ('١٢٫٣٤٥', '12.345'),
    ('١٬٢٣٤', '1234'), ('(1.234,56)', '-1234.56'), ('−50.25', '-50.25'),
    ('12.3456', '12.3456'), ('0.125', '0.125'), ('1.234.567', '1234567'),
])
def test_supported_international_amounts_keep_original_spans(raw, value):
    task = payload_for(raw, value)
    before = deepcopy(task)
    result = skill.validate_evidence(task)
    assert result['valid'], result['issues']
    assert result['field_support_contract'] == 'source_support_v2'
    fact = result['charges'][0]['field_support']['amount']
    assert fact['value'] == Decimal(value) and fact['score'] == 100 and fact['status'] == 'supported'
    target = fact['targets'][0]
    source_text = task['sources'][0]['blocks'][0]['text']
    assert source_text[target['value_start']:target['value_end']] == raw
    assert target['page'] == 4 and 'bbox' not in target
    assert task == before


@pytest.mark.parametrize(('raw', 'value', 'expected'), [
    ('1,234', '1234', {'1.234', '1234'}), ('1,234', '1.234', {'1.234', '1234'}),
    ('1.234', '1234', {'1.234', '1234'}), ('1.234', '1.234', {'1.234', '1234'}),
])
def test_three_digit_separator_is_not_disambiguated_by_the_model_value(raw, value, expected):
    result = skill.validate_evidence(payload_for(raw, value))
    assert not result['valid']
    fact = result['charges'][0]['field_support']['amount']
    assert fact['status'] == 'ambiguous' and fact['ambiguity_kind'] == 'format'
    assert set(fact['observations'][0]['candidates']) == expected
    assert any(issue['code'] == 'FIELD_VALUE_AMBIGUOUS' for issue in result['issues'])


@pytest.mark.parametrize('raw', ['1,23,4.56', '12 34,56', "1'23.45", '1,234,56', '1.2.3', '50O', '1,23x'])
def test_malformed_tokens_are_never_repaired_or_partially_matched(raw):
    result = skill.validate_evidence(payload_for(raw, '4.56'))
    assert not result['valid']
    assert result['charges'][0]['field_support']['amount']['status'] == 'unsupported'


def test_adjacent_layout_columns_split_while_grouped_numbers_stay_whole():
    assert [token['raw'] for token in skill.numeric_tokens('1 234,56')] == ['1 234,56']
    assert [token['raw'] for token in skill.numeric_tokens('65.00  1.00')] == ['65.00', '1.00']


def test_layout_amount_column_owns_the_support_not_the_rate_or_quantity():
    row = 'HANDLING CHARGE                        -    65.00  1.00  C      65.00'

    def support(value):
        charge = dict(charge_details={'amount': Decimal(value)}, evidence=[dict(
            field='amount', verified=True, source_id='doc', anchor='page:1/layout/financial',
            kind='pdf_layout_financial', quote=row, quote_start=0, content_sha256='hash')])
        return skill.field_support(charge, 'amount')

    fact = support('65')
    assert fact['status'] == 'supported' and fact['score'] == 100
    assert [item['raw'] for item in fact['observations']] == ['65.00']
    target = fact['targets'][0]
    assert row[target['value_start']:target['value_end']] == '65.00'
    assert support('1.00')['status'] == 'unsupported'


@pytest.mark.parametrize(('text', 'currency'), [
    ('US$', 'USD'), ('CA$', 'CAD'), ('AU$', 'AUD'), ('A$', 'AUD'), ('NZ$', 'NZD'),
    ('HK$', 'HKD'), ('SG$', 'SGD'), ('S$', 'SGD'), ('CN¥', 'CNY'), ('JP¥', 'JPY'), ('€', 'EUR'),
])
def test_currency_support_uses_only_qualified_unambiguous_symbols(text, currency):
    result = skill.validate_evidence(payload_for('50', '50', currency, text))
    assert result['valid'], result['issues']
    assert result['charges'][0]['field_support']['currency']['status'] == 'supported'


@pytest.mark.parametrize(('text', 'currency'), [('$', 'USD'), ('¥', 'JPY'), ('￥', 'CNY'),
                                               ('kr', 'SEK'), ('Rs', 'INR')])
def test_symbol_plus_context_can_recommend_a_currency(text, currency):
    task = payload_for('50', '50', currency, text)
    task['charges'][0].update(issuer='United States Shipping', country='US', language='en-US')
    result = skill.validate_evidence(task)
    fact = result['charges'][0]['field_support']['currency']
    assert fact['status'] == 'recommended' and fact['score'] == 40
    assert '推荐' in fact['reasons'][0]


@pytest.mark.parametrize(('text', 'currency'), [('¥', 'USD'), ('€', 'USD'), ('£', 'USD')])
def test_symbol_must_match_the_recommended_iso(text, currency):
    task = payload_for('50', '50', currency, text)
    result = skill.validate_evidence(task)
    assert not result['valid']
    fact = result['charges'][0]['field_support']['currency']
    assert fact['status'] in {'ambiguous', 'unsupported'}


@pytest.mark.parametrize(('text', 'currency'), [('Euro', 'EUR'), ('Euros', 'EUR'),
    ('US Dollar', 'USD'), ('US Dollars', 'USD'), ('Canadian Dollars', 'CAD'),
    ('Indian Rupees', 'INR'), ('人民币', 'CNY'), ('欧元', 'EUR'), ('日元', 'JPY'),
    ('Chinese Yuan', 'CNY'), ('Japanese Yen', 'JPY')])
def test_unique_official_full_names_and_bounded_local_names_are_source_evidence(text, currency):
    result = skill.validate_evidence(payload_for('50', '50', currency, text))
    assert result['valid'], result['issues']
    assert result['charges'][0]['field_support']['currency']['status'] == 'supported'


@pytest.mark.parametrize(('text', 'currency'), [('Dollar', 'USD'), ('Dollars', 'CAD'),
    ('Pound', 'GBP'), ('Rupees', 'INR'), ('Eurozone Freight', 'EUR')])
def test_generic_names_and_substrings_do_not_establish_a_currency(text, currency):
    result = skill.validate_evidence(payload_for('50', '50', currency, text))
    assert not result['valid']
    assert result['charges'][0]['field_support']['currency']['status'] != 'supported'


def test_lowercase_iso_is_supported_without_treating_prose_all_as_another_currency():
    task = payload_for('50', '50', 'USD', 'usd')
    text = 'Amount usd 50, pay all charges'
    task['sources'][0]['blocks'][0]['text'] = text
    task['charges'][0]['evidence'] = [dict(source_id='document', anchor='line', quote=text)]
    result = skill.validate_evidence(task)
    assert result['valid'], result['issues']
    for prose in ('All amounts in USD', 'Please try to pay USD 50'):
        tokens = skill.currency_tokens(prose)
        assert [token['value'] for token in tokens] == ['USD']


@pytest.mark.parametrize('quote', ['All', 'All amounts in USD'])
def test_candidate_all_does_not_turn_ordinary_source_word_into_currency(quote):
    task = dict(sources=[dict(source_id='document', text=quote)], charges=[dict(
        charge_id='c1', currency='ALL', evidence=[dict(source_id='document', quote=quote, field='currency')])])
    result = skill.validate_evidence(task)
    assert not result['valid']
    assert result['charges'][0]['field_support']['currency']['status'] == 'unsupported'


@pytest.mark.parametrize('code', ['ALL', 'TRY', 'TOP', 'PEN', 'MAD', 'MOP', 'GEL', 'CUP', 'BOB'])
def test_code_word_case_requires_source_currency_label_for_lowercase(code):
    assert skill.currency_tokens(code.lower()) == []
    assert skill.currency_tokens(code.title()) == []
    assert [token['value'] for token in skill.currency_tokens(code)] == [code]
    for labelled in (f'Currency: {code.lower()}', f'ccy={code.title()}', f'币种：{code.lower()}'):
        assert [token['value'] for token in skill.currency_tokens(labelled)] == [code]


def test_field_references_distinguish_equal_unit_price_and_line_amount():
    text = 'Quantity 1 | Unit price USD 20 | Amount USD 20'
    task = payload_for('20', '20')
    task['sources'][0]['blocks'][0]['text'] = text
    charge = task['charges'][0]
    charge.update(quantity=Decimal(1), unit_price=Decimal(20), evidence=[dict(
        source_id='document', anchor='line', quote=quote, field=field,
        quote_start=text.index(quote)) for field, quote in {
            'quantity': 'Quantity 1', 'unit_price': 'Unit price USD 20',
            'amount': 'Amount USD 20', 'currency': 'Amount USD 20'}.items()])
    result = skill.validate_evidence(task)
    assert result['valid'], result['issues']
    support = result['charges'][0]['field_support']
    assert all(support[field]['status'] == 'supported' for field in ('amount', 'quantity', 'unit_price'))
    assert support['amount']['targets'][0]['value_start'] != support['unit_price']['targets'][0]['value_start']
    charge['evidence'] = [dict(source_id='document', anchor='line', quote=text)]
    broad = skill.validate_evidence(task)
    assert not broad['valid']  # Approval cannot bypass unresolved source attribution.
    assert broad['charges'][0]['field_support']['amount']['ambiguity_kind'] == 'location'
    assert any(issue['code'] == 'FIELD_VALUE_AMBIGUOUS' for issue in broad['issues'])


def test_explicit_source_conflict_is_not_erased_by_a_second_matching_quote():
    task = payload_for('50', '50')
    task['sources'][0]['blocks'].append(dict(anchor='other', text='Amount USD 60'))
    task['charges'][0]['evidence'].append(dict(source_id='document', anchor='other', quote='Amount USD 60', field='amount'))
    result = skill.validate_evidence(task)
    fact = result['charges'][0]['field_support']['amount']
    assert not result['valid'] and fact['status'] == 'unsupported' and fact['conflict']


def test_only_quantity_reference_cannot_hide_missing_amount_currency_evidence():
    text = 'INV-1 THC USD 1,234 QTY 2'
    task = dict(revision=1, sources=[dict(source_id='document', text=text)], charges=[dict(
        charge_id='c1', amount=Decimal(1234), currency='USD', charge_item='THC', quantity=2,
        unit_price=Decimal(617), evidence=[dict(source_id='document', quote='QTY 2', field='quantity')])])
    assert skill.link_evidence(task)['valid']  # Pure citation read-back still succeeds.
    result = skill.validate_evidence(task)
    assert not result['valid']
    assert {issue['field'] for issue in result['issues'] if issue['code'] == 'FIELD_VALUE_UNSUPPORTED'} == {
        'amount', 'currency', 'charge_item'}
    assert all(result['charges'][0]['field_support'][field]['status'] == 'unavailable'
               for field in ('amount', 'currency', 'charge_item'))


def test_wrong_charge_name_is_a_hard_error_even_if_amount_and_currency_are_supported():
    task = payload_for('50', '50')
    text = 'THC Amount USD 50'
    task['sources'][0]['blocks'][0]['text'] = text
    task['charges'][0].update(charge_item='Storage Fee', evidence=[dict(
        source_id='document', anchor='line', quote=text)])
    result = skill.validate_evidence(task)
    assert not result['valid']
    assert result['charges'][0]['field_support']['amount']['status'] == 'supported'
    assert any(issue['code'] == 'FIELD_VALUE_UNSUPPORTED' and issue['field'] == 'charge_item'
               for issue in result['issues'])


def test_identical_word_cells_are_distinct_physical_facts_by_original_anchor():
    task = dict(revision=1, sources=[dict(source_id='word', blocks=[
        dict(anchor='unit-cell', text='50'), dict(anchor='amount-cell', text='50'),
        dict(anchor='total-cell', text='50'), dict(anchor='currency', text='USD')])],
        charges=[dict(charge_id='c1', amount=Decimal(50), unit_price=Decimal(50), currency='USD', evidence=[
            dict(source_id='word', anchor=anchor, quote=quote, field=field) for field, anchor, quote in (
                ('amount', 'amount-cell', '50'), ('unit_price', 'unit-cell', '50'), ('currency', 'currency', 'USD'))])],
        totals=[dict(source_id='word', amount=Decimal(50), currency='USD', evidence=[
            dict(source_id='word', anchor='total-cell', quote='50', field='amount'),
            dict(source_id='word', anchor='currency', quote='USD', field='currency')])])
    result = skill.validate_evidence(task)
    assert result['valid'], result['issues']
    facts = result['charges'][0]['field_support']
    amount, unit = [facts[field]['targets'][0] for field in ('amount', 'unit_price')]
    total = result['total_evidence'][0]['field_support']['amount']['targets'][0]
    assert amount['content_sha256'] == unit['content_sha256'] == total['content_sha256']
    assert {amount['anchor'], unit['anchor'], total['anchor']} == {'amount-cell', 'unit-cell', 'total-cell'}
    # Different cells cannot be collapsed if both are cited for a single field without ownership.
    task['charges'][0]['evidence'] = [dict(source_id='word', anchor=anchor, quote='50')
                                     for anchor in ('amount-cell', 'total-cell')]
    result = skill.validate_evidence(task)
    assert result['charges'][0]['field_support']['amount']['ambiguity_kind'] == 'location'


def test_numeric_invoice_suffix_is_not_money_evidence():
    task = payload_for('INV-50', '50')
    result = skill.validate_evidence(task)
    assert not result['valid'] and not result['charges'][0]['field_support']['amount']['targets']


def test_structured_ocr_json_punctuation_is_not_a_numeric_separator():
    text = '{"amount": 50.25, "currency": "USD"}'
    task = payload_for('50.25', '50.25')
    task['sources'][0]['blocks'][0]['text'] = text
    task['charges'][0]['evidence'] = [dict(source_id='document', anchor='line', quote=text)]
    result = skill.validate_evidence(task)
    assert result['valid'], result['issues']
    assert result['charges'][0]['field_support']['amount']['status'] == 'supported'


def test_trailing_numeric_punctuation_is_allowed_without_matching_identifier_currencies():
    task = payload_for('50', '50')
    text = 'Amount USD 50, payable on receipt.'
    task['sources'][0]['blocks'][0]['text'] = text
    task['charges'][0]['evidence'] = [dict(source_id='document', anchor='line', quote=text)]
    assert skill.validate_evidence(task)['valid']
    for identifier in ('INVUSD123', '123USD456', 'INV_USD_123'):
        assert skill.currency_tokens(identifier) == []
    assert skill.currency_tokens('US$50')[0]['value'] == 'USD'


def test_total_uses_same_international_parser_and_does_not_borrow_currency():
    task = payload_for('1.234,56', '1234.56', 'EUR')
    task['totals'] = [dict(source_id='document', amount=Decimal('1234.56'), currency='EUR', evidence=[dict(
        source_id='document', anchor='line', quote='Amount EUR 1.234,56', field='amount')])]
    result = skill.validate_evidence(task)
    assert result['valid'], result['issues']
    assert result['total_evidence'][0]['field_support']['currency']['status'] == 'supported'
    task['totals'][0]['currency'] = 'USD'
    result = skill.validate_evidence(task)
    assert any(issue['code'] == 'TOTAL_VALUE_UNSUPPORTED' and issue['field'] == 'totals.currency'
               for issue in result['issues'])


def test_preview_reuses_safe_parser_and_does_not_locate_ambiguous_number_as_a_cell():
    source = dict(source_id='document', format='xlsx', blocks=[dict(anchor='r2', text='费用 1.234,56',
        sheet='Fees', row=2, cells=[dict(text='1.234,56', coordinate='C2')])])
    result = skill.build_preview(dict(source=source, target=dict(anchor='r2', field='amount', value='1234.56')))
    assert result['target']['location_level'] == 'cell' and result['target']['coordinate'] == 'C2'
    source['blocks'][0]['cells'][0]['text'] = '1,234'
    result = skill.build_preview(dict(source=source, target=dict(anchor='r2', field='amount', value='1234')))
    assert result['target']['location_level'] == 'block' and 'coordinate' not in result['target']


def test_standalone_cli_uses_contract_outside_the_project(tmp_path):
    task = payload_for('1\u202f234,56', '1234.56', 'EUR', '€')
    result = subprocess.run([sys.executable, '-B', str(PACKAGE / 'scripts' / 'skill.py'),
        '--operation', 'validate_evidence'], cwd=tmp_path, input=simplejson.dumps(task, use_decimal=True),
        capture_output=True, encoding='utf-8', timeout=20)
    assert result.returncode == 0, result.stderr
    response = simplejson.loads(result.stdout, use_decimal=True)
    assert response['field_support_contract'] == 'source_support_v2'
    assert response['charges'][0]['field_support']['amount']['status'] == 'supported'
