"""Local LangSmith evaluation of the real supervisor on reviewed originals.

Default (offline): backend/python.cmd -m backend.evals.original_extraction
Paid single case: add --online-model --case png-debit-invoice
Remote OCR responses are immutable, hash-checked genuine-response replays;
the configured text model, native graph, middleware and business Skills run.
No production task/store, financial posting or LangSmith upload is performed.
These development labels are neither human-approved nor a final holdout.
"""
from __future__ import annotations

import argparse
import asyncio
from contextlib import ExitStack
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sys
import time
from types import SimpleNamespace
from unittest.mock import patch
from uuid import NAMESPACE_URL, uuid5

import httpx
from langchain_core.messages import messages_to_dict
from langgraph.checkpoint.memory import InMemorySaver
from langsmith import Client, aevaluate, tracing_context
from langsmith.schemas import Example

from backend.agents import factory
from backend.config.settings import WORKSPACE, SAMPLES
from backend.extensions import snapshots, skill_versions
from backend.infrastructure.repository import dumps, repository as production_repository
from backend.tests.test_host import FakeRepository

DATASET = Path(__file__).with_name('datasets') / 'original-extraction-dev.json'


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dumps(value), encoding='utf-8')


def replay_intake(case, directory, *, image_text=True):
    """Only input bytes and fixed OCR receipts enter the parser, never labels."""
    sample = SAMPLES / case['inputs']['sample']
    if digest(sample) != case['inputs']['sha256']:
        raise ValueError('Original sample hash changed: ' + sample.name)
    responses = {}
    for receipt in case['ocr_receipts']:
        path = WORKSPACE / receipt['response_path']
        if digest(path) != receipt['response_sha256']:
            raise ValueError('Original OCR receipt hash changed: ' + receipt['source_name'])
        responses[receipt['input_sha256']] = json.loads(path.read_text(encoding='utf-8'))
    calls = []

    def resolver(path, mapping):
        fingerprint = digest(path)
        if fingerprint not in responses:
            raise ValueError('No genuine response for original input ' + fingerprint)
        # A nonlocal test URL is never sent to the service: request is injected.
        return 'https://ocr-replay.invalid/' + fingerprint

    def request(endpoint, *, payload, timeout):
        fingerprint = payload['file'].rsplit('/', 1)[-1]
        calls.append(dict(input_sha256=fingerprint, mode='genuine_response_replay'))
        return httpx.Response(200, json=deepcopy(responses[fingerprint]),
                              request=httpx.Request('POST', endpoint))

    started = time.perf_counter()
    result = skill_versions.skill_module('document-intake').intake_document(
        sample, output_dir=directory / 'parsed', ocr_request=request,
        url_resolver=resolver, ocr_response_format='orderChange',
        pdf_text_mode='markdown', image_text_ocr=image_text,
        occurrence_id=case['case_id'], attachment_concurrency=3)
    result.update(asset_id=case['case_id'], ocr_response_format='orderChange',
                  ocr_text_pointer=None)
    write(directory / 'intake.json', result)
    write(directory / 'ocr-replay.json', dict(calls=calls,
        mode='genuine_response_replay', remote_requests=0,
        native_image_text=image_text, seconds=round(time.perf_counter() - started, 6)))
    if len(calls) != len(responses) or any(s['status'] != 'ready' for s in result['sources']):
        raise ValueError('Incomplete original OCR replay; see intake.json')
    return result


