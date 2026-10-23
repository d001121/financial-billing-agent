import assert from 'node:assert/strict';
import { test } from 'node:test';
import { billAttention, taskCategory, taskIsProcessing } from '../src/utils/taskPresentation.ts';

const bill = (overrides = {}) => ({
  id: 'offline-bill', title: '账单', accounting_entity: null,
  revision: 2, status: 'processing', created_at: '2026-10-23', ...overrides,
});

test('approved and completed bills ignore an old pending run indicator', () => {
  for (const status of ['approved', 'completed', 'succeeded', 'completed_with_gaps']) {
    for (const run_status of ['pending', 'running']) {
      const task = bill({ status, run_status, thread_status: 'idle' });
      assert.equal(taskIsProcessing(task), false, `${status}/${run_status}`);
      assert.equal(taskCategory(task), 'completed');
      assert.doesNotMatch(billAttention(task), /正在处理材料/);
    }
  }
});

test('current revision approval wins over an older processing status', () => {
  const task = bill({ run_status: 'pending', approval: { decision: 'approve', binding: { revision: 2 } } });
  assert.equal(taskIsProcessing(task), false);
  assert.match(billAttention(task), /已批准/);
  assert.match(billAttention(bill({ status: 'approved', run_status: 'pending' })), /已批准/);
  assert.equal(taskIsProcessing(bill({ approval: { decision: 'approve', binding: { revision: 1 } } })), true);
});

test('real material processing remains visible', () => {
  for (const status of ['pending', 'queued', 'starting', 'running', 'processing', 'pausing']) {
    const task = bill({ status, run_status: 'pending' });
    assert.equal(taskIsProcessing(task), true, status);
    assert.equal(billAttention(task), '正在处理材料，完成后可核对账单');
  }
});

test('questions, review, pause and failure are not overridden by an old run indicator', () => {
  for (const status of ['awaiting_input', 'awaiting_review', 'review_deferred', 'paused', 'error', 'incomplete', 'recovery_required', 'budget_exhausted']) {
    const task = bill({ status, run_status: 'pending', pending_questions: ['请确认币种'] });
    assert.equal(taskIsProcessing(task), false, status);
    assert.doesNotMatch(billAttention(task), /正在处理材料/);
  }
  assert.equal(billAttention(bill({ status: 'awaiting_input', pending_questions: ['请确认币种'] })), '请确认币种');
});

test('an ordinary chat run does not label a completed bill as material processing', () => {
  const task = bill({ status: 'completed', run_status: 'running', thread_status: 'busy' });
  assert.equal(taskIsProcessing(task), false);
  assert.match(billAttention(task), /已完成核验/);
});
