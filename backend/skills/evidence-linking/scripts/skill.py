"""Read-back validation for immutable source references."""
from copy import deepcopy
from hashlib import sha256
import math
import re
from decimal import Decimal, InvalidOperation
import unicodedata
from functools import lru_cache

import pycountry


SUPPORT_CONTRACT = 'source_support_v2'
SUPPORT_FIELDS = ('reference_no', 'charge_item', 'amount', 'currency', 'quantity', 'unit_price', 'payment_term')
LOCATION_KEYS = ('source_id', 'anchor', 'quote', 'quote_start', 'quote_end', 'page', 'bbox',
                 'sheet', 'row', 'column', 'paragraph', 'table', 'cell', 'attachment_path',
                 'filename', 'render_version', 'occurrence_id', 'source_version', 'content_sha256')

# A bare symbol narrows the ISO candidates.  The model may recommend one from
# context; the Skill records it as a recommendation that still needs review.
_SYMBOL_CURRENCIES = {
    '$': {'USD', 'CAD', 'AUD', 'HKD', 'SGD', 'NZD', 'MXN', 'TWD', 'ARS', 'CLP', 'COP'},
    '¥': {'CNY', 'JPY'}, '￥': {'CNY', 'JPY'},
    '€': {'EUR'}, '£': {'GBP'},
    'kr': {'SEK', 'NOK', 'DKK', 'ISK'},
    'Rs': {'INR', 'PKR', 'LKR', 'NPR'},
    '₩': {'KRW'}, '₹': {'INR'}, '₽': {'RUB'}, '฿': {'THB'},
}


def recommended_currency(raw, iso):
    """Return whether `iso` is a plausible context recommendation for `raw`."""
    raw = (raw or '').strip()
    iso = str(iso or '').upper()
    if not raw or not iso:
        return False
    for symbol, currencies in _SYMBOL_CURRENCIES.items():
        if raw == symbol or raw.casefold() == symbol.casefold():
            return iso in currencies
    return False


