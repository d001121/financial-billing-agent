<script setup lang="ts">
import { useChannelEffect, useStream } from '@langchain/vue';
import { AIMessage, HumanMessage, ToolMessage, type BaseMessage } from '@langchain/core/messages';
import { computed, nextTick, onBeforeUnmount, ref, shallowRef, watch } from 'vue';
import { Check, ChevronDown, CircleAlert, ListTodo, LoaderCircle, RefreshCw, Send, Sparkles } from '@lucide/vue';
import { api, errorMessage } from '../api/client';
import type { ConversationReply, Task, Todo } from '../types/contracts';
import AgentActivityFeed from './AgentActivityFeed.vue';
import AgentExpertActivity from './AgentExpertActivity.vue';
import AgentMessage from './AgentMessage.vue';
import { toolLabel } from '../utils/agentActivity';

const props = defineProps<{ task: Task; technical?: boolean; connectionEpoch?: number }>();
const emit = defineEmits<{ refresh: []; rejoin: []; updated: [task: Task]; locate: [chargeId: string, field: string]; edit: [chargeId: string, field: string] }>();
interface AgentState { todos?: Todo[]; messages?: unknown[]; [key: string]: unknown }
interface ReviewItem { charge_id: string; field: string; score: number; value?: unknown }
interface RequestPayload {
  name?: string; description?: string; args?: { question?: string; choices?: string[] }; kind?: string; threshold?: number;
  choices?: string[];
  tool_call_id?: string; items?: ReviewItem[];
  request_id?: string;
}
const boundThreadId = ref(props.task.thread_id || null);
const stream = useStream<AgentState>({
  apiUrl: import.meta.env.VITE_AGENT_URL || window.location.origin,
  assistantId: 'workorder-agent', threadId: boundThreadId,
});
useChannelEffect(stream, ['custom'], {
  replay: false,
  onEvent(event) {
    const data = event.params?.data;
    const payload = data?.payload ?? data;
    if (payload && typeof payload === 'object' && 'type' in payload && payload.type === 'intake_progress') emit('refresh');
  },
});
const { values, messages, toolCalls, interrupts, isLoading: streamLoading, isThreadLoading, error, subagents } = stream;
const isLoading = computed(() => streamLoading.value &&
  !['success', 'error', 'timeout', 'interrupted', 'checkpoint_unavailable'].includes(props.task.run_status || ''));
const text = ref(''), localError = ref(''), sending = ref(false), sentInterrupt = ref('');
const entityReviewOpening = ref(false), entityReviewKey = ref('');
const selected = ref('');
const requestId = ref('');
const localReplies = ref<ConversationReply[]>([]);
watch(text, () => { if (!sending.value) requestId.value = ''; });
const replies = computed(() => {
  const saved = new Map((props.task.conversation || []).map(reply => [reply.id, reply]));
  for (const reply of localReplies.value) {
    if (!saved.has(reply.id) || reply.state === 'sending' ||
        saved.get(reply.id)?.state === 'failed' && reply.state !== 'failed') saved.set(reply.id, reply);
  }
  return [...saved.values()];
});
// Hold the last SDK projections during rehydration; never rebuild the chat panel.
function hydrateNativeMessage(raw: unknown, index: number): BaseMessage | null {
  if (!raw || typeof raw !== 'object') return null;
  const item = raw as Record<string, unknown>;
  const content = item.content as never;
  const id = typeof item.id === 'string' ? item.id : `native-message-${index}`;
  const type = String(item.type || item.role || '');
  if (type === 'ai' || type === 'assistant') {
    return new AIMessage({ id, content, tool_calls: Array.isArray(item.tool_calls) ? item.tool_calls as never : [] });
  }
  if (type === 'tool') {
    return new ToolMessage({ id, content, name: typeof item.name === 'string' ? item.name : undefined,
      tool_call_id: typeof item.tool_call_id === 'string' && item.tool_call_id ? item.tool_call_id : id,
      status: item.status === 'error' ? 'error' : 'success' });
  }
  return new HumanMessage({ id, content });
}
const nativeMessages = computed<BaseMessage[]>(() => (props.task.native_messages || [])
  .map(hydrateNativeMessage).filter((message): message is BaseMessage => !!message));