async def exercise(inputs, prepared, repo, capability, output):
    case_id = inputs['case_id']
    intake = prepared[case_id]
    task_id = 'eval-' + case_id
    instruction = ('根据本任务全部原件提取每项费用、单据编号、金额、币种和付款方式，'
                   '保留真实原文证据。没有提供的信息留null。仅生成可查看的账单建议。')
    task = dict(id=task_id, revision=1, capability=deepcopy(capability),
        title=case_id, accounting_entity=inputs.get('accounting_entity'),
        instructions=instruction, asset_ids=[case_id], intake=[deepcopy(intake)],
        sources=deepcopy(intake['sources']), intake_issues=deepcopy(intake.get('issues', [])),
        source_urls={}, ocr_text_pointer=None, thread_id=task_id, run_id=None,
        control='running', status='queued', existing_records=[], update_instructions=[],
        records=[], charges=[], issues=[], coverage=[], totals=[],
        reason='隔离开发评测', validation=None, approval=None, export=None,
        usage=dict(model_calls=0, tool_calls=0, active_seconds=0))
    repo.objects['task', task_id] = deepcopy(task)
    repo.objects['asset', case_id] = dict(id=case_id, name=inputs['sample'],
        sha256=inputs['sha256'], relative_path='samples/' + inputs['sample'],
        source_url=None)
    config = dict(configurable=dict(task_id=task_id, thread_id=task_id, task_revision=1),
                  recursion_limit=capability['config']['runtime']['graph_recursion_limit'])
    started = time.perf_counter()
    state, error = {}, None
    print(json.dumps(dict(stage='model_start', case_id=case_id), ensure_ascii=False), flush=True)
    try:
        async with factory.make_graph(config, SimpleNamespace(execution_runtime=None)) as compiled:
            # Agent Server supplies its checkpointer in production. This local
            # evaluation compiles the same native builder with native memory.
            graph = compiled.builder.compile(checkpointer=InMemorySaver(), name=compiled.name)
            async for namespace, update in graph.astream(
                {**skill_versions.skill_state(capability, task),
                 'messages': [dict(role='user', content=instruction)]},
                config=config, stream_mode='updates', subgraphs=True):
                for node, values in update.items():
                    if isinstance(values, dict) and values.get('messages'):
                        messages = values['messages']
                        if not isinstance(messages, list):
                            messages = [messages]
                        names = [c['name'] for m in messages for c in getattr(m, 'tool_calls', [])]
                        if names:
                            print(json.dumps(dict(stage='tools_proposed', case_id=case_id,
                                namespace=list(namespace), tools=names)), flush=True)
            state = (await graph.aget_state(config)).values
    except Exception as exc:
        # Evaluation errors remain failures with saved partial artifacts.
        error = f'{type(exc).__name__}: {exc}'
    current = repo.get('task', task_id)
    receipts = repo.events(task_id, limit=10000)
    write(output / case_id / 'task.json', current)
    write(output / case_id / 'receipts.json', receipts)
    write(output / case_id / 'trajectory.json', messages_to_dict(state.get('messages', [])))
    result = dict(records=current.get('records', []), status=current['status'],
        validation_ok=(current.get('validation') or {}).get('ok'),
        error=error, usage=current['usage'], seconds=round(time.perf_counter() - started, 3),
        case_id=case_id, approval=current.get('approval'),
        review_request=current.get('review_request'))
    write(output / case_id / 'outputs.json', result)
    print(json.dumps(dict(stage='model_end', case_id=case_id,
        rows=len(result['records']), status=result['status'],
        error=error, seconds=result['seconds']), ensure_ascii=False), flush=True)
    return result


