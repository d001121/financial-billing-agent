"""Locate display citations in real PDF geometry, without changing saved evidence."""
from functools import lru_cache
from hashlib import sha256
import json
from pathlib import Path
import re
from threading import RLock
import unicodedata


def normalized(text):
    return ''.join(c for c in unicodedata.normalize('NFKC', str(text)).casefold() if not c.isspace())


def occurrences(text, needle):
    start = 0
    while needle:
        at = text.find(needle, start)
        if at < 0:
            break
        yield at, at + len(needle)
        start = at + len(needle)


def line_index(chars):
    """Rebuild visual spacing and preserve a pointer for every character."""
    text, pointers = '', []
    previous = None
    for char in chars:
        if previous and char['x0']-previous['x1'] > 2 and not text.endswith(' '):
            text += ' '
            pointers.append(previous)
        part = char['text']
        text += part
        pointers.extend([char] * len(part))
        previous = char
    return text, pointers


def text_lines(page):
    lines = []
    for line in page.dedupe_chars().extract_text_lines(return_chars=True):
        # Geometry order, not the order of objects in the PDF content stream.
        chars = sorted(line['chars'], key=lambda c: c['x0'])
        text, pointers = line_index(chars)
        lines.append(dict(text=text, pointers=pointers))
    return lines


_OCR_LOCK = RLock()


@lru_cache(maxsize=1)
def ocr_engine():
    from rapidocr import RapidOCR
    return RapidOCR(params={'EngineConfig.onnxruntime.intra_op_num_threads': 2,
                            'EngineConfig.onnxruntime.inter_op_num_threads': 1})


def ocr_lines(image, cache_file):
    """Auxiliary local boxes only. Never replace extraction/OCR/financial facts."""
    from PIL import ImageOps
    import numpy as np
    image = ImageOps.exif_transpose(image).convert('RGB')
    width, height = image.size
    with _OCR_LOCK:
        if cache_file.is_file():
            return json.loads(cache_file.read_text(encoding='utf-8'))
        output = ocr_engine()(np.array(image))
        lines = []
        if output.boxes is not None and output.txts is not None:
            for box, text, score in zip(output.boxes, output.txts, output.scores):
                if float(score) < .7:
                    continue
                xs, ys = [float(p[0]) / width for p in box], [float(p[1]) / height for p in box]
                lines.append(dict(text=text, box=dict(x=min(xs), y=min(ys),
                    width=max(xs)-min(xs), height=max(ys)-min(ys), unit='normalized'), score=float(score)))
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps(lines, ensure_ascii=False), encoding='utf-8')
        return lines


