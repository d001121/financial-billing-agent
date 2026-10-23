<script setup lang="ts">
import { useMessages, useToolCalls, type AnyStream, type SubagentDiscoverySnapshot } from "@langchain/vue";
import { computed, ref, watch } from "vue";
import { ChevronDown, CircleAlert, LoaderCircle, Users } from "@lucide/vue";
import AgentActivityFeed from "./AgentActivityFeed.vue";
const props = defineProps<{ stream: AnyStream; expert: SubagentDiscoverySnapshot; active: boolean; waiting: boolean }>();
const messages = useMessages(props.stream, () => props.expert);
const tools = useToolCalls(props.stream, () => props.expert);
const expanded = ref(props.expert.status === "running");
watch(() => props.expert.status, (status, previous) => {
  if (previous === 'running' && status === 'complete') expanded.value = false;
});
const names: Record<string, string> = {'document-specialist':'文档提取专家','billing-specialist':'账单核对专家'};
const title = computed(() => names[props.expert.name] || props.expert.name);
</script>
<template>
  <div class="expert-activity">
    <button class="expert-heading" :aria-expanded="expanded" @click="expanded = !expanded">
      <LoaderCircle v-if="expert.status === 'running' && active" :size="15" class="loading-icon" />
      <CircleAlert v-else-if="expert.status === 'error'" :size="15" />
      <Users v-else :size="15" />
      <strong>{{ title }}</strong><span>{{ expert.status === 'complete' ? '已结束' : expert.status === 'error' ? '调用失败' : active ? '处理中' : waiting ? '等待补充' : '未收到结束记录' }}</span>
      <ChevronDown :size="13" :class="{ rotated: expanded }" />
    </button>
    <div v-show="expanded" class="expert-content">
      <p v-if="expert.taskInput" class="expert-task">{{ expert.taskInput }}</p>
      <p v-if="expert.error" class="expert-error">{{ expert.error }}</p>
      <AgentActivityFeed :messages="messages" :tools="tools" :active="active && expert.status === 'running'" :waiting="waiting" />
    </div>
  </div>
</template>
<style scoped>
.expert-activity { border:1px solid var(--line); border-radius:9px; overflow:hidden; }
.expert-heading { display:flex; align-items:center; gap:9px; width:100%; padding:12px 14px; border:0; border-radius:0; background:#f8faf8; text-align:left; color:var(--primary); }
.expert-heading strong { font-size:12px; font-weight:500; }
.expert-heading span { margin-left:auto; color:var(--muted); font-size:11px; }
.expert-heading svg { flex-shrink:0; }
.expert-heading .rotated { transform:rotate(180deg); }
.expert-content { padding:14px; border-top:1px solid var(--line); }
.expert-task { margin:0 0 14px; color:var(--muted); font-size:11px; line-height:1.8; white-space:pre-wrap; overflow-wrap:anywhere; max-height:90px; overflow:auto; }
.expert-error { color:var(--red); font-size:12px; overflow-wrap:anywhere; }
</style>
