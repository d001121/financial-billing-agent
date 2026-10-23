"""Markdown adapter for the user-supplied pdf-ocr-md 3.4.0 Skill.

Adapts its page/section/table Markdown strategy to the project's OCR callable.
No PaddleOCR, ONNX models, second LLM, or additional agent loop is used.
Original blocks stay untouched; a sidecar maps rendered lines to exact text.
See ../references/pdf-ocr-md.md for upstream provenance and deliberate changes.
"""
import hashlib
import json
from pathlib import Path


def _json_leaves(text):
    """Walk JSON with its native decoder, retaining original scalar offsets."""
    decoder = json.JSONDecoder()
    def whitespace(index):
        while index < len(text) and text[index].isspace():
            index += 1
        return index
    def walk(index, path):
        index = whitespace(index)
        value, end = decoder.raw_decode(text, index)
        if isinstance(value, dict) and value:
            cursor = whitespace(index + 1)
            for key in value:
                _, key_end = decoder.raw_decode(text, cursor)
                cursor = whitespace(key_end)
                if text[cursor] != ':':
                    raise ValueError('Invalid JSON object')
                cursor = yield from walk(cursor + 1, path + '/' + str(key).replace('~', '~0').replace('/', '~1'))
                cursor = whitespace(cursor)
                if cursor < len(text) and text[cursor] == ',':
                    cursor = whitespace(cursor + 1)
        elif isinstance(value, list) and value:
            cursor = whitespace(index + 1)
            for i in range(len(value)):
                cursor = yield from walk(cursor, path + '/' + str(i))
                cursor = whitespace(cursor)
                if cursor < len(text) and text[cursor] == ',':
                    cursor = whitespace(cursor + 1)
        else:
            yield path or '/', index, end
        return end
    yield from walk(0, '')


def _cell(value):
    return str(value).replace('|', '\\|').replace('\r', '').replace('\n', '<br>')


