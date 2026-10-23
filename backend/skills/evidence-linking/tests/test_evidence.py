import importlib.util
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("evidence_linking_skill", Path(__file__).parents[1] / "scripts" / "skill.py")
skill = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(skill)


def cross_file_payload(relation='same_bill', key='reference_no', value='INV-1'):
    return dict(sources=[dict(source_id='a', text='Invoice INV-1 MBL BOL-9 THC 100'),
                         dict(source_id='b', text='Invoice INV-1 MBL BOL-9 Currency USD')],
        charges=[dict(charge_id='c', source_id='a', document_id='INV-1', reference_no='INV-1',
            source_links=[dict(source_id='b', relationship=relation, identity_field=key, identity_value=value,
                evidence=[dict(source_id=s, quote=value) for s in ('a', 'b')])],
            evidence=[dict(source_id='a', quote='THC 100', field='amount'),
                      dict(source_id='b', quote='Currency USD', field='currency')])])


def test_cross_source_citations_do_not_require_identity_proof_checklists():
    payload = cross_file_payload()
    assert skill.link_evidence(payload)['valid']
    payload['charges'][0]['source_links'] = []
    result = skill.link_evidence(payload)
    assert result['valid']
    assert result['charges'][0]['evidence'][1]['verified']


def test_same_shipment_does_not_authorize_currency_or_invoice_total_borrowing():
    payload = cross_file_payload('shipment_context', 'bill_of_lading', 'BOL-9')
    payload['sources'][1]['text']='Invoice INV-2 MBL BOL-9 Currency USD'
    payload['documents']=[dict(source_id=sid,reference_no=reference,
        evidence=[dict(source_id=sid,quote='Invoice '+reference,field='reference_no')])
        for sid,reference in (('a','INV-1'),('b','INV-2'))]
    assert not skill.link_evidence(payload)['valid']
    assert any(i['code']=='CROSS_SOURCE_DOCUMENT_CONFLICT' for i in skill.link_evidence(payload)['issues'])
    payload['charges'][0]['evidence'][1] = dict(source_id='b', quote='MBL BOL-9', field='bill_of_lading')
    assert skill.link_evidence(payload)['valid']


def test_forged_relationship_cannot_replace_a_real_citation():
    for text in ('Invoice INV-2 MBL BOL-9 Currency USD', 'Invoice INV-1 MBL BOL-9 Currency USD'):
        payload = cross_file_payload()
        payload['sources'][1]['text'] = text
        if 'INV-2' not in text:
            payload['charges'][0]['source_links'][0]['identity_value'] = 'invented'
        payload['charges'][0]['evidence'][1]['quote']='invented currency text'
        result = skill.link_evidence(payload)
        assert not result['valid']
        assert not result['charges'][0]['evidence'][1]['verified']


def test_document_headers_cannot_copy_a_number_from_another_source():
    payload = dict(sources=[dict(source_id='a', text='B/L LOCAL-1 Container CONT-1'),
                            dict(source_id='b', text='MBL MASTER-2 Container CONT-1')],
        documents=[dict(source_id='a', document_id='a', bill_of_lading='MASTER-2',
            evidence=[dict(source_id='a', quote='B/L LOCAL-1', field='bill_of_lading')])])
    result = skill.link_evidence(payload)
    assert not result['valid']
    assert any(i['code']=='DOCUMENT_VALUE_UNSUPPORTED' for i in result['issues'])
    payload['documents'][0]['bill_of_lading']='LOCAL-1'
    assert skill.link_evidence(payload)['valid']


def test_exact_readback_and_real_metadata_only():
    payload = {"sources": [{"source_id": "doc", "blocks": [{"anchor": "p2", "text": "THC USD 100", "page": 2}]}],
               "charges": [{"charge_id": "c", "evidence": [{"source_id": "doc", "anchor": "p2", "quote": "USD 100"}]}]}
    result = skill.link_evidence(payload)
    link = result["charges"][0]["evidence"][0]
    assert result["valid"] and link["verified"] and link["page"] == 2
    assert "bbox" not in link
    assert "content_sha256" not in payload["charges"][0]["evidence"][0]


def test_missing_changed_and_non_authoritative_quotes_fail():
    for source in ({"source_id": "doc", "text": "USD 10"}, {"source_id": "doc", "text": "USD 100", "authoritative": False}):
        result = skill.validate_evidence({"sources": [source], "charges": [{"evidence": [{"source_id": "doc", "quote": "USD 100"}]}]})
        assert not result["valid"]
    assert not skill.validate_evidence({"charges": [{"evidence": []}]})["valid"]