def locate(preview, path, *, numeric_tokens, currency_tokens, decimal, cache_dir=None):
    target = preview['target']
    quote = target.get('quote') or ''
    value = target.get('value')
    field = str(target.get('field') or '').split('.')[-1]
    context = target.get('context') or quote
    original = dict(status='unlocated', locations=[], reason='未在原件中找到对应内容')
    preview['original'] = original
    if value in (None, '') and not quote:
        original['reason'] = '请选择需要核对的字段或原文'
        return preview
    digest = sha256(Path(path).read_bytes()).hexdigest()
    original.update(content_sha256=digest, locator_version='1.0.0')

    def spans(text):
        # Character positions refer to the normalized physical line, not a
        # model-generated offset. Money parsing reuses the existing Skill.
        if field in ('amount', 'quantity', 'unit_price') and value is not None:
            return [(t['start'], t['end']) for t in numeric_tokens(text)
                    if t['candidates'] == [decimal(value)]]
        if field == 'currency' and value:
            return [(t['start'], t['end']) for t in currency_tokens(text.upper()) if t['value'] == value]
        choices = [target.get('display_value'), value] if value not in (None, '') else [quote]
        plain, offsets = '', []
        for index, char in enumerate(text):
            part = normalized(char)
            plain += part
            offsets.extend([index] * len(part))
        for choice in choices:
            needle = normalized(choice or '')
            found = [(offsets[a], offsets[b-1]+1) for a, b in occurrences(plain, needle)]
            if found:
                return found
        return []

    # Context chooses between real occurrences; it never creates a box. Ignore
    # JSON keys from structured OCR, but keep the original printed values.
    terms = {normalized(t) for t in re.findall(r'[^\W_]+', context, re.UNICODE) if len(t) > 1}
    terms -= {'amount', 'chargeitem', 'currency', 'chargelist', 'null'}

    def candidates(lines, page, *, bounds=None, method='pdf-text'):
        result = []
        joined = ''.join(normalized(line['text']) for line in lines)
        whole_matches = list(occurrences(joined, normalized(quote)))
        cursor = 0
        for line in lines:
            text = line['text']
            for first, last in spans(text):
                if bounds:
                    chars = line['pointers'][first:last]
                    if not chars:
                        continue
                    x0, top = min(c['x0'] for c in chars), min(c['top'] for c in chars)
                    x1, bottom = max(c['x1'] for c in chars), max(c['bottom'] for c in chars)
                    bx, by, br, bb = bounds
                    box = dict(x=(x0-bx)/(br-bx), y=(top-by)/(bb-by),
                               width=(x1-x0)/(br-bx), height=(bottom-top)/(bb-by), unit='normalized')
                else:
                    # OCR reports line polygons, so highlight the actual line,
                    # never interpolate a character box inside a scanned image.
                    box = line['box']
                if min(box['x'], box['y']) < 0 or box['x']+box['width'] > 1.001 or box['y']+box['height'] > 1.001:
                    continue
                exact = any(a <= cursor+len(normalized(text[:first])) and cursor+len(normalized(text[:last])) <= b for a, b in whole_matches)
                score = (10000 if exact else 0) + sum(len(t) for t in terms if t in normalized(text))
                result.append(dict(page=page, boxes=[box], text=text, method=method, context_score=score))
            cursor += len(normalized(text))
        return result

    found = []
    failures = []
    if preview['kind'] == 'image':
        from PIL import Image
        if cache_dir:
            with Image.open(path) as image:
                frame = max(0, int(target.get('page') or 1)-1)
                image.seek(frame)
                lines = ocr_lines(image, Path(cache_dir) / f'{digest}-frame{frame}-rapidocr3.10.json')
            found = candidates(lines, frame+1, method='local-ocr-line')
    else:
        import pdfplumber
        with pdfplumber.open(path) as pdf:
            page_hint = target.get('render_page') if preview.get('render') else target.get('page')
            # Search physical pages even when structured OCR provided no page.
            pages = list(range(len(pdf.pages)))
            if type(page_hint) is int and 1 <= page_hint <= len(pages):
                pages.remove(page_hint-1)
                pages.insert(0, page_hint-1)
            for index in pages:
                page = pdf.pages[index]
                bounds = page.cropbox or page.bbox
                lines = text_lines(page.crop(bounds))
                matches = candidates(lines, index+1, bounds=bounds)
                if not matches and cache_dir and (not lines or page.images):
                    try:
                        image = page.to_image(resolution=144).original
                        ocr = ocr_lines(image, Path(cache_dir) / f'{digest}-p{index+1}-rapidocr3.10.json')
                        matches = candidates(ocr, index+1, method='local-ocr-line')
                    except Exception as exc:
                        failures.append(f'第{index+1}页定位识别失败: {type(exc).__name__}: {exc}')
                found.extend(matches)
                page.close()
                if index+1 == page_hint and matches:
                    break
    # Deduplicate identical glyphs/layers, retaining distinct real occurrences.
    unique = {(m['page'], json.dumps(m['boxes'], sort_keys=True)): m for m in found}
    found = list(unique.values())
    if found:
        best = max(m['context_score'] for m in found)
        found = [m for m in found if m['context_score'] == best]
        original.update(status='located' if len(found) == 1 else 'ambiguous', locations=found,
            reason='已定位原件，黄色标注对应内容' if len(found) == 1 else f'找到{len(found)}处相同内容，请切换位置对照上下文')
    if failures:
        original['errors'] = failures
    return preview