@lru_cache(maxsize=1)
def _original_locator():
    import importlib.util
    from pathlib import Path
    spec = importlib.util.spec_from_file_location(__name__ + '_original_location',
        Path(__file__).with_name('original_location.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ISO_CURRENCIES = {row.alpha_3 for row in pycountry.currencies}
# These codes also occur as ordinary English words/names. Lower/title-case
# occurrences require an explicit source label, never the model's target code.
CODE_WORD_COLLISIONS = {'ALL', 'TRY', 'TOP', 'PEN', 'MAD', 'MOP', 'GEL', 'CUP', 'BOB',
                        'COP', 'CAD', 'RUB', 'ERN', 'BAM', 'SOS'}
# Qualified symbols identify a currency; country/language/issuer never does.
# C$, $, ¥, kr and Rs remain ambiguous in international material.
CURRENCY_ALIASES = {'US$': 'USD', 'CA$': 'CAD', 'AU$': 'AUD', 'A$': 'AUD', 'NZ$': 'NZD',
                    'HK$': 'HKD', 'SG$': 'SGD', 'S$': 'SGD', 'CN¥': 'CNY', 'JP¥': 'JPY',
                    'R$': 'BRL', '€': 'EUR'}
_currency_names = {}
for _currency in pycountry.currencies:
    _currency_names.setdefault(_currency.name.casefold(), set()).add(_currency.alpha_3)
CURRENCY_NAMES = {name: next(iter(codes)) for name, codes in _currency_names.items() if len(codes) == 1}
for _name, _code in list(CURRENCY_NAMES.items()):
    if _name.split()[-1] in ('dollar', 'euro', 'rupee', 'pound', 'franc', 'dinar', 'dirham', 'peso', 'rial', 'riyal'):
        CURRENCY_NAMES[_name + 's'] = _code
# Deliberately bounded local spellings, not a language/country inference table.
CURRENCY_LOCAL_NAMES = {'人民币': 'CNY', '欧元': 'EUR', '日元': 'JPY', '美元': 'USD',
                        '加元': 'CAD', '澳元': 'AUD', '港元': 'HKD', '英镑': 'GBP',
                        'Chinese Yuan': 'CNY', 'Japanese Yen': 'JPY'}
NUMERIC_RUN = re.compile(r'(?<![\w.,\uff0c\uff0e\u066b\u066c/])(?:[-+\u2212]?\(\s*|[-+\u2212]?)\d(?:[\d.,\uff0c\uff0e\u066b\u066c\u00a0\u202f \'’]*\d)?\s*\)?(?![\w/]|[.,\uff0c\uff0e\u066b\u066c]\d)')


def _canonical_decimal(value):
    """Read canonical machine numbers only, never guess a source locale."""
    if value is None or isinstance(value, bool):
        return None
    try:
        result = Decimal(str(value))
        return result if result.is_finite() else None
    except (InvalidOperation, ValueError):
        return None


def _grouped_integer(value, separator):
    groups = value.split(separator)
    if len(groups) < 2 or not all(group.isdigit() for group in groups) or groups[0].startswith('0'):
        return None
    western = 1 <= len(groups[0]) <= 3 and all(len(group) == 3 for group in groups[1:])
    indian = len(groups) > 2 and 1 <= len(groups[0]) <= 2 and len(groups[-1]) == 3 and all(
        len(group) == 2 for group in groups[1:-1])
    return ''.join(groups) if western or indian else None


def number_candidates(raw):
    """Return all supported readings of one whole source token, without a locale guess.

    Single punctuation followed by three digits can mean grouping or decimals.
    The extracted/model value never chooses between those readings.
    """
    chars = []
    for char in raw:
        try:
            chars.append(str(unicodedata.decimal(char)))
        except ValueError:
            chars.append({'\u066b': '.', '\u066c': ',', '\u00a0': ' ', '\u202f': ' ',
                          '’': "'", '\u2212': '-'}.get(char, unicodedata.normalize('NFKC', char)))
    token = ''.join(chars).strip()
    negative = token.startswith('(') and token.endswith(')')
    if '(' in token or ')' in token:
        if not negative:
            return []
        token = token[1:-1].strip()
    if token[:1] in ('+', '-'):
        if negative:
            return []
        negative, token = token[0] == '-', token[1:]
    if not token or not re.fullmatch(r"[0-9., ']+", token):
        return []
    # Space/apostrophe grouping must be complete, never deleted indiscriminately.
    groupers = [separator for separator in (' ', "'") if separator in token]
    if len(groupers) > 1:
        return []
    if groupers:
        grouper = groupers[0]
        tail = re.search(r'[.,][0-9]+$', token)
        integer = token[:tail.start()] if tail else token
        fraction = token[tail.start():] if tail else ''
        joined = _grouped_integer(integer, grouper)
        if joined is None or ',' in joined or '.' in joined:
            return []
        token = joined + fraction
    readings = []
    if ',' in token and '.' in token:
        decimal_mark = ',' if token.rfind(',') > token.rfind('.') else '.'
        grouping_mark = '.' if decimal_mark == ',' else ','
        if token.count(decimal_mark) != 1:
            return []
        integer, fraction = token.rsplit(decimal_mark, 1)
        grouped = _grouped_integer(integer, grouping_mark)
        if grouped and fraction.isdigit():
            readings.append(grouped + '.' + fraction)
    elif ',' in token or '.' in token:
        separator = ',' if ',' in token else '.'
        pieces = token.split(separator)
        if len(pieces) == 2 and all(piece.isdigit() for piece in pieces) and '\u066c' not in raw:
            readings.append(pieces[0] + '.' + pieces[1])
        grouped = _grouped_integer(token, separator)
        if grouped and '\u066b' not in raw:
            readings.append(grouped)
    elif token.isdigit():
        readings.append(token)
    result = []
    for reading in readings:
        value = Decimal(reading) * (-1 if negative else 1)
        if value not in result:
            result.append(value)
    return result


def _joins_number(left, right):
    """Whitespace is a group separator only inside one number (1 234,56)."""
    if re.search(r'[.,٫٬]', left):
        return False
    return bool(re.fullmatch(r'\d{3}(?:[.,٫٬]\d+)?\)?$', right))


def _numeric_parts(text, match):
    """Split a broad numeric run where layout columns are separated by spaces."""
    raw, start = match.group(), match.start()
    parts = []
    for piece in re.finditer(r'\S+', raw):
        if parts and _joins_number(parts[-1]['raw'], piece.group()):
            parts[-1]['end'] = start + piece.end()
        else:
            parts.append(dict(raw=piece.group(), start=start + piece.start(), end=start + piece.end()))
    for part in parts:
        part['raw'] = text[part['start']:part['end']]
    return parts


def numeric_tokens(text):
    """Keep raw spans. Invalid grouping is one invalid token, not valid suffixes."""
    result = []
    for match in NUMERIC_RUN.finditer(text):
        for part in _numeric_parts(text, match):
            start, end, raw = part['start'], part['end'], part['raw']
            # Do not interpret an invoice/container/date suffix as a money token.
            if start >= 2 and text[start - 1] in '-/' and text[start - 2].isalnum():
                continue
            result.append(dict(raw=raw, start=start, end=end, candidates=number_candidates(raw)))
    return result


def _layout_column(tokens, field):
    """A layout financial row prints rate, quantity and amount as its last three numbers."""
    if not tokens:
        return None
    if field == 'amount':
        token = tokens[-1]
    elif field == 'unit_price' and len(tokens) >= 3:
        token = tokens[-3]
    elif field == 'quantity' and len(tokens) >= 3:
        token = tokens[-2]
    else:
        return None
    return (token['start'], token['end'])


def currency_tokens(text):
    result = []
    for match in re.finditer(r'(?<!\w)[A-Za-z]{3}(?!\w)', text):
        code = match.group().upper()
        prefix = text[max(0, match.start() - 32):match.start()]
        labelled = bool(re.search(r'(?:\bcurrency|\bccy|币种)\s*[:=：]?\s*$', prefix, re.IGNORECASE))
        if code in ISO_CURRENCIES and (match.group().isupper() or code not in CODE_WORD_COLLISIONS or labelled):
            result.append(dict(value=code, start=match.start(), end=match.end(), raw=match.group()))
    for spelling, code in CURRENCY_ALIASES.items():
        boundary = r'(?<!\w)' if spelling[0].isalpha() else ''
        for match in re.finditer(boundary + re.escape(spelling) + r'(?![A-Za-z])', text, re.IGNORECASE):
            result.append(dict(value=code, start=match.start(), end=match.end(), raw=match.group()))
    for spelling, code in {**CURRENCY_NAMES, **CURRENCY_LOCAL_NAMES}.items():
        latin = spelling.isascii()
        pattern = (r'(?<!\w)' if latin else '') + re.escape(spelling) + (r'(?!\w)' if latin else '')
        for match in re.finditer(pattern, text, re.IGNORECASE):
            result.append(dict(value=code, start=match.start(), end=match.end(), raw=match.group()))
    unique = {(token['value'], token['start'], token['end']): token for token in result}
    return [token for token in unique.values() if not any(
        other['value'] == token['value'] and other['start'] <= token['start'] and
        other['end'] >= token['end'] and other['end'] - other['start'] > token['end'] - token['start']
        for other in unique.values())]


def _flat(row):
    result = dict(row)
    for name in ('document_info', 'charge_details', 'transaction_party', 'financial_attributes'):
        if isinstance(row.get(name), dict):
            result.update(row[name])
    return result


def field_support(row, field, *, total=False):
    """Measure one value inside fresh read-back references, retaining uncertainty."""
    values = _flat(row)
    value = values.get(field)
    fact = dict(value=deepcopy(value), score=0, status='missing', reasons=['当前字段缺失'], targets=[])
    if value is None or value == '':
        return fact
    refs = [ref for ref in row.get('evidence', []) if ref.get('verified') is True]
    explicit = [ref for ref in refs if str(ref.get('field', '')).split('.')[-1] == field]
    applicable = explicit or (refs if total else [ref for ref in refs if not ref.get('field')])
    if not applicable:
        fact.update(status='unavailable', reasons=['没有该字段的当前可回读引用'])
        return fact
    locations, targets, observations = set(), {}, []
    numeric_ambiguity = currency_ambiguity = location_ambiguity = contradictory = False
    for ref in applicable:
        text = ref['quote']
        spans = []
        if field in ('amount', 'quantity', 'unit_price'):
            expected = _canonical_decimal(value)
            tokens = numeric_tokens(text)
            # Layout financial rows also print rate and quantity. Only the
            # column that owns this field may support it, so the same number
            # appearing twice (rate == amount) is not a second location.
            is_layout = (ref.get('kind') == 'pdf_layout_financial'
                         or str(ref.get('anchor') or '').endswith('/layout/financial'))
            column = _layout_column(tokens, field) if is_layout else None
            checked = [token for token in tokens if column is None
                       or (token['start'], token['end']) == column]
            for token in checked:
                observations.append(dict(raw=token['raw'], candidates=[str(v) for v in token['candidates']],
                                         source_id=ref['source_id'], anchor=ref['anchor'],
                                         value_start=ref['quote_start'] + token['start'],
                                         value_end=ref['quote_start'] + token['end']))
                if expected is not None and expected in token['candidates']:
                    spans.append((token['start'], token['end']))
                    numeric_ambiguity |= len(token['candidates']) > 1
            contradictory |= bool(explicit and checked and not spans and any(t['candidates'] for t in checked))
        elif field == 'currency':
            tokens = currency_tokens(text)
            spans = [(token['start'], token['end']) for token in tokens if token['value'] == str(value).upper()]
            contradictory |= bool(explicit and tokens and not spans)
            currency_ambiguity |= bool(spans and any(token['value'] != str(value).upper() for token in tokens))
            if not tokens and re.search(r'\$|¥|￥|\b(?:kr|Rs)\b', text, re.IGNORECASE):
                currency_ambiguity = True
        else:
            spellings = [value]
            if field == 'payment_term':
                spellings = {'PP': ['PP', 'PREPAID', 'PRE-PAID'], 'CC': ['CC', 'COLLECT']}.get(str(value).upper(), spellings)
            if field == 'charge_item' and values.get('raw_charge_item'):
                spellings.append(values['raw_charge_item'])
            spans = sorted({m.span() for spelling in spellings for m in re.finditer(
                r'(?<!\w)' + re.escape(str(spelling).strip()) + r'(?!\w)', text, re.IGNORECASE)})
            # Nested normalized/raw spellings identify one printed occurrence.
            # Keep its widest span; disjoint repeated values remain ambiguous.
            spans = [(start, end) for start, end in spans if not any(
                a <= start and end <= b and (a, b) != (start, end) for a, b in spans)]
        location_ambiguity |= len(spans) > 1
        for start, end in spans:
            absolute = (ref['content_sha256'], ref['anchor'], ref['quote_start'] + start, ref['quote_start'] + end)
            locations.add(absolute)
            targets.setdefault(absolute, {key: deepcopy(ref[key]) for key in LOCATION_KEYS if key in ref} |
                               dict(field=field, value_start=absolute[2], value_end=absolute[3]))
    fact.update(targets=list(targets.values()))
    if observations:
        fact['observations'] = observations
    if contradictory:
        fact.update(status='unsupported', reasons=['字段专属引用包含与当前值矛盾的原文'], conflict=True)
    elif currency_ambiguity and recommended_currency(values.get('raw_currency'), value):
        fact.update(score=40, status='recommended',
                    reasons=[f'原文仅符号{values.get("raw_currency")}，结合上下文推荐{str(value).upper()}，需核对'])
    elif numeric_ambiguity or currency_ambiguity:
        fact.update(status='ambiguous', ambiguity_kind='format' if numeric_ambiguity else 'currency',
                    reasons=['原文数字存在多个合理格式解释，不能用模型值选择解释' if numeric_ambiguity else '原文币种符号或多币种引用存在歧义'])
    elif location_ambiguity or (len(locations) > 1 and not explicit and not (values.get('line_id') and all(
            ref.get('line_id') == values['line_id'] for ref in applicable))):
        fact.update(status='ambiguous', ambiguity_kind='location', reasons=['相同值有多个原文位置，需精确字段或费用行定位'])
    elif locations:
        fact.update(score=100, status='supported', reasons=['当前值有唯一字段/费用行原文支持；重复引用不增加支持度'])
    else:
        fact.update(status='unsupported', reasons=['已回读引用不支持当前字段值'])
    return fact


def _registry(sources):
    result = {}
    for source in sources:
        sid = str(source.get("source_id", source.get("id", "")))
        blocks = source.get("blocks") or [source]
        for block in blocks:
            bid = str(block.get("source_id", sid))
            anchor = str(block.get("anchor", block.get("block_id", block.get("id", "text"))))
            entry = {**source, **block, "source_id": bid, "anchor": anchor,
                     "text": block.get("text", block.get("content", ""))}
            result.setdefault((bid, anchor), []).append(entry)
            if sid and sid != bid:
                result.setdefault((sid, anchor), []).append(entry)
    return result


def link_evidence(payload: dict) -> dict:
    """Validate source/anchor/quote and add immutable provenance, preserving occurrences."""
    registry = _registry(payload.get("sources", []))
    references = {}
    for document in payload.get('documents', []):
        if document.get('reference_no'):
            references.setdefault(str(document.get('source_id') or ''), set()).add(
                str(document['reference_no']).strip().casefold())
    charges, issues = deepcopy(payload.get("charges", payload.get("records", []))), []
    for charge in charges:
        evidence = charge.get("evidence", [])
        valid_links = []
        origin = str(charge.get('source_id') or '')
        primary_references = references.get(origin, set())
        if charge.get('reference_no'):
            primary_references = primary_references | {str(charge['reference_no']).strip().casefold()}
        # Material relationships are a semantic decision of the reading agent.
        # Verify actual quotations; do not demand a duplicate identity-proof DAG.
        if not evidence:
            issues.append({"code": "EVIDENCE_MISSING", "field": "evidence", "charge_id": charge.get("charge_id"),
                           "message": "每条费用至少需要一处可回读的来源", "severity": "error", "repairable": True})
        for ref in evidence:
            sid = str(ref.get("source_id", ""))
            anchor = str(ref.get("anchor", ref.get("block_id", "text")))
            field = str(ref.get('field') or '').split('.')[-1]
            if (sid != origin and field in ('amount', 'currency', 'unit_price', 'quantity', 'payment_term')
                    and primary_references and references.get(sid)
                    and primary_references.isdisjoint(references[sid])):
                issues.append(dict(code='CROSS_SOURCE_DOCUMENT_CONFLICT', field=field,
                    charge_id=charge.get('charge_id'), source_id=sid, severity='error', repairable=True,
                    message='补充引用所属单据编号与本费用明确冲突；共享运输信息不能转借财务字段'))
                valid_links.append({**ref, 'verified': False})
                continue
            matches = registry.get((sid, anchor), [])
            quote = ref.get("quote", "")
            verified = [s for s in matches if s.get("authoritative") is not False and
                        not s.get("structure_only") and isinstance(quote, str) and quote and quote in str(s.get("text", ""))]
            locations, unambiguous = [], []
            if verified:
                for source in verified:
                    content = str(source.get("text", ""))
                    start = ref.get("quote_start")
                    starts = [m.start() for m in re.finditer('(?=' + re.escape(quote) + ')', content)]
                    for position in starts:
                        if len(locations) < 8:
                            locations.append(dict(quote_start=position, quote_end=position + len(quote),
                                context_quote=content[max(0, position - 80):position + len(quote) + 80],
                                **{k: source[k] for k in ('page', 'occurrence_id') if k in source}))
                    if isinstance(start, int) and not isinstance(start, bool) and start in starts:
                        unambiguous.append((source, start))
                    elif len(starts) == 1:
                        # Exact, unique source text determines location; LLM
                        # character arithmetic cannot override that location.
                        unambiguous.append((source, starts[0]))
            if len(unambiguous) != 1:
                issues.append({"code": "EVIDENCE_AMBIGUOUS" if len(locations) > 1 else "EVIDENCE_UNREADABLE",
                               "field": "evidence", "charge_id": charge.get("charge_id"),
                               "source_id": sid, "anchor": anchor, "message": "引用必须唯一定位且与原文逐字相符",
                               "locations": locations,
                               "severity": "error", "repairable": True})
                valid_links.append({**ref, "verified": False})
                continue
            source, offset = unambiguous[0]
            text = str(source.get("text", ""))
            linked = {**ref, "source_id": sid, "anchor": anchor, "verified": True,
                      "content_sha256": sha256(text.encode("utf-8")).hexdigest(),
                      "source_version": source.get("version", source.get("source_version", 1)),
                      "quote_start": offset, "quote_end": offset + len(quote)}
            if ref.get('quote_start') is not None and ref['quote_start'] != offset:
                linked.update(reported_quote_start=ref['quote_start'], location_method='unique_exact_quote')
            for key in ("kind", "page", "bbox", "sheet", "row", "column", "paragraph", "table", "cell",
                        "attachment_path", "filename", "render_version", "occurrence_id"):
                if source.get(key) is not None:
                    linked[key] = deepcopy(source[key])
            valid_links.append(linked)
        charge["evidence"] = valid_links
    documents = []
    for index, document in enumerate(payload.get('documents', [])):
        checked = link_evidence(dict(sources=payload.get('sources', []), charges=[dict(document,
            charge_id=f'_document:{index}', source_links=[])]))
        entry = deepcopy(document)
        entry['evidence'] = checked['charges'][0]['evidence']
        entry['field_support'] = {}
        issues.extend(dict(i, document_id=document.get('document_id')) for i in checked['issues'])
        for field in ('reference_no', 'bill_of_lading', 'master_bill_of_lading', 'booking_no', 'container_no'):
            if not document.get(field):
                continue
            # A header identifier must occur in this source's read-back facts.
            # A printed B/L may legitimately support both reference_no and B/L.
            supported = field_support(dict(entry, evidence=[dict(ref, field=field)
                for ref in entry['evidence'] if ref.get('source_id') == document.get('source_id')]), field)
            entry['field_support'][field] = supported
            if supported['status'] != 'supported':
                issues.append(dict(code='DOCUMENT_VALUE_UNSUPPORTED', field=field,
                    source_id=document.get('source_id'), document_id=document.get('document_id'),
                    severity='error', repairable=True,
                    message='单据头身份值必须由该文件自己的原文支持；不能把其他材料的编号覆盖到本文件'))
        documents.append(entry)
    return {"valid": not issues, "issues": issues, "charges": charges, "records": charges, 'documents': documents,
            "revision": payload.get("revision")}


def validate_evidence(payload: dict) -> dict:
    result = link_evidence(payload)
    result['field_support_contract'] = SUPPORT_CONTRACT
    for charge in result['charges']:
        charge['field_support'] = {field: field_support(charge, field) for field in SUPPORT_FIELDS}
        for field in ('amount', 'currency', 'charge_item'):
            fact = charge['field_support'][field]
            if fact['status'] not in ('supported', 'missing'):
                result['issues'].append(dict(code='FIELD_VALUE_AMBIGUOUS' if fact['status'] == 'ambiguous' else 'FIELD_VALUE_UNSUPPORTED',
                    field=field, charge_id=charge.get('charge_id'), source_id=charge.get('source_id'),
                    severity='error', repairable=True, message='；'.join(fact['reasons'])))
    totals = []
    for index, total in enumerate(payload.get('totals', [])):
        linked = link_evidence(dict(sources=payload.get('sources', []), revision=payload.get('revision'),
            charges=[dict(total, charge_id=f'_total:{index}')])) if total.get('evidence') else None
        entry = deepcopy(total)
        entry.update(total_index=index, evidence=linked['charges'][0]['evidence'] if linked else [])
        entry['field_support'] = {field: field_support(entry, field, total=True) for field in ('amount', 'currency')}
        totals.append(entry)
        if linked:
            result['issues'].extend(dict(i, field='totals.evidence', total_index=index) for i in linked['issues'])
            for field in ('amount', 'currency'):
                fact = entry['field_support'][field]
                if fact['status'] != 'supported' and fact.get('ambiguity_kind') != 'location':
                    result['issues'].append(dict(code='TOTAL_VALUE_UNSUPPORTED', field=f'totals.{field}',
                        total_index=index, source_id=total.get('source_id'), severity='error', repairable=True,
                        message=f'声明总额的{field}与所引用原文不一致或缺少支持；不能用计算合计替代原文总额'))
    result['total_evidence'] = totals
    result['valid'] = not result['issues']
    return result


def validate_repair(payload: dict) -> dict:
    """Reject a nonempty replacement that loses a previously supported fact.

    Both sides are read back against the same current immutable sources; saved
    verified flags are not trusted. Explicit null is a valid correction, and a
    changed value with its own support is allowed. No value/ref is invented.
    """
    previous, candidate = payload['previous'], payload['candidate']
    before = validate_evidence(dict(previous, records=[]))
    after = validate_evidence(dict(candidate, sources=previous.get('sources', []), records=[]))
    old = {row['charge_id']: row for row in before['charges'] if row.get('charge_id')}
    issues = []
    for row in after['charges']:
        prior = old.get(row.get('charge_id'))
        if not prior:
            continue
        for field in SUPPORT_FIELDS:
            if (row.get(field) is not None and
                    prior['field_support'][field]['status'] == 'supported' and
                    row['field_support'][field]['status'] != 'supported'):
                issues.append(dict(code='EVIDENCE_REGRESSION', charge_id=row['charge_id'],
                    field=field, severity='error', message='修改后的非空值失去原文支持；保留已保存候选供复核'))
    return dict(valid=not issues, issues=issues)


def build_preview(payload: dict) -> dict:
    """Project saved source blocks and resolve a display target without inventing geometry.

    This is a read-only representation of a source, not another extraction or
    a new financial judgement. HTML is never generated from document content.
    """
    source = payload['source']
    request = deepcopy(payload.get('target') or {})
    saved_record = None
    if request.get('charge_id'):
        records = payload.get('records') or payload.get('charges') or []
        found = [r for r in records if r.get('charge_id') == request['charge_id']]
        if len(found) == 1:
            saved_record = found[0]
            field = str(request.get('field', '')).split('.')[-1]
            group = 'document_info' if field == 'reference_no' else 'charge_details'
            saved_value = found[0].get(group, {}).get(field, found[0].get(field))
            if field in ('reference_no', 'charge_item', 'amount', 'currency', 'payment_term'):
                request.update(field=field, value=saved_value)
    blocks = source.get('blocks') or [dict(anchor='text', text=source.get('text', ''))]
    visible_keys = ('anchor', 'text', 'kind', 'page', 'sheet', 'row', 'column',
                    'table', 'cell', 'paragraph', 'cells', 'hidden', 'authoritative',
                    'structure_only', 'render_version', 'merged_cells', 'cell_anchor')
    projected = [{k: deepcopy(b[k]) for k in visible_keys if k in b} for b in blocks]
    anchor, quote = request.get('anchor'), request.get('quote')
    matches = [b for b in blocks if (not anchor or b.get('anchor', 'text') == anchor)
               and (not quote or quote in str(b.get('text', '')))] if anchor or quote else []
    target = dict(field=request.get('field'), quote=quote, located=False,
                  location_level='file', reason='尚未选择可定位的原文引用')
    if request.get('value') is not None:
        target['value'] = str(request['value'])
    if saved_record and request.get('field') == 'charge_item':
        target['display_value'] = saved_record.get('charge_details', {}).get('original_charge_item')
    render = None
    preview = source.get('metadata', {}).get('office_preview') or {}
    if preview.get('format') == 'pdf' and preview.get('sha256'):
        render = dict(kind='pdf', sha256=preview['sha256'], version=preview['sha256'],
                      page_count=preview.get('page_count'), authoritative=False)
    if len(matches) == 1:
        block = matches[0]
        text = str(block.get('text', ''))
        # An anchor locates a block; a repeated quote cannot identify a unique
        # occurrence within that block. Preserve the block location honestly.
        unique_quote = not quote or text.count(quote) == 1
        target.update({k: deepcopy(block[k]) for k in
                       ('anchor', 'page', 'sheet', 'row', 'column', 'table', 'cell',
                        'paragraph', 'render_version') if k in block})
        target.update(located=True, location_level='block',
                      reason='已定位原件内容块' if unique_quote else '已定位内容块；引用在块内重复')
        target['context'] = quote or text
        if len(str(quote or text).strip()) < 12:
            parent_rows = [b for b in blocks if b.get('table') == block.get('table') and
                           b.get('row') == block.get('row') and b.get('structure_only') and
                           block.get('table') is not None]
            if len(parent_rows) == 1:
                target['context'] = parent_rows[0].get('text', target['context'])
        value = request.get('value')
        raw_cells = block.get('cells') or []
        cells = [cell for row in raw_cells for cell in (row if isinstance(row, list) else [row])
                 if isinstance(cell, dict)]
        if value is not None and cells:
            value_text = str(value).strip()
            def supports(cell):
                displayed = str(cell.get('text', cell.get('value', ''))).strip()
                if request.get('field') == 'amount':
                    expected = _canonical_decimal(value)
                    return any(token['candidates'] == [expected] for token in numeric_tokens(displayed))
                return bool(value_text and value_text in displayed)
            matched_cells = [c for c in cells if supports(c) and not c.get('merged_proxy') and not c.get('merge_proxy')]
            if len(matched_cells) == 1:
                cell = matched_cells[0]
                target.update(location_level='cell', reason='已定位原件表格单元格')
                for key in ('column', 'cell', 'coordinate'):
                    if key in cell:
                        target[key] = deepcopy(cell[key])
                target['cell_anchor'] = cell.get('anchor', cell.get('coordinate'))
                target['value'] = value_text
            elif len(matched_cells) > 1:
                target['reason'] = '该行有多个相同值，已定位行；请核对对应列'
        # Only a saved, explicitly dimensioned box can be rendered. Unknown OCR
        # coordinate formats stay unknown instead of becoming plausible boxes.
        bbox = block.get('bbox')
        if isinstance(bbox, dict) and bbox.get('unit') in ('normalized', 'pixel'):
            keys = ('x', 'y', 'width', 'height')
            if all(isinstance(bbox.get(k), (int, float)) and not isinstance(bbox[k], bool)
                   and math.isfinite(bbox[k]) for k in keys) and bbox['width'] > 0 and bbox['height'] > 0:
                if bbox['unit'] == 'normalized' and all(0 <= bbox[k] <= 1 for k in keys) or (
                        bbox['unit'] == 'pixel' and bbox.get('image_width', 0) > 0 and bbox.get('image_height', 0) > 0):
                    target['bbox'] = {k: bbox[k] for k in (*keys, 'unit', 'image_width', 'image_height') if k in bbox}
        target['authoritative'] = block.get('authoritative', source.get('authoritative', True)) is not False
        mapping = block.get('preview') or {}
        render_pages = mapping.get('pages', [])
        if render and mapping.get('artifact_sha256') == render['sha256'] and render_pages and all(
                type(p) is int and 1 <= p <= (render.get('page_count') or 0) for p in render_pages):
            target.update(render_page=render_pages[0], render_pages=render_pages, render_version=render['version'])
    elif anchor or quote:
        target['reason'] = '原文引用不唯一，无法精确定位' if matches else '未在已保存原文中找到该引用'
    kind = str(source.get('format', '')).lower()
    if kind in ('xls', 'xlsx', 'doc', 'docx'):
        kind = 'office'
    elif kind in ('png', 'jpg', 'jpeg', 'tif', 'tiff', 'bmp', 'webp', 'image'):
        kind = 'image'
    elif kind != 'pdf':
        kind = 'text'
    result = dict(source_id=source.get('source_id'), revision=payload.get('revision'),
                name=source.get('name', source.get('filename', '材料')), kind=kind,
                blocks=projected, target=target, authoritative=source.get('authoritative', True),
                preview_version='1.3.0', source_version=source.get('source_version', source.get('version', 1)),
                representation='original_structure' if kind == 'office' else 'original_file',
                content_sha256=source.get('content_id'), render=render, valid=True)
    if payload.get('original_path') and (kind in ('pdf', 'image') or render):
        try:
            _original_locator().locate(result, payload['original_path'], numeric_tokens=numeric_tokens,
                          currency_tokens=currency_tokens, decimal=_canonical_decimal,
                          cache_dir=payload.get('location_cache_dir'))
        except Exception as exc:
            result['original'] = dict(status='error', locations=[],
                reason=f'原件定位失败: {type(exc).__name__}: {exc}')
    return result


def main(argv=None):
    """Call one existing evidence function with portable JSON file/stdio IO."""
    import argparse
    from contextlib import ExitStack
    from pathlib import Path
    import simplejson
    import sys

    operations = {"link_evidence": link_evidence, "validate_evidence": validate_evidence,
                  "build_preview": build_preview}
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", help="Input JSON path; omit or use - for stdin")
    parser.add_argument("--output", help="Output JSON path; omit or use - for stdout")
    parser.add_argument("--operation", choices=operations, default="link_evidence")
    args = parser.parse_args(argv)
    with ExitStack() as stack:
        try:
            source = (stack.enter_context(Path(args.input).open(encoding="utf-8-sig"))
                      if args.input and args.input != "-" else sys.stdin)
            payload = simplejson.load(source, use_decimal=True)
            if not isinstance(payload, dict):
                raise ValueError("Input must be a JSON object")
            result = operations[args.operation](payload)
        except (ValueError, OSError) as exc:
            result = {"valid": False, "issues": [{"code": "CLI_INPUT", "message": str(exc), "severity": "error"}]}
        try:
            destination = (stack.enter_context(Path(args.output).open("w", encoding="utf-8"))
                           if args.output and args.output != "-" else sys.stdout)
            simplejson.dump(result, destination, use_decimal=True, ensure_ascii=False, allow_nan=False)
            destination.write("\n")
        except OSError as exc:
            print(f"CLI_OUTPUT: {exc}", file=sys.stderr)
            return 1
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