def build_markdown(source, output_dir):
    """Create clean, searchable Markdown for *every* parsed source occurrence."""
    lines = ['# ' + source.get('name', source['source_id']), '',
             '> source_id: ' + source['source_id'],
             '> status: ' + source.get('status', 'unknown'), '']
    spans, representations = [], []
    blocks = sorted(source.get('blocks', []), key=lambda block: block.get('priority', 50))
    word_rows = [b for b in blocks if b.get('structure_only') and b.get('kind') == 'table_row']
    grouped = {(b.get('table'), b.get('row')) for b in word_rows}
    for block in blocks:
        if block.get('authoritative') is False:
            continue
        # Render Word cells once as rows while mapping each cell paragraph back
        # to its authoritative content anchor, never to structure-only row text.
        if not block.get('structure_only') and (block.get('table'), block.get('row')) in grouped:
            continue
        text = block.get('text', '')
        anchor = block.get('anchor', 'text')
        kind = block.get('kind', 'text')
        location = {k: block[k] for k in ('page', 'original_pages', 'frame', 'sheet', 'row', 'table', 'cell',
                    'paragraph', 'response_pointer', 'extraction_method') if block.get(k) is not None}
        title = (f"Page {block['page']} / " if block.get('page') else '') + anchor
        lines.extend(['## ' + title, ''])
        first = len(lines) + 1
        def add(rendered, start, end):
            lines.append(rendered)
            spans.append(dict(line=len(lines), anchor=anchor, start=start, end=end,
                              quote=text[start:end], kind=kind, **location))
        if block.get('structure_only') and kind == 'table_row':
            cells = block.get('cells', [])
            lines.extend(['| ' + ' | '.join(str(c.get('column', i + 1)) for i, c in enumerate(cells)) + ' |',
                          '| ' + ' | '.join('---' for _ in cells) + ' |',
                          '| ' + ' | '.join(_cell(c.get('text', '[merged]')) for c in cells) + ' |'])
            for paragraph in blocks:
                if paragraph.get('structure_only') or paragraph.get('authoritative') is False:
                    continue
                if (paragraph.get('table'), paragraph.get('row')) != (block.get('table'), block.get('row')):
                    continue
                original = paragraph.get('text', '')
                if original:
                    spans.append(dict(line=len(lines), anchor=paragraph['anchor'], start=0, end=len(original),
                        quote=original, kind=paragraph.get('kind'), **{k: paragraph[k] for k in
                        ('table', 'row', 'cell', 'cell_anchor', 'paragraph') if k in paragraph}))
        elif block.get('structure_only'):
            continue
        elif kind == 'pdf_layout_financial' and block.get('rows'):
            lines.extend(['> 整理列不等于逐字原文；每行引用只对应 Original row。若币种来自同页表头，请另引用下方 layout 中印出币种的行。', '',
                          '| Description | Currency | Amount | Quantity | Rate | P/C | Original row |',
                          '| --- | --- | --- | --- | --- | --- | --- |'])
            offset = 0
            for row in block['rows']:
                raw = row['text']
                start = text.find(raw, offset)
                if start < 0:
                    raise ValueError('财务行与原始版式文本不一致')
                values = [row.get(key) for key in ('description', 'currency', 'raw_amount', 'raw_quantity', 'raw_rate', 'pc')]
                add('| ' + ' | '.join(_cell('' if value is None else str(value)) for value in [*values, raw]) + ' |',
                    start, start + len(raw))
                offset = start + len(raw)
        elif kind == 'ocr_structured':
            lines.extend(['> Structured OCR fields; not verbatim document full text.', '',
                          '| Field | Value |', '| --- | --- |'])
            for pointer, start, end in _json_leaves(text):
                # Literal JSON strings remain literal, including escape sequences;
                # never substitute decoded text for original evidence offsets.
                raw = text[start:end]
                display = raw[1:-1] if raw.startswith('"') and raw.endswith('"') else raw
                add(f'| {_cell(pointer)} | {_cell(display)} |', start, end)
        elif kind == 'table_row' and block.get('cells'):
            cells = block['cells']
            names = [c.get('coordinate', c.get('column', i + 1)) for i, c in enumerate(cells)]
            values = [c.get('value', c.get('text', '')) for c in cells]
            lines.extend(['| ' + ' | '.join(map(_cell, names)) + ' |',
                          '| ' + ' | '.join('---' for _ in cells) + ' |'])
            add('| ' + ' | '.join(_cell(v) for v in values) + ' |', 0, len(text))
        else:
            offset = 0
            for raw in text.splitlines(keepends=True):
                clean = raw.rstrip('\r\n').rstrip()
                if clean.strip():
                    # A single minified/very long paragraph must remain readable
                    # through the native line-paginated tool without mid-line loss.
                    for position in range(0, len(clean), 2000):
                        add(clean[position:position + 2000], offset + position,
                            offset + min(len(clean), position + 2000))
                offset += len(raw)
        representations.append(dict(anchor=anchor, kind=kind, start_line=first,
            end_line=len(lines), verbatim_fulltext=kind != 'ocr_structured', **location))
        lines.append('')
    if not spans:
        lines.extend(['> No usable text is available. Check source status and OCR receipt.', ''])
    markdown = '\n'.join(lines).rstrip() + '\n'
    target = Path(output_dir) / 'markdown' / (source['source_id'] + '.md')
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(markdown, encoding='utf-8', newline='\n')
    sidecar = target.with_suffix('.map.json')
    metadata = dict(source_id=source['source_id'], content_id=source.get('content_id'),
        status=source.get('status'), path=str(target.resolve()), map_path=str(sidecar.resolve()),
        virtual_path=f"/materials/{source['source_id']}.md", line_count=len(markdown.splitlines()),
        sha256=hashlib.sha256(markdown.encode()).hexdigest(), spans=spans, representations=representations,
        adapter='pdf-ocr-md/3.4.0-project-adapter/1')
    sidecar.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')
    return dict(**metadata, text=markdown)
