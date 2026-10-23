<script setup lang="ts">
import { computed, ref, watch } from "vue";
import type { BaseMessage } from "@langchain/core/messages";
import type { AssembledToolCall } from "@langchain/vue";
import { Check, ChevronDown, CircleAlert, LoaderCircle, MessageSquare, Terminal } from "@lucide/vue";
import { activityEntries, commandFor, displayValue, toolContext, toolLabel } from "../utils/agentActivity";
import type { ConversationReply } from '../types/contracts';
import AgentMessage from './AgentMessage.vue';

const props = defineProps<{ messages: BaseMessage[]; tools: AssembledToolCall[]; replies?: ConversationReply[]; active: boolean; waiting?: boolean; embedded?: boolean }>();
const expandedHistory = ref(false);
const expandedTools = ref(new Set<string>());
const transcript = ref<HTMLElement | null>(null);
const following = ref(true);
const entries = computed(() => activityEntries(props.messages, props.tools, props.replies));
const visible = computed(() => expandedHistory.value ? entries.value : entries.value.slice(-12));
const hiddenCount = computed(() => Math.max(0, entries.value.length - 12));
function followLatest() {
  following.value = true;
  if (transcript.value) transcript.value.scrollTop = transcript.value.scrollHeight;
}
function onScroll() {
  const element = transcript.value;
  if (element) following.value = element.scrollHeight - element.clientHeight - element.scrollTop < 48;
}
function toggleTool(id: string, event: Event) {
  if ((event.target as HTMLDetailsElement).open) expandedTools.value.add(id);
  else expandedTools.value.delete(id);
}
watch(() => [props.messages.at(-1)?.text, props.tools.map(tool => `${tool.id}:${tool.status}`).join('|'), props.replies?.length], () => {
  if (!props.embedded && following.value) followLatest();
}, { flush: 'post' });
function status(tool: AssembledToolCall): string {
  if (tool.status === "finished") return "已返回";
  if (tool.status === "error") return "调用失败";
  return props.active ? "执行中" : props.waiting ? "等待补充" : "未收到返回";
}
</script>

<template>
  <div class="activity-feed" aria-label="智能体会话记录" role="log" aria-live="polite" aria-relevant="additions text">
    <div ref="transcript" class="activity-transcript" :class="{ embedded }" @scroll.passive="onScroll">
    <button v-if="hiddenCount" class="history-toggle" :aria-expanded="expandedHistory" @click="expandedHistory = !expandedHistory">
      <ChevronDown :size="13" :class="{ rotated: expandedHistory }" />
      {{ expandedHistory ? '收起较早记录' : `查看之前 ${hiddenCount} 条记录` }}
    </button>
    <ol class="activity-list">
      <li v-for="entry in visible" :key="entry.id" :data-activity-id="entry.id" :class="['activity-entry', entry.kind, entry.kind === 'message' ? entry.role : '']">
        <span class="activity-marker">
          <MessageSquare v-if="entry.kind === 'message'" :size="14" />
          <LoaderCircle v-else-if="entry.tool.status === 'running' && active" :size="14" class="loading-icon" />
          <CircleAlert v-else-if="entry.tool.status === 'error'" :size="14" class="failed" />
          <Check v-else-if="entry.tool.status === 'finished'" :size="14" />
          <Terminal v-else :size="14" />
        </span>
        <div v-if="entry.kind === 'message'" class="message-content">
          <div class="message-author">{{ entry.role === 'user' ? '您' : '账单助手' }}</div>
          <template v-if="entry.role === 'user'">
            <p class="user-text">{{ entry.text }}</p>
            <small v-if="entry.delivery === 'sending'" class="message-delivery" role="status">正在发送…</small>
            <small v-else-if="entry.delivery === 'failed'" class="message-delivery failed" role="status">未发送成功，请在输入框重试</small>
          </template>
          <details v-else-if="entry.text.length > 1600" class="long-message">
            <summary>{{ entry.text.slice(0, 180) }}… <span>展开完整回复</span><ChevronDown :size="13" /></summary>
            <AgentMessage :text="entry.text" />
          </details>
          <AgentMessage v-else :text="entry.text" />
        </div>
        <details v-else class="activity-tool" @toggle="toggleTool(entry.tool.id, $event)">
          <summary>
            <strong>{{ toolLabel(entry.tool.name) }}</strong>
            <span v-if="toolContext(entry.tool)" class="tool-context" :title="toolContext(entry.tool)">{{ toolContext(entry.tool) }}</span>
            <span :class="['call-status', entry.tool.status]">{{ status(entry.tool) }}</span>
            <ChevronDown :size="13" class="disclosure-chevron" />
          </summary>
          <div v-if="expandedTools.has(entry.tool.id)" class="call-detail">
            <div class="native-name">工具 <code>{{ entry.tool.name }}</code></div>
            <template v-if="commandFor(entry.tool)">
              <h4>执行命令</h4><pre class="command-output">{{ commandFor(entry.tool) }}</pre>
            </template>
            <details class="call-arguments"><summary>调用参数<ChevronDown :size="12" /></summary>
              <pre>{{ displayValue(entry.tool.args) }}</pre>
            </details>
            <h4>{{ entry.tool.status === 'error' ? '错误信息' : '返回结果' }}</h4>
            <pre :class="{ 'failed-output': entry.tool.status === 'error' }">{{ entry.tool.error || (entry.tool.output === null ? (entry.tool.status === 'finished' ? '工具已返回，未提供可展示内容。' : status(entry.tool)) : displayValue(entry.tool.output)) }}</pre>
          </div>
        </details>
      </li>
    </ol>
    <p v-if="!entries.length" class="activity-empty">{{ active ? '已连接，等待智能体返回消息或工具记录…' : '当前检查点没有可展示的执行记录。' }}</p>
    </div>
    <button v-if="!embedded && !following && active" class="latest-toggle" @click="followLatest"><ChevronDown :size="13" />查看最新进度</button>
  </div>
