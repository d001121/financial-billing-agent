"""Each portable business CLI works outside the project and rejects invalid input."""
from decimal import Decimal
from pathlib import Path
import subprocess
import sys

import pytest
import simplejson

ROOT = Path(__file__).resolve().parents[1]
PACKAGES = ('document-extraction', 'evidence-linking', 'billing-reconciliation', 'billing-export')


def valid_payload(package):
    evidence = [dict(source_id='doc', anchor='text', quote='THC USD 100')]
    sources = [dict(source_id='doc', text='THC USD 100')]
    charge = dict(charge_id='c1', source_id='doc', charge_item='THC',
                  amount=Decimal('100.1234567890123456789'), currency='USD',
                  creditor='Carrier', debtor='Client', evidence=[{**evidence[0], 'verified': True}])
    if package == 'document-extraction':
        return dict(sources=sources)
    if package == 'evidence-linking':
        return dict(sources=sources, charges=[charge])
    if package == 'billing-reconciliation':
        return dict(charges=[charge], existing_records=[], accounting_entity='Client', revision=1)
    return dict(records=[dict(operation='CREATE', charge_item='THC', amount=charge['amount'],
                             currency='USD', accounting_entity='Client', posting_type='AP')], revision=1)


def run_cli(package, tmp_path, *args, data=None):
    script = ROOT / 'skills' / package / 'scripts' / 'skill.py'
    return subprocess.run([sys.executable, '-B', str(script), *map(str, args)], cwd=tmp_path,
                          input=data, capture_output=True, encoding='utf-8', timeout=30)


@pytest.mark.parametrize('package', PACKAGES)
def test_skill_cli_accepts_files_and_preserves_default_stdio(package, tmp_path):
    payload = simplejson.dumps(valid_payload(package), use_decimal=True, ensure_ascii=False)
    input_path, output_path = tmp_path / '输入.json', tmp_path / '输出.json'
    input_path.write_text(payload, encoding='utf-8-sig')
    file_run = run_cli(package, tmp_path, '--input', input_path, '--output', output_path)
    assert file_run.returncode == 0, file_run.stderr
    assert file_run.stdout == '' and file_run.stderr == ''
    file_result = simplejson.loads(output_path.read_text(encoding='utf-8'), use_decimal=True)
    stdio_run = run_cli(package, tmp_path, data=payload)
    assert stdio_run.returncode == 0, stdio_run.stderr
    assert stdio_run.stderr == ''
    assert simplejson.loads(stdio_run.stdout, use_decimal=True) == file_result
    if package == 'billing-export':
        assert isinstance(file_result, list)
        assert file_result[0]['charge_details']['amount'] == Decimal('100.1234567890123456789')
    elif package == 'document-extraction':
        # The documented default operation is read_materials, not validation.
        assert file_result['mode'] in ('read', 'search')
    else:
        assert file_result['valid']
    if package == 'billing-reconciliation':
        assert file_result['records'][0]['operation'] == 'CREATE'
        assert file_result['records'][0]['charge_details']['amount'] == Decimal('100.1234567890123456789')


@pytest.mark.parametrize(('package', 'payload', 'operation', 'issue'), [
    ('document-extraction', {'sources': [{'source_id': 's', 'status': 'failed'}]},
     'validate_coverage', 'SOURCE_INCOMPLETE'),
    ('evidence-linking', {'charges': [{'evidence': []}]}, 'validate_evidence', 'EVIDENCE_MISSING'),
    ('billing-reconciliation', {'charges': [{'amount': True}]}, 'validate_amounts', 'INVALID_AMOUNT'),
    ('billing-export', {'records': [{'operation': 'CREATE'}]}, 'validate_export', 'EXPORT_REQUIRED'),
])
def test_skill_cli_business_rejection_returns_json_and_exit_one(package, payload, operation, issue, tmp_path):
    result = run_cli(package, tmp_path, '--input', '-', '--output', '-', '--operation', operation,
                     data=simplejson.dumps(payload))
    assert result.returncode == 1
    assert result.stderr == ''
    rejection = simplejson.loads(result.stdout)
    assert not rejection['valid']
    assert issue in {i['code'] for i in rejection['issues']}


@pytest.mark.parametrize('package', PACKAGES)
def test_skill_cli_malformed_json_is_an_explicit_rejection(package, tmp_path):
    result = run_cli(package, tmp_path, data='{"unterminated":')
    assert result.returncode == 1 and result.stderr == ''
    rejection = simplejson.loads(result.stdout)
    assert not rejection['valid'] and rejection['issues'][0]['code'] == 'CLI_INPUT'