const shownMessages = shallowRef<BaseMessage[]>(messages.value.length ? messages.value : nativeMessages.value), shownTools = shallowRef(toolCalls.value);
watch([messages, nativeMessages], ([value, fallback]) => {
  if (value.length) shownMessages.value = value;
  else if (fallback.length) shownMessages.value = fallback;
}, { immediate: true });
watch(toolCalls, value => { if (value.length) shownTools.value = value; }, { immediate: true });
const conversationBody = ref<HTMLElement | null>(null), following = ref(true);
function followLatest() {
  following.value = true;
  if (conversationBody.value) conversationBody.value.scrollTop = conversationBody.value.scrollHeight;
}
function onConversationScroll() {
  const body = conversationBody.value;
  if (body) following.value = body.scrollHeight - body.clientHeight - body.scrollTop < 48;
}
const pending = computed(() => {
  void values.value; void interrupts.value;
  // Native SDK can still hold a previous interrupt while the accepted run queues.
  if (['pending', 'running'].includes(props.task.run_status || '') || props.task.status === 'paused' || sending.value) return [];
  const nested = (stream.getThread()?.interrupts || []).map(i => ({id:i.interruptId, value:i.payload as RequestPayload}));
  const entries = nested.length ? nested : interrupts.value.length
    ? interrupts.value.map(i => ({id:i.id || '', value:i.value as RequestPayload}))
    : (props.task.interrupts || []).map(i => ({id:i.id, value:i.value as RequestPayload}));
  // A native before/after-agent interrupt need not emit a tool lifecycle event.
  for (const item of props.task.interrupts || []) {
    if (!entries.some(entry => entry.id === item.id)) entries.push({id:item.id,value:item.value as RequestPayload});
  }
  const authoritative = props.task.interrupts && new Set(props.task.interrupts.map(i => i.id));
  return entries.filter(entry => (!authoritative || authoritative.has(entry.id)) &&
    !replies.value.some(reply => reply.interrupt_id === entry.id && reply.state !== 'failed'));
});
const current = computed(() => pending.value.find(i => i.id === selected.value) || pending.value[0]);
const awaiting = computed(() => !!current.value && current.value.id !== sentInterrupt.value);
const companyChoices = computed(() => [...new Set(
  (current.value?.value.choices || current.value?.value.args?.choices || [])
    .filter(choice => typeof choice === 'string' && choice.trim()),
)]);
function chooseCompany(company: string) {
  text.value = `本次记账主体是${company}。`;
  document.getElementById('agent-reply')?.focus();
}
const validationIssues = computed(() => {
  const validation = props.task.validation as { issues?: { code?: string }[] } | undefined;
  return validation?.issues || [];
});
// New runs open this review in the graph. Existing gap tasks open the same
// native review once when viewed, so there is no separate "add entity" button.
const needsEntityReview = computed(() =>
  !props.technical &&
  props.task.status === 'completed_with_gaps' &&
  !!props.task.thread_id &&
  !props.task.accounting_entity &&
  !['pending', 'running'].includes(props.task.run_status || '') &&
  !pending.value.length &&
  validationIssues.value.some(issue => issue.code === 'POSTING_UNRESOLVED'),
);
async function openEntityReview() {
  const key = `${props.task.id}:${props.task.revision}`;
  if (!needsEntityReview.value || entityReviewOpening.value || entityReviewKey.value === key) return;
  entityReviewKey.value = key;
  entityReviewOpening.value = true;
  localError.value = '';
  try {
    const updated = await api.reviewConversation(props.task.id, {
      expected_revision: props.task.revision,
      action: 'entity',
    });
    emit('updated', updated);
    emit('refresh');
    emit('rejoin');
  } catch (e) {
    localError.value = errorMessage(e);
  } finally {
    entityReviewOpening.value = false;
  }
}
watch([() => props.task.id, () => props.task.revision, () => props.task.status,
  () => props.task.accounting_entity, () => pending.value.length],
  () => { if (needsEntityReview.value) void openEntityReview(); }, { immediate: true });