</template>

<style scoped>
.activity-feed { min-width:0; }
.activity-transcript { max-height:660px; overflow:auto; padding:4px 8px 4px 0; overflow-anchor:none; }
.activity-transcript.embedded { max-height:none; overflow:visible; }
.latest-toggle { display:flex; margin:12px auto 0; padding:5px 10px; font-size:11px; color:var(--primary); border:1px solid var(--line); background:var(--surface); border-radius:20px; }
.activity-list { list-style:none; padding:0; margin:0; }
.activity-entry { position:relative; display:flex; gap:13px; padding:0 0 16px; min-width:0; }
.activity-entry:last-child { padding-bottom:0; }
.activity-entry:not(:last-child)::before { content:""; position:absolute; width:1px; left:9px; top:25px; bottom:4px; background:var(--line); }
.activity-marker { width:20px; height:24px; display:grid; place-items:center; flex-shrink:0; color:var(--primary); }
.message-content,.activity-tool { flex:1; min-width:0; }
.message-author { font-size:11px; color:var(--muted); margin:0 0 7px; }
.activity-entry.user { padding-left:32px; }
.activity-entry.user .activity-marker { display:none; }
.activity-entry.user .message-content { background:#edf3ef; border:1px solid #e0e9e3; border-radius:12px; padding:12px 16px; margin:4px 0; }
.activity-entry.user::before { display:none; }
.activity-entry.user .message-author { color:var(--primary); }
.activity-entry .user-text { white-space:pre-wrap; margin:0; }
.message-delivery { display:block; margin-top:6px; font-size:11px; color:var(--muted); }
.message-content p { margin:1px 0 0; font-size:13px; color:var(--ink); line-height:1.9; white-space:pre-wrap; overflow-wrap:anywhere; }
summary { list-style:none; cursor:pointer; }
summary::-webkit-details-marker { display:none; }
.activity-tool > summary { display:flex; align-items:center; gap:10px; min-height:26px; font-size:12px; color:var(--ink); border-radius:5px; }
.activity-tool > summary:hover { color:var(--primary); }
.activity-tool strong { font-weight:500; flex-shrink:0; }
.tool-context { font-family:Consolas,monospace; font-size:11px; color:var(--muted); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.call-status { margin-left:auto; color:var(--muted); white-space:nowrap; font-size:11px; }
.call-status.running { color:var(--primary); }
.call-status.error,.failed { color:var(--red); }
.disclosure-chevron { flex-shrink:0; color:var(--muted); transition:transform .15s; }
.activity-tool[open] > summary .disclosure-chevron,.long-message[open] > summary > svg { transform:rotate(180deg); }
.call-detail { padding:12px 14px; margin-top:9px; background:#f7f9f7; border:1px solid var(--line); border-radius:8px; min-width:0; }
.native-name { color:var(--muted); font-size:11px; }
.native-name code { color:var(--ink); margin-left:6px; }
.call-detail h4 { margin:13px 0 6px; font-size:11px; font-weight:500; color:var(--muted); }
.call-detail pre { margin:6px 0 0; max-height:260px; overflow:auto; white-space:pre-wrap; overflow-wrap:anywhere; font:11px/1.8 Consolas,monospace; color:#405650; }
.call-detail .command-output { padding:10px 12px; background:#19312b; color:#e3f3e8; border-radius:6px; }
.call-detail .failed-output { color:var(--red); }
.call-arguments { margin-top:12px; }
.call-arguments > summary { display:flex; align-items:center; gap:6px; font-size:11px; color:var(--muted); }
.long-message > summary { color:var(--ink); font-size:13px; line-height:1.9; overflow-wrap:anywhere; }
.long-message > summary span { color:var(--primary); font-size:11px; white-space:nowrap; }
.long-message > summary svg { vertical-align:middle; color:var(--primary); }
.history-toggle { font-size:11px; padding:4px 0 16px; border:0; background:none; color:var(--muted); }
.history-toggle .rotated { transform:rotate(180deg); }
.activity-empty { margin:0; color:var(--muted); font-size:12px; line-height:1.8; }
@media(max-width:600px) {
  .activity-entry { gap:9px; }
  .activity-tool > summary { flex-wrap:wrap; gap:3px 8px; }
  .tool-context { order:3; width:100%; }
  .call-status { margin-left:auto; }
  .message-content p { font-size:12px; }
  .call-detail { padding:10px; }
}
@media(prefers-reduced-motion:reduce) { .loading-icon { animation:none; } }
</style>
