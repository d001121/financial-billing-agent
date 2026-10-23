"""Real source targets remain honest across Office and OCR representations."""
from backend.extensions.skill_versions import skill_module


def preview(source, **target):
    return skill_module('evidence-linking').build_preview(dict(source=source, revision=3, target=target))


def test_excel_selects_exact_decimal_cell_and_never_substring_amount():
    source = dict(source_id='x', name='invoice.xlsx', format='xlsx', blocks=[dict(
        anchor='sheet:Fees/row:2', text='THC\t150\t50.00\tUSD', sheet='Fees', row=2,
        cells=[dict(column=1, coordinate='A2', value='THC'),
               dict(column=2, coordinate='B2', value=150),
               dict(column=3, coordinate='C2', value='50.00'),
               dict(column=4, coordinate='D2', value='USD')])])
    result = preview(source, anchor='sheet:Fees/row:2', field='amount', value='50')
    assert result['target']['location_level'] == 'cell'
    assert result['target']['column'] == 3 and result['target']['cell_anchor'] == 'C2'
    assert result['representation'] == 'original_structure'


def test_duplicate_amount_only_locates_row():
    source = dict(source_id='x', format='xlsx', blocks=[dict(anchor='r2', text='50\t50',
        cells=[dict(column=1, value=50), dict(column=2, value=50)])])
    result = preview(source, anchor='r2', field='amount', value='50')
    assert result['target']['located'] and result['target']['location_level'] == 'block'
    assert 'column' not in result['target']


def test_unknown_ocr_boxes_and_repeated_anchors_are_not_guessed():
    source = dict(source_id='scan', format='pdf', blocks=[dict(anchor='p1', text='USD 50',
        page=1, bbox=[0.1, 0.2, 0.3, 0.4])])
    result = preview(source, anchor='p1', quote='USD 50')
    assert 'bbox' not in result['target']
    source['blocks'].append(dict(source['blocks'][0]))
    assert preview(source, anchor='p1')['target']['located'] is False


def test_word_rendered_page_is_bound_to_pdf_hash_and_does_not_invent_original_page():
    source = dict(source_id='word', format='docx', metadata={'office_preview': dict(
        format='pdf', sha256='version-a', page_count=4)}, blocks=[dict(
        anchor='table:1/row:45', text='THC USD 50', preview=dict(
            pages=[3], artifact_sha256='version-a'))])
    result = preview(source, anchor='table:1/row:45', quote='THC USD 50')
    assert result['target']['render_page'] == 3 and result['target']['render_version'] == 'version-a'
    assert 'page' not in result['target']
    source['metadata']['office_preview']['sha256'] = 'version-b'
    assert 'render_page' not in preview(source, anchor='table:1/row:45')['target']
