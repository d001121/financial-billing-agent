import assert from 'node:assert/strict';
import { test } from 'node:test';
import { AIMessage, HumanMessage, ToolMessage } from '@langchain/core/messages';
import { activityEntries, mergeMessageProjections } from '../src/utils/agentActivity.ts';

const ai = (id, text) => new AIMessage({ id, content: text });
const chat = (id, extra = {}) => ({
  id, text: '你好', kind: 'chat', question: '', interrupt_id: '', revision: 2,
  state: 'running', at: '2026-10-24T02:58:46+08:00', ...extra,
});
const texts = (messages, replies) => activityEntries(messages, [], replies).map(entry => entry.text);

test('an optimistic chat stays before the streamed answer until its native human message arrives', () => {
  const reply = chat('hello', { anchor_message_id: 'old-answer' });
  const streaming = [ai('old-answer', '之前的回复'), ai('new-answer', '你好！')];
  assert.deepEqual(texts(streaming, [reply]), ['之前的回复', '你好', '你好！']);
  const hydrated = [streaming[0], new HumanMessage({ id: 'chat-user-hello', content: '你好' }), streaming[1]];
  assert.deepEqual(texts(hydrated, [reply]), ['之前的回复', '你好', '你好！']);
});

test('a completed chat without a native human marker is placed before its recorded answer', () => {
  const reply = chat('hello', { state: 'completed', response_message_id: 'new-answer' });
  assert.deepEqual(texts([ai('old-answer', '之前的回复'), ai('new-answer', '你好！')], [reply]),
    ['之前的回复', '你好', '你好！']);
});

test('native human order takes priority over a shared old anchor across multiple chat turns', () => {
  const replies = [chat('one', { anchor_message_id: 'old' }),
    chat('two', { text: '第二次提问', anchor_message_id: 'old' })];
  const messages = [ai('old', '历史'), new HumanMessage({ id: 'chat-user-one', content: '你好' }),
    ai('one-answer', '第一次答复'), new HumanMessage({ id: 'chat-user-two', content: '第二次提问' }),
    ai('two-answer', '第二次答复')];
  assert.deepEqual(texts(messages, replies), ['历史', '你好', '第一次答复', '第二次提问', '第二次答复']);
});

test('a local reply can anchor after a tool result before the assistant starts streaming', () => {
  const messages = [ai('old', '历史'), new ToolMessage({ id: 'tool-result', content: 'done', tool_call_id: 'tool' }),
    ai('answer', '新回复')];
  assert.deepEqual(texts(messages, [chat('hello', { anchor_message_id: 'tool-result' })]),
    ['历史', '你好', '新回复']);
});

test('a nonempty stale stream cannot hide the latest checkpoint answer (bill12)', () => {
  const old = ai('old', '之前的回复');
  const user = new HumanMessage({ id: 'chat-user-hello', content: '你好' });
  const answer = ai('answer', '你好！');
  const checkpoint = [old, user, answer];
  const merged = mergeMessageProjections([old], checkpoint, false);
  assert.deepEqual(merged.map(message => message.id), ['old', 'chat-user-hello', 'answer']);
  assert.deepEqual(texts(merged, [chat('hello')]), ['之前的回复', '你好', '你好！']);
});

test('live deltas append after checkpoint history and update the same ID in place', () => {
  const old = ai('old', '历史');
  const user = new HumanMessage({ id: 'chat-user-hello', content: '你好' });
  const checkpoint = [old, user];
  for (const content of ['你', '你好！']) {
    const merged = mergeMessageProjections([old, ai('answer', content)], checkpoint, true);
    assert.deepEqual(merged.map(message => message.id), ['old', 'chat-user-hello', 'answer']);
    assert.deepEqual(texts(merged, [chat('hello')]), ['历史', '你好', content]);
  }
  const partial = [...checkpoint, ai('answer', '你')];
  const merged = mergeMessageProjections([...checkpoint, ai('answer', '你好！')], partial, true);
  assert.equal(merged.length, 3);
  assert.equal(merged.at(-1).text, '你好！');
});

test('a delayed stream cannot shorten a saved final answer or regress persisted order', () => {
  const old = ai('old', '历史');
  const checkpoint = [old, ai('answer', '你好，完整回复！'), ai('receipt', '已完成')];
  const merged = mergeMessageProjections([old, ai('answer', '你好')], checkpoint, true);
  assert.deepEqual(merged.map(message => message.text), ['历史', '你好，完整回复！', '已完成']);
  const equalTail = mergeMessageProjections([ai('answer', '你好')], [checkpoint[1]], true);
  assert.equal(equalTail[0].text, '你好，完整回复！');
});

test('bounded checkpoint history keeps older SDK messages before the shared anchor', () => {
  const checkpoint = [ai('two', '旧第二条'), ai('three', '最新第三条')];
  const live = [ai('one', '最早第一条'), checkpoint[0]];
  assert.deepEqual(mergeMessageProjections(live, checkpoint, false).map(message => message.id),
    ['one', 'two', 'three']);
  assert.deepEqual(mergeMessageProjections([], checkpoint, false), checkpoint);
  assert.deepEqual(mergeMessageProjections(live, [], true), live);
});

test('human review replies remain immediately after their native question without duplicates', () => {
  const reply = chat('review', { kind: 'conversation_review', text: '本次主体是A',
    anchor_message_id: 'review-question-id' });
  const messages = [ai('review-question-id', '请确认主体'), ai('receipt', '已修改')];
  assert.deepEqual(texts(messages, [reply]), ['请确认主体', '本次主体是A', '已修改']);
  const toolReply = chat('tool-reply', {kind: 'ask_user', question: '请确认', tool_call_id: 'ask'});
  const asked = new AIMessage({ id: 'asked', content: '',
    tool_calls: [{ id: 'ask', name: 'ask_user', args: { question: '请确认' } }] });
  const entries = activityEntries([asked], [{ id: 'ask', name: 'ask_user', status: 'finished', args: {} }], [toolReply]);
  assert.equal(entries.filter(entry => entry.role === 'user').length, 1);
  assert.equal(entries.filter(entry => entry.text === '请确认').length, 1);
});