const todos = computed(() => Array.isArray(values.value?.todos) ? values.value.todos : props.task.todos || []);
const completed = computed(() => todos.value.filter(t => t.status === 'completed').length);
const unfinished = computed(() => todos.value.filter(t => t.status !== 'completed'));
const running = computed(() => isLoading.value || ['pending', 'running'].includes(props.task.run_status || ''));
const sendBlocked = computed(() => sending.value || running.value || isThreadLoading.value ||
  !props.task.thread_id || [props.task.control, props.task.status].some(value => ['paused', 'pausing', 'cancelled'].includes(value || '')));
const taskReminder = computed(() => {
  if (props.task.status === 'paused' || props.task.control === 'paused') return '任务已暂停，请在上方恢复后继续发送。';
  if (props.task.control === 'cancelled') return '任务已取消，当前消息可保留为草稿。';
  if (running.value) return '助手正在处理，您可先写好下一条消息。';
  if (['incomplete', 'error', 'budget_exhausted', 'recovery_required'].includes(props.task.status)) return props.task.summary || '任务尚未完成，请关注处理状态。';
  return '';
});
async function focusPending(id: string) {
  selected.value = id;
  await nextTick();
  followLatest();
  document.getElementById('agent-reply')?.focus();
}
const experts = computed(() => Array.from(subagents.value.values()));
const activeTool = computed(() => toolCalls.value.filter(t => t.status === 'running').at(-1));
const status = computed(() => {
  if (entityReviewOpening.value) return '正在打开主体核对';
  if (awaiting.value) return '等待您的回复';
  if (sending.value) return '正在发送回复';
  if (sentInterrupt.value && !isLoading.value && props.task.run_status === 'pending') return '回复已提交，正在继续';
  if (isThreadLoading.value) return '正在同步会话';
  if (props.task.status === 'incomplete' && props.task.run_status === 'success') return '处理未完成';
  if (isLoading.value) return activeTool.value ? toolLabel(activeTool.value.name) : '正在回复';
  if (['pending','running'].includes(props.task.run_status || '')) return '正在继续处理';
  if (props.task.status === 'paused') return '已暂停';
  if (['error', 'timeout'].includes(props.task.run_status || '')) return '本轮已停止';
  return '可以继续提问或修改字段';
});
const fieldLabels: Record<string,string> = {amount:'金额',currency:'币种',reference_no:'单据编号',charge_item:'费用名称',posting_type:'AR/AP',payment_term:'付款方式'};
function prompt(value: RequestPayload): string {
  if (value.name === 'ask_user') return value.args?.question || value.description || '请补充任务所需信息。';
  if (value.kind === 'confidence_review') return '以下字段需要您核对。您可以直接回复正确的内容，也可以说明确认无误或需要暂缓。';
  return value.description || '这一步需要您的意见，请用一句话说明如何继续。';
}
const connectionError = computed(() => error.value ? '会话连接暂时中断，已有记录和账单结果已保留。' : '');
watch(() => current.value?.id, (id, previous) => {
  if (id && id !== previous) {
    if (selected.value !== id) requestId.value = '';
    selected.value = id;
    void nextTick(() => {
      followLatest();
      document.getElementById('agent-reply')?.focus();
    });
  }
}, { immediate: true });
watch(() => [messages.value.at(-1)?.text, toolCalls.value.map(t => `${t.id}:${t.status}`).join('|'),
  replies.value.length], () => {
  if (following.value) followLatest();
}, { flush: 'post' });
watch(isLoading, (now, before) => { if (before && !now) emit('refresh'); });
// A thread event stream that reconnects after a run finished never delivers
// the terminal event, so streamLoading can stay true forever.  Reconcile the
// task detail while loading; run_status then becomes terminal and clears it.
let reconcileTimer: ReturnType<typeof setInterval> | undefined;
watch(isLoading, (now) => {
  if (reconcileTimer) { clearInterval(reconcileTimer); reconcileTimer = undefined; }
  if (now) reconcileTimer = setInterval(() => { if (isLoading.value) emit('refresh'); }, 10000);
}, { immediate: true });
onBeforeUnmount(() => { if (reconcileTimer) clearInterval(reconcileTimer); });
let reconnecting = false;
async function rejoinStream() {
  if (reconnecting) return;
  reconnecting = true;
  try {
    await stream.disconnect();
    // Reactive threadId is the public Vue SDK hydration entry point.
    boundThreadId.value = null;
    await nextTick();
    boundThreadId.value = props.task.thread_id || null;
    await nextTick();
    await stream.hydrationPromise.value;
  } finally { reconnecting = false; }
}
watch(() => props.connectionEpoch, () => { void rejoinStream(); });
// A terminal run state with a still-loading SDK means the completion event was
// missed during reconnect. Rebuild the subscription from the checkpoint.
watch(() => props.task.run_status, (run) => {
  if (['success', 'error', 'timeout', 'interrupted', 'checkpoint_unavailable'].includes(run || '') &&
      streamLoading.value && !sending.value) void rejoinStream();
});
watch([() => props.task.run_id, () => props.task.run_status,
  () => props.task.usage?.model_calls, () => props.task.usage?.tool_calls], () => {
  if (!error.value && !isLoading.value && !isThreadLoading.value &&
      ['running','queued','processing'].includes(props.task.status) &&
      !['success','error','timeout','interrupted'].includes(props.task.run_status || '')) emit('rejoin');
});
async function send() {
  const entry = current.value;
  if (!text.value.trim() || sendBlocked.value) return;
  localError.value = ''; sending.value = true;
  requestId.value ||= crypto.randomUUID();
  const reply: ConversationReply = { id:requestId.value, text:text.value.trim(), question:entry ? prompt(entry.value) : '',
    interrupt_id:entry?.id || '', kind:entry ? undefined : 'chat', tool_call_id:entry?.value.tool_call_id, revision:props.task.revision,
    anchor_message_id:entry?.value.request_id ? 'review-question-' + entry.value.request_id : undefined,
    state:'sending', at:new Date().toISOString() };
  localReplies.value = [...localReplies.value.filter(item => item.id !== reply.id), reply];
  await nextTick(); followLatest();
  try {
    const result = await api.reply(props.task.id, {text:reply.text, expected_revision:props.task.revision,
      interrupt_id:entry?.id, conversational:true, reply_id:requestId.value});
    sentInterrupt.value = entry?.id || '';
    localReplies.value = localReplies.value.map(item => item.id === reply.id ? {...item,state:'running'} : item);
    text.value = ''; requestId.value = '';
    emit('updated', result); emit('refresh'); emit('rejoin');
  } catch (e) {
    localReplies.value = localReplies.value.map(item => item.id === reply.id ? {...item,state:'failed'} : item);
    localError.value = errorMessage(e);
  }
  finally { sending.value = false; }
}
function reconnect() { localError.value = ''; emit('refresh'); emit('rejoin'); }
onBeforeUnmount(() => { void stream.disconnect(); });
</script>

