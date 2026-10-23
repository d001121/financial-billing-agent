"""Task-bound native tools invoking the independent business Skills."""
import asyncio
from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path
from typing import Literal
from uuid import uuid4
from langchain.tools import tool, ToolRuntime
from langchain.messages import ToolMessage
from langgraph.types import Command
from langchain_core.tools import ToolException
import redis
from backend.extensions.skill_versions import function, skill_module
from backend.infrastructure.repository import repository, dumps, loads, now, Conflict
from backend.config.settings import ASSETS, DATA, OCR_URL, office_converter
from backend.config.transactions import read_config
from backend.harness.dispatch import check, PolicyDenied
from backend.harness.stopping import RepairStop
from backend.infrastructure.assets import add_storage_references, asset_file
from .artifacts import save_fields, reconcile_saved, validate_and_store, validation_tool, verification_summary
from .context import context_tool
from .human_input import human_input_tool


TOOL_SKILLS = {
    'record_review_decision': 'human-review',
    'intake_documents': 'document-intake',
    'prepare_document_extraction': 'document-extraction',
    'read_document_sources': 'document-extraction',
    'read_markdown_evidence': 'document-extraction',
    'read_materials': 'document-extraction',
    'view_source_image': 'document-extraction',
    'save_document_extraction': 'document-extraction',
    'link_task_evidence': 'evidence-linking',
    'reconcile_task_charges': 'billing-reconciliation',
    'prepare_export': 'billing-export',
    'assess_task_confidence': 'billing-confidence',
    'search_reviewed_experiences': 'feedback-improvement',
}


