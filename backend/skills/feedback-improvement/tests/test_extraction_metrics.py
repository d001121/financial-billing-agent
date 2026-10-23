"""Independent financial-field metrics must detect realistic wrong answers."""
from copy import deepcopy
from decimal import Decimal
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location('extraction_metrics', Path(__file__).parents[1]/'scripts/skill.py')
skill = importlib.util.module_from_spec(spec)
spec.loader.exec_module(skill)


def row(name='Handling Charge', amount=65, currency='USD', reference='DC-108478'):
    return dict(document_info={'reference_no': reference}, charge_details=dict(
        charge_item=name, amount=amount, currency=currency, payment_term=None))


def scores(actual, expected):
    return {m['key']: m['score'] for m in skill.extraction_evaluator(
        {'records': actual}, {'records': expected})}


def test_order_and_decimal_representation_do_not_change_correctness():
    expected = [row(), row(amount=35)]
    actual = [row(amount=Decimal('35.00')), row(amount=65.0)]
    assert scores(actual, expected)['extraction_exact']


def test_same_name_merge_omission_duplicate_and_wrong_number_fail():
    expected = [row(), row(amount=35)]
    for actual in ([row(amount=100)], [row()], [*expected, row()], [row(reference='WRONG'), row(amount=35)]):
        assert not scores(actual, expected)['extraction_exact']
    assert scores([row()], expected)['missing_rows'] == 1
    assert scores([*expected, row()], expected)['extra_rows'] == 1


def test_swapped_currencies_fail_even_when_individual_column_bags_match():
    expected = [row(currency='USD'), row(amount=35, currency='EUR')]
    actual = [row(currency='EUR'), row(amount=35, currency='USD')]
    result = scores(actual, expected)
    assert result['charge_details_currency']
    assert result['charge_details_amount']
    assert not result['extraction_exact'] and result['charge_recall'] == 0


def test_null_is_a_label_not_permission_to_guess_and_amount_must_be_numeric():
    assert scores([row(currency=None)], [row(currency=None)])['extraction_exact']
    assert not scores([row(currency='USD')], [row(currency=None)])['extraction_exact']
    for value in ('65', True, float('nan'), float('inf')):
        assert not scores([row(amount=value)], [row()])['extraction_exact']


def test_existing_release_metrics_reject_a_changed_document_number():
    expected = row()
    actual = deepcopy(expected)
    actual['document_info']['reference_no'] = 'ANOTHER-INVOICE'
    metrics = {m['key']:m['score'] for m in skill.financial_evaluator(
        {'records':[actual]}, {'records':[expected]})}
    assert not metrics['document_info_reference_no']