<template>
  <section class="card agent-panel" aria-label="与账单助手的会话">
    <div class="card-head">
      <div class="flex"><span class="agent-symbol"><Sparkles :size="16" /></span><h3>账单助手</h3><span class="conversation-label">会话</span></div>
      <span class="conversation-status" role="status"><i v-if="isLoading || sending" class="activity-pulse" />{{ status }}</span>
    </div>
    <div v-if="pending.length || unfinished.length || taskReminder" class="conversation-attention" aria-label="未完成事项提醒" aria-live="polite">
      <details v-if="pending.length || unfinished.length">
        <summary><ListTodo :size="14" /><strong>待办事项</strong><span v-if="pending.length" class="pending-count">{{ pending.length }} 项待回复</span><span v-if="unfinished.length">{{ unfinished.length }} 项计划未完成</span><ChevronDown :size="13" /></summary>
        <ul>
          <li v-for="entry in pending" :key="entry.id"><button type="button" class="ghost" @click="focusPending(entry.id)"><span>待回复 · {{ prompt(entry.value) }}</span><span>去回复</span></button></li>
          <li v-for="(todo,i) in unfinished" :key="'todo-'+i"><span>{{ todo.status === 'in_progress' ? '进行中' : '未完成' }} · {{ todo.content }}</span></li>
        </ul>
      </details>
      <p v-if="taskReminder" role="status"><CircleAlert :size="13" />{{ taskReminder }}</p>
    </div>
    <div class="conversation-scroll">
    <div ref="conversationBody" class="conversation-body" tabindex="0" aria-label="账单会话消息，可滚动查看" @scroll.passive="onConversationScroll">
    <div v-if="todos.length" class="conversation-plan">
      <details><summary><ListTodo :size="14" /><span>处理计划</span><small>{{ completed }} / {{ todos.length }}</small><ChevronDown :size="13" /></summary>
        <ol><li v-for="(todo,i) in todos" :key="i"><Check v-if="todo.status === 'completed'" :size="13" /><LoaderCircle v-else-if="todo.status === 'in_progress' && isLoading" :size="13" class="loading-icon" /><span v-else class="plan-index">{{ i+1 }}</span>{{ todo.content }}</li></ol>
      </details>
    </div>
      <AgentActivityFeed :messages="shownMessages" :tools="shownTools" :replies="replies" :active="isLoading" :waiting="awaiting" embedded />
      <details v-if="experts.length" class="expert-records"><summary>专家协作记录 <span>{{ experts.length }}</span><ChevronDown :size="13" /></summary>
        <AgentExpertActivity v-for="expert in experts" :key="expert.id" :stream="stream" :expert="expert" :active="isLoading" :waiting="awaiting" />
      </details>
      <div v-if="isLoading && !awaiting" class="working-note"><LoaderCircle :size="14" class="loading-icon" />{{ activeTool ? toolLabel(activeTool.name) : '账单助手正在处理…' }}</div>
      <div v-if="awaiting && current" class="assistant-question" :key="current.id">
        <span class="question-author"><Sparkles :size="14" />账单助手 <small>需要您的回复</small></span>
        <AgentMessage v-if="current.value.name !== 'ask_user' || !toolCalls.some(t => t.id === current?.value.tool_call_id)" :text="prompt(current.value)" />
        <div v-if="current.value.kind === 'confidence_review'" class="review-facts">
          <div v-for="(item,i) in current.value.items" :key="i"><span>{{ fieldLabels[item.field] || item.field }}</span><strong>{{ item.value ?? '待明确' }}</strong><small>{{ item.score }} 分</small><button class="ghost" @click="emit('locate', item.charge_id, item.field)">查看原文</button></div>
        </div>
        <div v-if="pending.length > 1" class="question-choices" aria-label="选择要回复的问题"><button v-for="(entry,i) in pending" :key="entry.id" :class="{active:entry.id === current.id}" @click="selected = entry.id">问题 {{ i+1 }}</button></div>
      </div>
    </div>
    <button v-if="!following" class="latest-message" @click="followLatest"><ChevronDown :size="13" />回到最新消息</button>
    </div>
    <div class="conversation-footer">
    <div v-if="connectionError" class="connection-notice" role="alert"><CircleAlert :size="15" /><span>{{ connectionError }}</span><button class="ghost" @click="reconnect"><RefreshCw :size="13" />重新连接</button></div>
    <div v-if="localError" class="notice error" role="alert">{{ localError }}</div>
    <form class="conversation-composer" @submit.prevent="send">
      <div v-if="companyChoices.length" class="company-choices" aria-label="选择本次记账公司">
        <span>材料中的公司 · 点击填入回复，也可直接填写其他公司</span>
        <div><button v-for="company in companyChoices" :key="company" type="button" :disabled="sending" @click="chooseCompany(company)">{{ company }}</button></div>
      </div>
      <label class="sr-only" for="agent-reply">回复账单助手</label>
      <textarea id="agent-reply" v-model="text" rows="2" maxlength="12000" :disabled="sending" placeholder="随时提问或说明修改，例如：把第一笔费用金额改为 65 美元。" @keydown.ctrl.enter.prevent="send" @keydown.meta.enter.prevent="send" />
      <div class="composer-actions"><span>{{ running ? '正在处理，可先输入草稿' : awaiting ? '有待办待回复，也可以继续提问' : '提问、补充或修改字段' }} · Ctrl / ⌘ + Enter</span><button class="primary" type="submit" :disabled="!text.trim() || sendBlocked"><LoaderCircle v-if="sending" :size="15" class="loading-icon" /><Send v-else :size="15" />{{ sending ? '发送中' : '发送' }}</button></div>
    </form>
    <details v-if="technical" class="native-details"><summary>原生中断详情</summary><pre>{{ JSON.stringify(pending, null, 2) }}</pre></details>
    </div>
  </section>