def tools_for(task_id, capability, allowed_skills=None, *, allowed_tools=None):
    """Bind known portable package functions to task storage; no loop or script runner."""
    cap = capability

    def ocr_options(task, revision, runtime=None, cache=False):
        """Inject host credentials; never expose them as model/tool arguments."""
        options = dict(ocr_response_format=os.environ.get('OCR_RESPONSE_FORMAT', 'text'),
            obs_options={'enabled': os.environ.get('OBS_ENABLE', 'false').lower() == 'true',
                **{key: os.environ.get(env, '') for key, env in {
                    'access_key_id': 'OBS_ACCESS_KEY_ID', 'secret_access_key': 'OBS_SECRET_ACCESS_KEY',
                    'server': 'OBS_SERVER', 'bucket': 'OBS_BUCKET', 'security_token': 'OBS_SECURITY_TOKEN',
                    'object_prefix': 'OBS_OBJECT_PREFIX', 'socket_timeout': 'OBS_SOCKET_TIMEOUT'}.items()}},
            request_guard=lambda: check(task_id, revision=revision, skill='document-intake', policy_only=True))
        if cache:
            def progress(event):
                if event['stage'] != 'ocr_complete':
                    check(task_id, revision=revision, skill='document-intake', policy_only=True)
                event = deepcopy(event)
                preview = event.pop('preview', None)
                stage = event['stage']
                if preview:
                    add_storage_references(preview)
                    def publish(current):
                        sources = {s['source_id']: s for s in current.get('sources', [])}
                        sources.setdefault(preview['source_id'], preview)
                        current['sources'] = list(sources.values())
                        previews = {p['source_id']: p for p in current.get('intake_preview', [])}
                        previews[preview['source_id']] = dict(source_id=preview['source_id'], name=preview['name'],
                            rows=preview['metadata'].get('financial_rows', []))
                        current.update(intake_preview=list(previews.values()), intake_progress=event,
                            summary=f'已读取{preview["name"]}，正在核对识别结果')
                    repo = repository()
                    repo.mutate('task', task_id, publish, expected_revision=revision)
                    if hasattr(repo, 'flush'):
                        repo.flush(task_id)
                else:
                    from .artifacts import save_fields_fast
                    save_fields_fast(task_id, revision, intake_progress=event)
                repository().event(task_id, 'ocr_receipt' if stage == 'ocr_complete' else 'intake_progress',
                    revision=revision, **event)
                if runtime is not None:
                    runtime.stream_writer(dict(type='intake_progress', **event))
            options.update(ocr_cache_dir=DATA / 'cache' / 'ocr',
                ocr_cache_ttl=int(os.environ.get('OCR_CACHE_TTL', '86400')),
                ocr_cache_version=os.environ.get('OCR_CACHE_VERSION', 'orderChange-v1'), on_progress=progress)
        return options

    def with_material_files(response, sources, runtime, name):
        if runtime is None or not extraction_module or not hasattr(extraction_module, 'markdown_files'):
            return response
        files = extraction_module.markdown_files(dict(sources=sources))
        if not files:
            return response
        return Command(update=dict(files=files, messages=[ToolMessage(
            content=dumps(response), tool_call_id=runtime.tool_call_id, name=name)]))

    def compact_reading(reading):
        """Manifest only: the model reads the body once through read_materials."""
        return dict(mode=reading.get('mode'), materials=reading.get('materials', []),
            content_returned=False,
            instruction='接入只返回材料清单，正文未展开。短材料调用 read_materials 一次读取；'
                '只有 read_materials 返回 mode=search 时才用 /materials/*.md 的 grep/read_file。'
                '引用直接使用 read_materials 返回的 [r...]；不要重复读取已 pin 的 SKILL.md。')


    @tool
    async def intake_documents(asset_ids: list[str] | None = None,
                               source_urls: dict[str, str] | None = None,
                               ocr_text_pointer: str | None = None,
                               include_content: bool = True, runtime: ToolRuntime = None) -> dict:
        """接入当前任务的原件并返回材料清单（来源、状态、行数、issues），不展开正文。
        asset_ids参数仅作提示，实际材料范围始终取当前任务；正文请随后调用 read_materials。"""
        task = await asyncio.to_thread(check, task_id, skill='document-intake')
        if source_urls is not None or ocr_text_pointer is not None:
            def supplement(current):
                if source_urls is not None:
                    current['source_urls'] = {**current.get('source_urls', {}), **source_urls}
                if ocr_text_pointer is not None:
                    current['ocr_text_pointer'] = ocr_text_pointer
            task = await asyncio.to_thread(repository().mutate, 'task', task_id, supplement,
                                           expected_revision=task['revision'])
        revision = task['revision']
        # The task owns its material set.  A model-transcription error in the
        # asset id must not crash the run or silently drop attachments.
        ids = list(task['asset_ids'])
        semaphore = asyncio.Semaphore(cap['config']['runtime']['document_concurrency'])
        current_format = os.environ.get('OCR_RESPONSE_FORMAT', 'text')
        current_pointer = task.get('ocr_text_pointer')
        reusable = {r['asset_id']: r for r in task.get('intake', [])
                    if r.get('asset_id') and r.get('sources') and not r.get('issues')
                    and all(s.get('status') == 'ready' for s in r['sources'])
                    and r.get('ocr_response_format', 'text') == current_format
                    and r.get('ocr_text_pointer') == current_pointer}
        def parse(asset):
            module = skill_module('document-intake', cap['version'])
            # An OCR retry/new task must retain the earlier wire response.
            output = ASSETS / asset['id'] / 'parsed' / str(uuid4())
            url_map = task.get('source_urls', {})
            # Credentials stay in this host closure, outside tool/model/task data.
            intake_options = {}
            if hasattr(module, 'OBSPublisher'):
                intake_options = ocr_options(task, revision, runtime, cache=getattr(module, 'RAW_OCR_CACHE', False))
            if hasattr(module, 'PDF_TEXT_MODES'):
                intake_options['pdf_text_mode'] = 'markdown' if getattr(module, 'MARKDOWN_FIRST', False) else 'ocr_only'
            if hasattr(module, 'ATTACHMENT_CONCURRENCY'):
                intake_options['attachment_concurrency'] = max(1,
                    cap['config']['runtime']['document_concurrency'] // max(1, len(ids)))
            if getattr(module, 'IMAGE_TEXT_OCR', False):
                intake_options['image_text_ocr'] = os.environ.get('IMAGE_TEXT_OCR_ENABLE', 'true').lower() == 'true'
            def resolver(path, mapping):
                pages = mapping.get('original_pages', [])
                ranged = (f"{mapping.get('source_id')}:pages:{pages[0]}-{pages[-1]}" if pages else
                          f"{mapping.get('source_id')}:frame:{mapping.get('frame')}" if mapping.get('frame') else None)
                generated = path.is_relative_to(output) and path.relative_to(output).parts[0] in ('pdf-slices', 'image-frames')
                return url_map.get(ranged) or url_map.get(path.name) or (
                    url_map.get(mapping.get('source_id', '')) if not generated else None)
            key = 'bishi1:intake:' + sha256(dumps([asset['id'], asset['sha256'], asset.get('source_url'), url_map,
                                                  cap['version'], OCR_URL, task.get('ocr_text_pointer'),
                                                  office_converter(), True,
                                                  intake_options.get('ocr_response_format'), intake_options.get('pdf_text_mode'),
                                                  intake_options.get('image_text_ocr', False),
                                                  {k: intake_options.get('obs_options', {}).get(k)
                                                   for k in ('enabled', 'server', 'bucket', 'object_prefix')}]).encode()).hexdigest()
            cache = redis.Redis.from_url(os.environ['REDIS_URL'], socket_timeout=3)
            try:
                cached = cache.get(key)
            except redis.RedisError:
                cached = None
            if cached:
                return loads(cached)
            result = module.intake_document(str(ASSETS / asset['relative_path']),
                        source_url=asset.get('source_url'), output_dir=str(output),
                        ocr_endpoint=OCR_URL, url_resolver=resolver,
                        ocr_text_pointer=task.get('ocr_text_pointer'), occurrence_id=asset['id'],
                        pdf_pages_per_slice=cap['config']['runtime'].get('pdf_pages_per_slice', 20),
                        doc_converter=office_converter(), **intake_options)
            result['asset_id'] = asset['id']
            result['ocr_response_format'] = intake_options.get('ocr_response_format')
            result['ocr_text_pointer'] = task.get('ocr_text_pointer')
            if not result.get('issues'):
                try:
                    cache.setex(key, 86400, dumps(result))
                except redis.RedisError:
                    pass  # Cache is optional; the source artifact remains durable.
            return result
        async def one(asset_id):
            async with semaphore:
                if asset_id in reusable and source_urls is None and ocr_text_pointer is None:
                    # Durable task artifacts include supplementary reads. A new
                    # turn must not replace them with an earlier Redis snapshot.
                    return deepcopy(reusable[asset_id])
                return await asyncio.to_thread(parse, repository().get('asset', asset_id))
        parsed = await asyncio.gather(*(one(a) for a in ids))
        add_storage_references(parsed)
        def store(current):
            indexed = {r['asset_id']: r for r in current.get('intake', []) if r.get('asset_id')}
            indexed.update({r['asset_id']: r for r in parsed})
            all_results = list(indexed.values())
            sources = [s for r in all_results for s in r.get('sources', [])]
            issues = [i for r in all_results for i in r.get('issues', [])]
            current.update(sources=sources, intake=all_results, intake_issues=issues,
                           status='processing', summary=f'已接入{len(sources)}个材料出现位置',
                           intake_progress=dict(stage='complete'))
            current.pop('intake_preview', None)
        saved = await asyncio.to_thread(repository().mutate, 'task', task_id, store, expected_revision=revision)
        sources, issues = saved['sources'], saved['intake_issues']
        response = dict(sources=[{k: s.get(k) for k in ('source_id', 'name', 'status', 'format')}
                             for s in sources], issues=issues,
                    artifact=f'/api/tasks/{task_id}/artifacts')
        if include_content and 'document-extraction' in enabled:
            if getattr(extraction_module, 'BUNDLE_READING', False):
                response['reading'] = compact_reading(
                    await asyncio.to_thread(extraction_module.read_materials, saved))
            else:
                response['extraction'] = await asyncio.to_thread(prepare_document_extraction.func, limit=12)
        return with_material_files(response, sources, runtime, 'intake_documents')

    @tool
    def prepare_document_extraction(offset: int = 0, limit: int = 8, source_id: str | None = None,
                                    runtime: ToolRuntime = None) -> dict:
        """读取Markdown目录和覆盖分块编号；用原生grep/read_file定位，再回读引文。旧材料仍支持分页。"""
        task = check(task_id, skill='document-extraction')
        if not task.get('sources'):
            raise ValueError('请先实际接入材料')
        if getattr(extraction_module, 'BUNDLE_READING', False):
            return with_material_files(extraction_module.read_materials(task), task['sources'], runtime,
                                       'prepare_document_extraction')
        result = function(cap, 'document-extraction', 'prepare_extraction')(task)
        save_fields(task_id, task['revision'], chunks=result['chunks'], preparation=result)
        chunks = [c for c in result['chunks'] if source_id is None or c['source_id'] == source_id]
        if any(s.get('markdown') for s in task['sources']) and hasattr(extraction_module, 'markdown_manifest'):
            selected = chunks[max(0, offset):max(0, offset) + min(12, max(1, limit))]
            response = dict(materials=extraction_module.markdown_manifest(task),
                chunks=[{k: c[k] for k in ('chunk_id', 'source_id', 'anchor', 'owned_range', 'page', 'sheet', 'row') if k in c}
                        for c in selected], total_chunks=len(chunks), bundle_total_chunks=len(result['chunks']),
                issues=result.get('issues', []),
                instruction='全文已在/materials/*.md。使用原生grep(output_mode=content)定位，read_file按行阅读；'
                    '引用时read_markdown_evidence获取真实原文偏移。全部文件都需检查，未命中不是不存在；表格逐行和跨页须扩读。')
            return with_material_files(response, task['sources'], runtime, 'prepare_document_extraction')
        response = dict(total_chunks=len(chunks), bundle_total_chunks=len(result['chunks']),
                    chunks=chunks[max(0, offset):max(0, offset) + min(12, max(1, limit))],
                    material_bundle=result.get('material_bundle'),
                    issues=result.get('issues', []),
                    instruction='每块必须有coverage；authoritative=false的正文不得支持正式费用。逐批保存，所有块完成后再校验。')
        return (extraction_module.extraction_view(response) if hasattr(extraction_module, 'extraction_view') else response)

    enabled = {s['name'] for s in cap['config']['skills']['skills'] if s.get('enabled', True)}
    extraction_module = (skill_module('document-extraction', cap['version'])
                         if 'document-extraction' in enabled else None)
    extraction_type = extraction_module.ExtractionResult if extraction_module else dict

    @tool
    def read_materials(windows: list[dict] | None = None, max_chars: int = 32000,
                       runtime: ToolRuntime = None) -> dict:
        """批量阅读本任务材料，默认整包短Markdown；长材料可一次指定多个source_id/start_line/end_line窗口。引用直接复制[r...]。"""
        task = check(task_id, skill='document-extraction')
        try:
            result = extraction_module.read_materials(dict(task, windows=windows, max_chars=max_chars))
        except ValueError as exc:
            raise ToolException(str(exc)) from exc
        return with_material_files(result, task['sources'], runtime, 'read_materials')

    read_materials.handle_tool_error = True

    @tool
    def read_document_sources(source_ids: list[str], method: Literal['text', 'layout', 'ocr'],
                              reason: str, pages: list[int] | None = None,
                              frame: int | None = None, runtime: ToolRuntime = None) -> dict:
        """按需补读任务原件。text/layout读PDF文字；ocr调用指定OCR读PDF原页或图片帧，只返回文本目录。"""
        task = check(task_id, skill='document-extraction')
        indexed = {s['source_id']: s for s in task.get('sources', [])}
        if not source_ids or any(sid not in indexed for sid in source_ids):
            raise ToolException('补读材料不属于当前任务；请从材料清单选择真实source_id')
        if method != 'ocr' and any(indexed[sid].get('format') != 'pdf' for sid in source_ids):
            raise ToolException('text/layout补读仅支持PDF。图片/EML/Office请用prepare_document_extraction(source_id=真实ID)读取已接入正文/OCR块；不能将图片按PDF补读。')
        if method == 'ocr' and any(indexed[sid].get('format') not in {'pdf', 'image'} for sid in source_ids):
            raise ToolException('OCR补读仅支持PDF原页或图片帧')
        reads = []
        for sid in dict.fromkeys(source_ids):
            check(task_id, revision=task['revision'], skill='document-extraction')
            source = indexed[sid]
            payload = dict(source=source, method=method, reason=reason, pages=pages)
            if method == 'layout':
                payload['path'] = str(asset_file(source))
            try:
                intake_module = skill_module('document-intake', cap['version'])
                if method == 'ocr':
                    if allowed_skills is not None and 'document-intake' not in allowed_skills:
                        raise ToolException('当前专家未获OCR接入能力')
                    check(task_id, revision=task['revision'], skill='document-intake')
                    if not hasattr(intake_module, 'supplement_ocr'):
                        raise ToolException('当前任务固定的历史Skill不支持按页OCR补读')
                    output = ASSETS / 'derived' / task_id / str(uuid4())
                    def resolver(path, mapping):
                        original = mapping.get('original_pages', [])
                        key = (f'{sid}:pages:{original[0]}-{original[-1]}' if original else
                               f'{sid}:frame:{mapping.get("frame")}')
                        return task.get('source_urls', {}).get(key)
                    read = intake_module.supplement_ocr(source, path=asset_file(source), output_dir=output,
                        reason=reason, pages=pages, frame=frame, ocr_endpoint=OCR_URL,
                        ocr_text_pointer=task.get('ocr_text_pointer'), url_resolver=resolver,
                        **ocr_options(task, task['revision'], runtime, cache=getattr(intake_module, 'RAW_OCR_CACHE', False)))
                else:
                    read = function(cap, 'document-extraction', 'supplement_pdf')(payload)
                    if source.get('markdown') and read['added_anchors'] and hasattr(intake_module, 'write_markdown'):
                        check(task_id, revision=task['revision'], skill='document-intake')
                        output = ASSETS / 'derived' / task_id / str(uuid4())
                        md = intake_module.write_markdown(read['source'], output)
                        read['artifacts'] = [dict(path=md[key], kind=kind, source_id=sid)
                            for key, kind in [('path', 'markdown'), ('map_path', 'markdown_map')]]
                add_storage_references(read)
                reads.append(read)
            except ValueError as exc:
                raise ToolException(str(exc)) from exc

        def apply(current):
            replacements = {r['source']['source_id']: r['source'] for r in reads}
            if any(s != indexed[s['source_id']] for s in current.get('sources', [])
                   if s['source_id'] in replacements):
                raise ValueError('补读期间该来源已更新，请读取最新材料后重试')
            # Preserve other sources and synchronize the persisted intake bundle.
            current['sources'] = [deepcopy(replacements.get(s['source_id'], s))
                                  for s in current.get('sources', [])]
            for intake in current.get('intake', []):
                intake['sources'] = [deepcopy(replacements.get(s['source_id'], s))
                                     for s in intake.get('sources', [])]
                owned = {s['source_id'] for s in intake.get('sources', [])}
                for read in reads:
                    if read['source']['source_id'] in owned:
                        intake.setdefault('artifacts', []).extend(deepcopy(read.get('artifacts', [])))
                        intake.setdefault('issues', []).extend(deepcopy(read.get('issues', [])))
            current.setdefault('intake_issues', []).extend(
                deepcopy(issue) for read in reads for issue in read.get('issues', []))
            if not getattr(extraction_module, 'BUNDLE_READING', False):
                result = function(cap, 'document-extraction', 'prepare_extraction')(current)
                current.update(chunks=result['chunks'], preparation=result)
            if any(r['added_anchors'] or r.get('issues') for r in reads):
                current.update(evidence=None, validation=None, approval=None, export=None,
                               auto_review=None, confidence_interrupt=None, last_export=None,
                               reconciliation=None, records=[], issues=[], status='processing')
        saved = repository().mutate('task', task_id, apply, expected_revision=task['revision'])
        added = {(r['source']['source_id'], anchor) for r in reads for anchor in r['added_anchors']}
        selected = [c for c in saved.get('chunks', []) if (c['source_id'], c['anchor']) in added]
        if not added and not any(r.get('issues') for r in reads):
            return dict(reads=[{k: v for k, v in r.items() if k not in {'source', 'artifacts'}} for r in reads],
                content_returned=False, instruction='没有新增原文；沿用已经读取的材料与引用，不再重复补读相同表示。')
        if getattr(extraction_module, 'BUNDLE_READING', False):
            response = dict(reads=[{k: v for k, v in r.items() if k not in {'source', 'artifacts'}} for r in reads],
                reading=extraction_module.read_materials(dict(saved, windows=[dict(source_id=sid) for sid in source_ids])))
            return with_material_files(response, saved['sources'], runtime, 'read_document_sources')
        if any(s.get('markdown') for s in saved['sources']):
            response = dict(reads=[{k: v for k, v in r.items() if k not in {'source', 'artifacts'}} for r in reads],
                materials=extraction_module.markdown_manifest(saved),
                instruction='Markdown已更新；用原生grep/read_file定向读取新增表示，旧证据和覆盖仍保留。')
            return with_material_files(response, saved['sources'], runtime, 'read_document_sources')
        return dict(reads=[{k: v for k, v in r.items() if k not in {'source', 'artifacts'}} for r in reads],
                    bundle_total_chunks=len(saved['chunks']), total_chunks=len(selected),
                    chunks=selected[:12],
                    instruction='仅返回本次新增块，先前已读块仍存档且需coverage。超过12块请定向分页；不重复生成费用。')

    # Native tool handling returns a failed ToolMessage for correctable inputs.
    read_document_sources.handle_tool_error = True

    @tool
    def read_markdown_evidence(source_id: str, start_line: int = 1, limit: int = 60) -> dict:
        """将已定位的Markdown行回读为真实原文、anchor及字符偏移；不调用模型，不把搜索命中当全文读取。"""
        task = check(task_id, skill='document-extraction')
        try:
            result = function(cap, 'document-extraction', 'read_markdown_evidence')(
                dict(sources=task['sources'], source_id=source_id, start_line=start_line, limit=limit))
        except ValueError as exc:
            raise ToolException(str(exc)) from exc
        receipt = {k: result[k] for k in ('source_id', 'markdown_sha256', 'start_line', 'end_line', 'total_lines', 'eof', 'truncated')}
        def store(current):
            current.setdefault('material_reads', []).append(receipt)
        repository().mutate('task', task_id, store, expected_revision=task['revision'])
        return result

    read_markdown_evidence.handle_tool_error = True

    @tool(response_format='content_and_artifact')
    def view_source_image(source_id: str, reason: str, frame: int = 1, page: int | None = None) -> tuple:
        """查看任务原图片的一帧或PDF指定原页；核对版式/缺口，返回原生多模态图片，不重复OCR。"""
        task = check(task_id, skill='document-extraction')
        source = next((s for s in task.get('sources', []) if s['source_id'] == source_id), None)
        if source is None:
            raise ToolException('原图不属于当前任务，请使用材料清单的真实source_id')
        if source.get('format') not in {'image', 'pdf'}:
            raise ToolException('原图工具只读取图片或PDF原页')
        if source.get('format') == 'pdf' and not hasattr(extraction_module, 'read_pdf_page'):
            raise ToolException('当前任务固定的历史Skill不支持PDF原页查看')
        try:
            result = function(cap, 'document-extraction', 'read_image')(
                dict(source=source, path=str(asset_file(source)), frame=frame, page=page, reason=reason))
        except ValueError as exc:
            raise ToolException(str(exc)) from exc
        def store(current):
            saved = next(s for s in current['sources'] if s['source_id'] == source_id)
            if saved.get('content_id') != source.get('content_id'):
                raise ValueError('读取期间原图已更新，请使用最新材料')
            saved.setdefault('metadata', {}).setdefault('visual_reads', []).append(result['receipt'])
            for intake in current.get('intake', []):
                for item in intake.get('sources', []):
                    if item['source_id'] == source_id:
                        item.setdefault('metadata', {})['visual_reads'] = deepcopy(saved['metadata']['visual_reads'])
        repository().mutate('task', task_id, store, expected_revision=task['revision'])
        return result['content'], result['receipt']

    view_source_image.handle_tool_error = True

    @tool
    def save_document_extraction(result: extraction_type, replace: bool = False,
                                 finalize: bool = (allowed_skills is None and
                                     cap['config']['runtime'].get('agent_style') == 'codex')) -> dict:
        """保存候选；主控默认完成代码核对并返回verification，可直接答复。
        分批暂存用finalize=false；按charge_id增量保存，修复时明确replace。"""
        task = check(task_id, skill='document-extraction')
        check(task_id, skill='human-review', policy_only=True)
        if finalize:
            for name in ('evidence-linking', 'billing-reconciliation', 'billing-confidence'):
                if allowed_skills is not None and name not in allowed_skills:
                    raise ToolException('当前专家未获财务核对能力，请保存候选交主控完成')
                check(task_id, revision=task['revision'], skill=name, policy_only=True)
        # Preserve omitted fields on a partial correction; explicit null still clears.
        candidate = result.model_dump(mode='python', exclude_unset=True)
        digest = sha256(dumps(candidate).encode()).hexdigest()
        def apply(current):
            if current.get('repair_revision', current['revision']) != current['revision']:
                current.update(candidate_digests=[], repair_attempts={})
            current['repair_revision'] = current['revision']
            if digest in current.get('candidate_digests', []):
                raise RepairStop('NO_PROGRESS', '相同候选没有进展，请转人工复核')
            existing_ranges = {c.get('chunk_id') for c in current.get('coverage', [])}
            affected = {c.get('chunk_id') for c in candidate.get('coverage', [])} & existing_ranges
            for collection, key in (('charges', 'charge_id'), ('documents', 'document_id')):
                existing_ids = {row.get(key) for row in current.get(collection, []) if row.get(key)}
                affected.update(f'{key}:{row[key]}' for row in candidate.get(collection, []) if row.get(key) in existing_ids)
            # Bundle-reading candidates need no chunk coverage. Anonymous corrections
            # still consume a source's repair allowance instead of bypassing it.
            existing_sources = {row.get('source_id') for row in current.get('charges', []) if row.get('source_id')}
            new_chunks = {c.get('chunk_id') for c in candidate.get('coverage', []) if c.get('chunk_id')} - existing_ranges
            if not new_chunks:
                # A save that adds no new chunk is a correction. Anonymous
                # corrections often omit source_id; their evidence still names
                # the source they are revising.
                for row in candidate.get('charges', []):
                    if row.get('charge_id'):
                        continue
                    sources = {row.get('source_id')} if row.get('source_id') else set()
                    sources |= {ref.get('source_id') for ref in row.get('evidence') or [] if ref.get('source_id')}
                    affected.update(f"source:{source_id}" for source_id in sources & existing_sources)
            if affected:
                attempts = current.setdefault('repair_attempts', {})
                for chunk_id in affected:
                    if attempts.get(chunk_id, 0) >= cap['config']['runtime']['repair_rounds']:
                        limit = cap['config']['runtime']['repair_rounds']
                        rounds = '两' if limit == 2 else str(limit)
                        raise RepairStop('REPAIR_LIMIT', f'该范围自动纠错已达{rounds}轮，请转人工复核')
                    attempts[chunk_id] = attempts.get(chunk_id, 0) + 1
            combined = function(cap, 'human-review', 'merge_extraction')(
                {'task': current, 'result': candidate, 'replace': replace})
            checked = function(cap, 'document-extraction', 'validate_extraction')(
                dict(result=combined, sources=current.get('sources', []), chunks=current.get('chunks', []),
                    records=current.get('records', [])))
            combined.update(checked)
            evidence_module = skill_module('evidence-linking', cap['version'])
            if hasattr(evidence_module, 'validate_repair'):
                guard = evidence_module.validate_repair(dict(previous=current, candidate=combined))
                if not guard['valid']:
                    raise RepairStop('EVIDENCE_REGRESSION',
                        '修复会破坏已有有效证据，候选未保存：' + dumps(guard['issues']))
            current.setdefault('candidate_digests', []).append(digest)
            current.update(extraction=combined, charges=combined.get('charges', []),
                           documents=combined.get('documents', []),
                           coverage=combined.get('coverage', []), totals=combined.get('totals', []),
                           validation=None, approval=None, export=None)
        saved = repository().mutate('task', task_id, apply, expected_revision=task['revision'])
        response = dict(saved=True, revision=saved['revision'], charges=len(saved.get('charges', [])),
                    coverage=len(saved.get('coverage', [])), issues=saved['extraction'].get('issues', []))
        if finalize:
            checked = reconcile_saved(task_id)
            response['history_lookup'] = checked.get('history_lookup')
            response['verification'] = verification_summary(checked['validation'])
            response['validation'] = (extraction_module.compact_feedback(checked['validation'])
                if getattr(extraction_module, 'BUNDLE_READING', False) else checked['validation'])
            response['record_count'] = checked['record_count']
            response['next'] = ('阅读verification和issues，仅修复有依据的误读；否则直接答复，宿主保存结果和缺口。无需prepare_export或重复link/validate/reconcile。'
                if getattr(extraction_module, 'BUNDLE_READING', False) else
                '仅定向修复真实错误；否则prepare_export结束或产生真实低置信度中断，无需再次link/validate/reconcile。')
        if getattr(extraction_module, 'BUNDLE_READING', False):
            response['issues'] = extraction_module.compact_feedback(response)['issues']
        # Decimal values in low-score feedback otherwise make native tools
        # fall back to Python repr, hiding the structured verification receipt.
        # Persisted financial values retain Decimal; only this projection is JSON.
        return json.loads(dumps(response))

    save_document_extraction.handle_tool_error = True

    @tool
    def link_task_evidence() -> dict:
        """用evidence-linking Skill回读引用并核验证据，不编造来源。"""
        task = check(task_id, skill='evidence-linking')
        result = function(cap, 'evidence-linking', 'link_evidence')(task)
        save_fields(task_id, task['revision'], charges=result.get('charges', task.get('charges', [])),
                    documents=result.get('documents', task.get('documents', [])), evidence=result)
        return dict(valid=result['valid'], issues=result.get('issues', []),
                    artifact=f'/api/tasks/{task_id}/artifacts')

    @tool
    def reconcile_task_charges(update_instructions: list[dict] | None = None) -> dict:
        """自动检索同主体历史并核对费用；明确更新时传update_instructions（target_id或reference_no+charge_item及changes），其余字段继承旧值。"""
        check(task_id, skill='billing-reconciliation')
        return json.loads(dumps(reconcile_saved(task_id, update_instructions)))


    @tool
    def assess_task_confidence() -> dict:
        """读取当前任务并执行统一Hook；Skill按已有值和阈值决定是否复核，缺失信息不计低分。"""
        from backend.hooks.validation import validate
        from .artifacts import confidence_payload
        task = check(task_id, skill='billing-confidence')
        return function(cap, 'billing-confidence', 'assess_confidence')(confidence_payload(task, validate(task)))

    @tool(return_direct=cap['config']['runtime'].get('agent_style') != 'codex',
          response_format='content_and_artifact')
    async def prepare_export() -> tuple[str, dict]:
        """保存可查看和修改的提取结果与缺口，完成本次任务；不执行财务记账。"""
        await asyncio.to_thread(check, task_id, skill='billing-export', policy_only=True)
        from .review import finalize_with_review
        task = await finalize_with_review(task_id)
        feedback = (extraction_module.compact_feedback(task['validation'])
                    if getattr(extraction_module, 'BUNDLE_READING', False) else task['validation'])
        result = dict(status=task['status'], revision=task['revision'], valid=task['export']['valid'],
                    issues=feedback['issues'], verification=verification_summary(task['validation']),
                    records=task.get('export', {}).get('records', task.get('records', [])))
        return dumps(result), dict(revision=task['revision'], verification=result['verification'])


    @tool
    def search_reviewed_experiences(query: str) -> dict:
        """按具体核对疑点检索当前主体已审核经验，最多3条；经验不是当前单据证据，缺失字段仍留空。"""
        task = check(task_id, skill='feedback-improvement')
        if (not cap['config']['runtime'].get('use_reviewed_experiences', True) or
                not read_config('runtime').get('use_reviewed_experiences', True)):
            return dict(experiences=[], role='reference_only', enabled=False,
                instruction='经验库使用已关闭，不检索或引用经验，依据当前原件继续处理。')
        records = []
        for pinned in cap.get('experiences', []):
            current = repository().get('experience', pinned['id'], required=False)
            if current and current.get('status') == 'active' and current['revision'] == pinned['revision']:
                records.append(pinned)
        found = function(cap, 'feedback-improvement', 'retrieve_experiences')(
            records, accounting_entity=task.get('accounting_entity'), query=query)
        for item in found:
            use_id = 'use-' + sha256(dumps([task_id, task['revision'], item['id'], item['revision']]).encode()).hexdigest()[:32]
            if repository().get('experience_use', use_id, required=False) is None:
                from psycopg.errors import UniqueViolation
                try:
                    repository().create('experience_use', dict(id=use_id, task_id=task_id,
                        task_title=task.get('title'), task_revision=task['revision'],
                        experience_id=item['id'], experience_revision=item['revision'],
                        query=query[:800], outcome='retrieved', at=now()))
                except UniqueViolation:
                    pass
        return dict(experiences=found, role='reference_only',
            instruction='仅参考适用条件与核对方法；历史单号、金额、币种和方向不能填入当前账单，仍须当前原件依据。')

    common = [context_tool(task_id), validation_tool(task_id), human_input_tool()]
    if (cap.get('experiences') and cap['config']['runtime'].get('use_reviewed_experiences', True)
            and read_config('runtime').get('use_reviewed_experiences', True)
            and (allowed_skills is None or 'feedback-improvement' in allowed_skills)):
        # Native common tool is visible without an extra Skill-discovery model round.
        common.append(search_reviewed_experiences)
    business = [intake_documents, prepare_document_extraction, save_document_extraction,
                link_task_evidence, reconcile_task_charges, assess_task_confidence, prepare_export]
    if extraction_module and hasattr(extraction_module, 'read_markdown_evidence'):
        business.insert(2, read_markdown_evidence)
    if extraction_module and hasattr(extraction_module, 'read_materials'):
        business.insert(2, read_materials)
    if extraction_module and hasattr(extraction_module, 'supplement_pdf'):
        business.insert(2, read_document_sources)
    if extraction_module and hasattr(extraction_module, 'read_image'):
        business.insert(3, view_source_image)
    enabled = {s['name'] for s in cap['config']['skills']['skills'] if s.get('enabled', True)}
    if allowed_skills is not None:
        enabled &= set(allowed_skills)
    business = [t for t in business if TOOL_SKILLS[t.name] in enabled]
    if allowed_tools is not None:
        common = [t for t in common if t.name in allowed_tools]
        business = [t for t in business if t.name in allowed_tools]
    return common, business
