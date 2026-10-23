"""Real native image text parsing complements, never replaces, required OCR."""
import importlib.util
from pathlib import Path
from unittest.mock import patch

import httpx
from langchain_core.documents import Document

spec = importlib.util.spec_from_file_location('image_text_intake', Path(__file__).parents[1]/'scripts/skill.py')
skill = importlib.util.module_from_spec(spec)
spec.loader.exec_module(skill)
ORIGINAL = Path(__file__).parents[3]/'data/samples/图片示例.png'


def test_native_parser_recovers_printed_currency_missing_from_remote_structure(tmp_path):
    calls = []
    def remote(**kwargs):
        calls.append(kwargs)
        return {'success':True, 'data':{'list':[{'chargeList':[{'name':'WHARFAGE','amount':21.9}]}]}}
    result = skill.intake_document(ORIGINAL, output_dir=tmp_path, image_text_ocr=True,
        source_url='https://replay.invalid/original.png', ocr_response_format='orderChange', ocr_request=remote)
    source = result['sources'][0]
    text = next(b for b in source['blocks'] if b['kind']=='image_ocr_text')
    assert len(calls)==1 and source['status']=='ready'
    assert text['authoritative'] and text['frame']==1
    assert text['source_content_id']==source['content_id']
    assert all(s in text['text'] for s in ('USD','WHARFAGE','ORFR1618731','26.90'))
    assert 'USD' in source['markdown']['text']
    assert any(a['kind']=='image_text_ocr' and a['sha256'] for a in result['artifacts'])


def test_local_success_cannot_hide_required_remote_failure(tmp_path):
    with patch('langchain_community.document_loaders.parsers.images.RapidOCRBlobParser.parse',
               return_value=[Document(page_content='Fee USD 5')]):
        result = skill.intake_document(ORIGINAL, output_dir=tmp_path, image_text_ocr=True,
            source_url='https://replay.invalid/original.png',
            ocr_request=lambda **_:httpx.Response(503,request=httpx.Request('POST',skill.OCR_ENDPOINT)))
    source = result['sources'][0]
    assert source['status']!='ready'
    assert not next(b for b in source['blocks'] if b['kind']=='image_ocr_text')['authoritative']
    assert any(i['code']=='ocr_http_error' for i in result['issues'])


def test_auxiliary_parser_failure_is_visible_and_keeps_remote_receipt(tmp_path):
    with patch('langchain_community.document_loaders.parsers.images.RapidOCRBlobParser.parse',
               side_effect=RuntimeError('fixture parser failure')):
        result = skill.intake_document(ORIGINAL, output_dir=tmp_path, image_text_ocr=True,
            source_url='https://replay.invalid/original.png', ocr_request=lambda **_:'Fee USD 5')
    source = result['sources'][0]
    assert source['status']=='ready'
    assert source['metadata']['image_text_ocr'][0]['status']=='failed'
    assert any(i['code']=='image_text_failed' and not i['blocking'] for i in result['issues'])
    assert any(a['kind']=='ocr_raw' for a in result['artifacts'])