def test_attachment_occurrences_are_not_deduplicated_by_hash():
    sources = [{"source_id": "a", "text": "USD 100", "occurrence_id": "mail1/att"},
               {"source_id": "b", "text": "USD 100", "occurrence_id": "mail2/att"}]
    result = skill.link_evidence({"sources": sources, "charges": [{"evidence": [{"source_id": s["source_id"], "quote": "USD 100"} for s in sources]}]})
    links = result["charges"][0]["evidence"]
    assert result["valid"] and len(links) == 2
    assert links[0]["content_sha256"] == links[1]["content_sha256"]
    assert links[0]["occurrence_id"] != links[1]["occurrence_id"]


def test_repeated_identical_line_requires_an_explicit_offset():
    payload = {"sources": [{"source_id": "a", "text": "THC 100\nTHC 100"}],
               "charges": [{"evidence": [{"source_id": "a", "quote": "THC 100"}]}]}
    assert not skill.link_evidence(payload)["valid"]
    payload["charges"][0]["evidence"][0]["quote_start"] = 8
    assert skill.link_evidence(payload)["valid"]


def test_unique_quote_recovers_reported_offset_from_actual_source():
    text = 'Header\r\nSHA pay TAR：H/C $50'
    ref = dict(source_id='mail', quote='H/C $50', quote_start=19)
    result = skill.link_evidence(dict(sources=[dict(source_id='mail', text=text)],
                                     charges=[dict(evidence=[ref])]))
    located = result['charges'][0]['evidence'][0]
    assert result['valid']
    assert located['quote_start'] == text.index('H/C $50')
    assert located['reported_quote_start'] == 19
    assert located['location_method'] == 'unique_exact_quote'
    assert ref['quote_start'] == 19


def test_repeated_quote_wrong_offset_returns_real_choices_without_picking_one():
    text = 'CONSIGNEE\nVASINGER LLC\nNOTIFY PARTY\nVASINGER LLC'
    result = skill.link_evidence(dict(sources=[dict(source_id='hbl', text=text)],
        charges=[dict(evidence=[dict(source_id='hbl', quote='VASINGER LLC', quote_start=1)])]))
    assert not result['valid']
    assert not result['charges'][0]['evidence'][0]['verified']
    choices = result['issues'][0]['locations']
    assert [c['quote_start'] for c in choices] == [10, 36]
    assert 'CONSIGNEE' in choices[0]['context_quote']


def test_null_offset_uses_unique_source_occurrence_without_relaxing_duplicates():
    payload = {"sources": [{"source_id": "doc", "text": "Invoice INV-1 Amount USD 20"}],
               "charges": [{"evidence": [{"source_id": "doc", "quote": "Amount USD 20",
                                           "quote_start": None, "quote_end": None}]}]}
    result = skill.link_evidence(payload)
    ref = result["charges"][0]["evidence"][0]
    assert result["valid"] and ref["quote_start"] == 14 and ref["quote_end"] == 27
    assert payload["charges"][0]["evidence"][0]["quote_start"] is None
    payload["sources"][0]["text"] += " Amount USD 20"
    result = skill.link_evidence(payload)
    assert not result["valid"] and not result["charges"][0]["evidence"][0]["verified"]


def test_same_total_quote_supports_unlabelled_field_without_borrowing_other_totals():
    payload = {"sources": [{"source_id": "doc", "blocks": [
        {"anchor": "total", "text": "Total USD 70"}, {"anchor": "other-total", "text": "Total EUR 50"}]}],
        "totals": [{"source_id": "doc", "role": "total", "amount": "70", "currency": "USD", "evidence": [
            {"source_id": "doc", "anchor": "total", "quote": "Total USD 70", "field": "amount"}]}]}
    result = skill.validate_evidence(payload)
    assert result["valid"], result["issues"]
    payload["totals"].append({"source_id": "doc", "role": "total", "amount": "50", "currency": "USD", "evidence": [
        {"source_id": "doc", "anchor": "other-total", "quote": "Total EUR 50", "field": "amount"}]})
    result = skill.validate_evidence(payload)
    assert not result["valid"]
    assert [i["total_index"] for i in result["issues"] if i["code"] == "TOTAL_VALUE_UNSUPPORTED"] == [1]


def test_explicit_total_field_reference_keeps_precedence_over_fallback():
    payload = {"sources": [{"source_id": "doc", "text": "Total USD 70 | Requested currency EUR"}],
        "totals": [{"source_id": "doc", "amount": "70", "currency": "USD", "evidence": [
            {"source_id": "doc", "quote": "Total USD 70", "field": "amount"},
            {"source_id": "doc", "quote": "Requested currency EUR", "field": "currency"}]}]}
    result = skill.validate_evidence(payload)
    assert not result["valid"]
    assert any(i["code"] == "TOTAL_VALUE_UNSUPPORTED" and i["field"] == "totals.currency" for i in result["issues"])
