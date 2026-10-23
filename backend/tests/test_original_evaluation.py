"""One local LangSmith code-scoring probe; no OCR or model network calls."""
from unittest.mock import patch
from uuid import uuid4

import pytest
from langsmith import Client, aevaluate, tracing_context
from langsmith.schemas import Example


@pytest.mark.asyncio
async def test_native_local_evaluation_keeps_outputs_without_langsmith_requests():
    async def target(inputs):
        with tracing_context(enabled=False, parent=False):
            return {'amount': inputs['amount']}

    def evaluator(outputs, reference_outputs):
        return outputs == reference_outputs

    # Installed 0.14.11 async forwarding enables root tracing even with
    # upload_results=False. The native sampling option suppresses that upload.
    client = Client(tracing_sampling_rate=0, auto_batch_tracing=False)
    with patch.object(client.session, 'request', side_effect=AssertionError('Unexpected upload')):
        result = await aevaluate(target, data=[Example(id=uuid4(), inputs={'amount':5},
            outputs={'amount':5})], evaluators=[evaluator], client=client,
            upload_results=False, disable_evaluator_tracing=True, max_concurrency=0)
        rows = [row async for row in result]
    assert len(rows)==1 and rows[0]['run'].outputs=={'amount':5}
    assert rows[0]['evaluation_results']['results'][0].score is True