</template>

<style scoped>
.conversation-attention { flex:0 0 auto; max-height:112px; overflow:auto; background:#f6f8f3; border-bottom:1px solid var(--line); padding:8px 20px; color:#626b52; font-size:11px; }
.conversation-attention summary { display:flex; align-items:center; gap:7px; cursor:pointer; list-style:none; }
.conversation-attention summary::-webkit-details-marker { display:none; }
.conversation-attention summary > svg:last-child { margin-left:auto; }
.conversation-attention strong { font-weight:600; color:var(--ink); }
.conversation-attention .pending-count { color:#94651e; background:#fbefd9; padding:2px 6px; border-radius:4px; }
.conversation-attention ul { margin:8px 0 0; padding:0; list-style:none; }
.conversation-attention li + li { margin-top:7px; }
.conversation-attention li > button { display:flex; justify-content:space-between; gap:12px; width:100%; padding:0; font-size:11px; text-align:left; }
.conversation-attention li > button span:first-child { min-width:0; overflow:hidden; white-space:nowrap; text-overflow:ellipsis; }
.conversation-attention li > button span:last-child { flex-shrink:0; color:var(--primary); }
.conversation-attention p { display:flex; gap:6px; align-items:center; margin:0; }
.conversation-attention details + p { margin-top:6px; }
.company-choices { padding:12px 14px 0; }
.company-choices > span { display:block; color:var(--muted); font-size:11px; margin-bottom:8px; }
.company-choices > div { display:flex; flex-wrap:wrap; gap:6px; max-height:115px; overflow:auto; }
.company-choices button { color:var(--primary); background:var(--surface); border:1px solid var(--line); border-radius:8px; padding:7px 10px; font-size:12px; text-align:left; white-space:normal; overflow-wrap:anywhere; }
.agent-panel { overflow:hidden; min-width:0; height:min(480px, calc(100dvh - 180px)); min-height:360px; display:flex; flex-direction:column; position:relative; }
.agent-panel > .card-head { flex-shrink:0; }
.card-head { padding:8px 16px; border-bottom:1px solid var(--line); gap:8px; flex-wrap:wrap; }
.card-head h3 { margin:0; font-size:13px; }
.agent-symbol { display:grid; place-items:center; width:24px; height:24px; border-radius:7px; color:var(--primary); background:#edf3ef; }
.conversation-label { font-size:11px; color:var(--muted); padding-left:10px; border-left:1px solid var(--line); }
.conversation-status { color:var(--muted); font-size:11px; display:flex; align-items:center; gap:7px; }
.activity-pulse { width:6px; height:6px; border-radius:50%; background:var(--primary); animation:pulse 1.5s infinite; }
.conversation-scroll { flex:1 1 0; min-height:0; position:relative; }
.conversation-body { padding:20px 24px; height:100%; overflow:auto; overscroll-behavior:contain; overflow-anchor:none; scrollbar-gutter:stable; }
.conversation-body:focus-visible { outline:2px solid var(--primary); outline-offset:-3px; }
.conversation-plan { padding:0 0 20px; }
.conversation-plan summary,.expert-records summary { cursor:pointer; display:flex; align-items:center; gap:8px; color:var(--muted); font-size:12px; list-style:none; }
.conversation-plan small { margin-left:auto; }
.conversation-plan ol { list-style:none; padding:8px 0; margin:0; }
.conversation-plan li { display:flex; gap:9px; align-items:start; padding:6px 0; font-size:12px; }
.plan-index { width:13px; text-align:center; color:var(--muted); }
.expert-records { border-top:1px solid var(--line); margin-top:16px; padding-top:14px; }
.working-note { margin:16px 0 0 33px; display:flex; align-items:center; gap:8px; font-size:12px; color:var(--muted); }
.assistant-question { padding:18px 0 0 33px; margin-top:16px; border-top:1px solid var(--line); }
.question-author { display:flex; align-items:center; gap:7px; color:var(--primary); font-size:12px; margin-bottom:10px; }
.question-author small { margin-left:auto; font-size:11px; color:var(--muted); }
.review-facts { margin-top:12px; }
.review-facts > div { display:flex; align-items:center; gap:10px; flex-wrap:wrap; padding:8px 0; font-size:12px; border-bottom:1px solid var(--line); }
.review-facts small { color:var(--muted); }
.review-facts button { margin-left:auto; }
.question-choices { display:flex; gap:6px; margin-top:12px; }
.question-choices .active { border-color:var(--primary); color:var(--primary); }
.conversation-footer { flex:0 0 auto; max-height:60%; overflow:auto; background:var(--surface); }
.conversation-footer:has(.conversation-composer) { border-top:1px solid var(--line); padding-top:8px; }
.latest-message { position:absolute; right:30px; bottom:12px; display:flex; align-items:center; gap:5px; padding:7px 12px; color:var(--primary); background:var(--surface); border:1px solid var(--line); border-radius:20px; box-shadow:0 2px 8px #183a2810; font-size:11px; }
.conversation-composer { margin:0 16px 10px; border:1px solid #c9d9ce; border-radius:10px; background:var(--surface); box-shadow:0 2px 5px #183a2810; }
.conversation-composer:focus-within { border-color:var(--primary); box-shadow:0 0 0 2px #3a715615; }
.conversation-composer textarea { display:block; width:100%; resize:none; height:44px; min-height:44px; max-height:44px; border:0; box-shadow:none; background:transparent; padding:7px 12px 2px; font-family:inherit; font-size:13px; line-height:1.6; border-radius:10px; outline:none; }
.composer-actions { padding:2px 8px 6px 12px; display:flex; align-items:center; gap:8px; justify-content:space-between; }
.composer-actions > span { color:var(--muted); font-size:10px; }
.composer-actions button { flex-shrink:0; padding:5px 10px; font-size:12px; }
.conversation-end { margin:0; padding:12px 24px; color:var(--muted); font-size:11px; background:#f8faf8; border-top:1px solid var(--line); }
.connection-notice { display:flex; align-items:center; gap:8px; margin:0 24px 16px; padding:10px 12px; border:1px solid var(--line); border-radius:8px; color:var(--muted); font-size:12px; }
.connection-notice > span { flex:1; }
.native-details { padding:16px 24px; font-size:12px; }
.native-details pre { max-height:240px; overflow:auto; white-space:pre-wrap; overflow-wrap:anywhere; }
.sr-only { position:absolute; width:1px; height:1px; margin:-1px; overflow:hidden; clip:rect(0,0,0,0); }
@keyframes pulse {50% {opacity:.3}}
@media(max-width:600px) { .agent-panel {height:min(440px, calc(100dvh - 120px));} .card-head {padding:8px 12px;} .conversation-body {padding:16px;} .conversation-composer {margin:0 12px 10px;} .assistant-question {padding-left:0;} .composer-actions {align-items:flex-end;} .composer-actions > span {max-width:145px;} .conversation-status {max-width:100%;} .connection-notice {margin:0 16px 16px; flex-wrap:wrap;} .latest-message {right:20px;} }
@media(prefers-reduced-motion:reduce) { .activity-pulse {animation:none;} }
</style>