async def main(args):
    dataset = json.loads(DATASET.read_text(encoding='utf-8'))
    cases = [c for c in dataset['cases'] if not args.case or c['case_id'] in args.case]
    if not cases:
        raise ValueError('Unknown case')
    output = Path(args.output).resolve() if args.output else WORKSPACE / 'backend/tests/reports' / (
        'original-extraction-' + datetime.now().strftime('%Y%m%d-%H%M%S'))
    output.mkdir(parents=True, exist_ok=True)
    prepared = {c['case_id']: replay_intake(c, output / c['case_id'],
        image_text=not args.no_image_text) for c in cases}
    if args.prepare_only or not args.online_model:
        print(json.dumps(dict(stage='prepared', output=str(output), cases=len(cases))))
        return
    repo = FakeRepository()  # Existing host test store; never a production connection.
    wires = []
    original_factory = factory.make_model

    def observed_factory(task_id, runtime):
        model, client = original_factory(task_id, runtime)

        async def observe(request):
            if request.method == 'POST' and '/chat/completions' in request.url.path:
                body = json.loads(request.content)
                image_input = any(isinstance(m.get('content'), list) and any(
                    p.get('type') in ('image_url', 'image') for p in m['content'] if isinstance(p, dict))
                    for m in body['messages'])
                wires.append(dict(task_id=task_id, model=body['model'],
                    enable_thinking=body.get('enable_thinking'), image_input=image_input))
                write(output / 'model-wire-metadata.json', wires)
        client.event_hooks['request'].append(observe)
        return model, client

    with ExitStack() as stack:
        # The existing app imports repository into several boundary modules.
        # Replace those exact references only; import no alternate agent loop.
        for name, module in list(sys.modules.items()):
            if name.startswith('backend.') and getattr(module, 'repository', None) is production_repository:
                stack.enter_context(patch.object(module, 'repository', lambda: repo))
        for module in (snapshots, skill_versions):
            stack.enter_context(patch.object(module, 'RELEASES', output / 'releases'))
        stack.enter_context(patch.object(factory, 'make_model', observed_factory))
        stack.enter_context(patch.dict('os.environ', {'LANGSMITH_TRACING': 'false',
            'LANGCHAIN_TRACING_V2': 'false', 'OCR_RESPONSE_FORMAT': 'orderChange'}))
        capability = snapshots.snapshot()
        write(output / 'capability.json', capability)
        examples = [Example(id=uuid5(NAMESPACE_URL, dataset['version'] + c['case_id']),
            inputs=dict(case_id=c['case_id'], **c['inputs']), outputs=c['reference_outputs'],
            metadata=dict(case_id=c['case_id'], dataset_role=c['dataset_role'])) for c in cases]

        async def target(inputs):
            # Installed LangChain callbacks treat the evaluator's 'local'
            # context as truthy. Disable child tracing explicitly; aevaluate
            # still retains its root run/result locally for the code scorer.
            with tracing_context(enabled=False, parent=False):
                return await exercise(inputs, prepared, repo, capability, output)

        def evaluator(outputs, reference_outputs):
            metrics = skill_versions.function(capability, 'feedback-improvement',
                'extraction_evaluator')(outputs, reference_outputs)
            metrics.append(dict(key='execution_without_error', score=outputs.get('error') is None))
            metrics.append(dict(key='business_validation_ok', score=outputs.get('validation_ok') is True))
            metrics.append(dict(key='no_approval', score=outputs.get('approval') is None))
            return {'results': metrics}

        experiment = await aevaluate(target, data=examples, evaluators=[evaluator],
            max_concurrency=0, num_repetitions=1, upload_results=False,
            client=Client(tracing_sampling_rate=0, auto_batch_tracing=False),
            disable_evaluator_tracing=True,
            metadata=dict(dataset_version=dataset['version'], role='development_regression',
                ocr='genuine_response_replay', image_text=not args.no_image_text))
        rows = []
        async for row in experiment:
            rows.append(dict(case_id=row['example'].metadata['case_id'],
                metrics={m.key: m.score for m in row['evaluation_results']['results']},
                langsmith_run_error=row['run'].error, outputs=row['run'].outputs))
        report = dict(at=datetime.now(timezone.utc).isoformat(), engine='langsmith-local',
            dataset_version=dataset['version'], dataset_sha256=digest(DATASET),
            label_policy=dataset['label_policy'], capability_version=capability['version'],
            mode='online_model_genuine_ocr_replay', remote_ocr_requests=0,
            native_image_text=not args.no_image_text, cases=rows,
            passed=sum(bool(r['metrics'].get('extraction_exact')) for r in rows), total=len(rows))
        write(output / 'report.json', report)
        print(json.dumps(dict(report=str(output / 'report.json'),
            passed=report['passed'], total=report['total']), ensure_ascii=False), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', action='append', choices=[c['case_id'] for c in
        json.loads(DATASET.read_text(encoding='utf-8'))['cases']])
    parser.add_argument('--output')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--prepare-only', action='store_true')
    mode.add_argument('--online-model', action='store_true',
        help='Explicitly authorize a real configured model call for the selected case')
    parser.add_argument('--no-image-text', action='store_true',
        help='Development ablation: replay structured OCR without supplemental image text')
    args = parser.parse_args()
    if args.online_model and (not args.case or len(args.case) != 1):
        parser.error('--online-model requires exactly one --case; batch model evaluation is disabled')
    asyncio.run(main(args))
