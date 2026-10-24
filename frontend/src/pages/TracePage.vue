<script setup lang="ts">
import {
  computed,
  defineAsyncComponent,
  onBeforeUnmount,
  onMounted,
  ref,
} from "vue";
import {
  Activity,
  ArrowRight,
  CircleAlert,
  Clock3,
  GitBranch,
  RefreshCw,
  Search,
  Users,
} from "@lucide/vue";
import { api, errorMessage } from "../api/client";
import {
  formatDate,
  taskStatusLabels,
  type Task,
  type TaskTrace,
  type TraceOverview,
} from "../types/contracts";
const AgentPanel = defineAsyncComponent(
  () => import("../components/AgentPanel.vue"),
);
const overview = ref<TraceOverview | null>(null),
  trace = ref<TaskTrace | null>(null);
const selected = ref<Task | null>(null),
  query = ref(""),
  error = ref(""),
  traceError = ref("");
const loading = ref(true),
  busy = ref(false),
  traceLoading = ref(false),
  epoch = ref(0);
let sequence = 0,
  timer: ReturnType<typeof setInterval>;
const rows = computed(() =>
  (overview.value?.tasks || []).filter((task) =>
    [task.title, task.id, task.thread_id]
      .join(" ")
      .toLowerCase()
      .includes(query.value.toLowerCase()),
  ),
);
const receipts = computed(() =>
  [...(trace.value?.events || [])]
    .reverse()
    .filter((event) =>
      ["tool_receipt", "tool_blocked", "dispatch_denied"].includes(event.event),
    ),
);
function seconds(value: unknown) {
  const number = Number(value);
  return value == null || !Number.isFinite(number)
    ? "—"
    : `${number.toFixed(2)} s`;
}
function percent(value: number | null | undefined) {
  return value == null ? "—" : `${(value * 100).toFixed(1)}%`;
}
async function refresh() {
  if (busy.value) return;
  busy.value = true;
  try {
    overview.value = await api.traces();
    error.value = "";
  } catch (failure) {
    error.value = errorMessage(failure);
  } finally {
    busy.value = false;
    loading.value = false;
  }
}
async function inspect(task: Task) {
  const current = ++sequence;
  selected.value = task;
  trace.value = null;
  traceError.value = "";
  traceLoading.value = true;
  try {
    const value = await api.trace(task.id);
    if (current === sequence) trace.value = value;
  } catch (failure) {
    if (current === sequence) traceError.value = errorMessage(failure);
  } finally {
    if (current === sequence) traceLoading.value = false;
  }
}
onMounted(() => {
  void refresh();
  timer = setInterval(() => {
    if (!document.hidden) void refresh();
  }, 10000);
});
onBeforeUnmount(() => {
  clearInterval(timer);
  sequence++;
});
</script>
<template>
  <div class="trace-page">
    <div class="trace-toolbar">
      <span
        ><Activity :size="16" />当前
        {{ overview?.sample_size ?? "—" }} 份提交的真实运行记录</span
      ><button class="ghost" :disabled="busy" @click="refresh">
        <RefreshCw :size="14" :class="{ 'loading-icon': busy }" />刷新统计
      </button>
    </div>
    <div v-if="error" class="notice error" role="alert">{{ error }}</div>
    <div class="trace-metrics">
      <article class="card">
        <Clock3 /><span>累计活跃耗时</span
        ><strong>{{
          overview
            ? seconds(
                overview.tasks.reduce(
                  (sum, row) => sum + Number(row.usage?.active_seconds || 0),
                  0,
                ),
              )
            : "—"
        }}</strong
        ><small>重叠调用只计一次 · 不含人工等待</small>
      </article>
      <article class="card">
        <GitBranch /><span>模型 / 工具调用</span
        ><strong
          >{{
            overview
              ? overview.tasks.reduce(
                  (sum, row) => sum + Number(row.usage?.model_calls || 0),
                  0,
                )
              : "—"
          }}
          /
          {{
            overview
              ? overview.tasks.reduce(
                  (sum, row) => sum + Number(row.usage?.tool_calls || 0),
                  0,
                )
              : "—"
          }}</strong
        ><small>共享预算中的实际调用计数</small>
      </article>
      <article class="card">
        <Users /><span>人工干预比例</span
        ><strong>{{ percent(overview?.human.revision_ratio) }}</strong
        ><small
          >{{ overview?.human.revised_tasks ?? "—" }} 份发生人工修订 /
          {{ overview?.sample_size ?? "—" }} 份提交</small
        >
      </article>
      <article class="card">
        <CircleAlert /><span>当前等待补充 / 曾确认</span
        ><strong
          >{{ overview?.human.waiting_input_tasks ?? "—" }} /
          {{ overview?.human.confirmation_tasks ?? "—" }}</strong
        ><small>历史确认按提交去重，当前版本仍需单独核验</small>
      </article>
    </div>
    <section class="quality-strip card" aria-label="识别质量评测">
      <div>
        <span class="eyebrow">EXTRACTION QUALITY</span>
        <h2>识别质量</h2>
        <p>{{ overview?.quality.reason || "正在读取评测状态" }}</p>
      </div>
      <div>
        <span>识别准确率</span
        ><strong>{{ percent(overview?.quality.accuracy) }}</strong>
      </div>
      <div>
        <span>误识率</span
        ><strong>{{ percent(overview?.quality.false_positive_rate) }}</strong>
      </div>
      <div>
        <span>漏识率</span
        ><strong>{{ percent(overview?.quality.false_negative_rate) }}</strong>
      </div>
      <span class="quality-status">{{
        overview?.quality.labeled_samples
          ? `${overview.quality.labeled_samples} 个金标样本`
          : "未关联金标 · 未评测"
      }}</span>
    </section>
    <p class="metric-definition">
      {{ overview?.human.definition }} 列表最多
      {{ overview?.limit ?? 100 }} 份，所有统计以当前列出的提交为分母。
    </p>
    <section class="card trace-list">
      <div class="list-heading">
        <h2>执行记录</h2>
        <label class="trace-search"
          ><Search :size="15" /><input
            v-model="query"
            placeholder="搜索账单、任务或线程"
            aria-label="搜索执行记录"
        /></label>
      </div>
      <div v-if="loading" class="empty">正在读取运行记录…</div>
      <div v-else class="table-scroll">
        <table>
          <thead>
            <tr>
              <th>账单 / 执行标识</th>
              <th>业务状态</th>
              <th>活跃耗时</th>
              <th>模型 / 工具</th>
              <th>人工修订</th>
              <th />
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="task in rows"
              :key="task.id"
              :class="{ selected: selected?.id === task.id }"
            >
              <td>
                <strong>{{ task.title }}</strong
                ><small class="mono">{{ task.id }}</small>
              </td>
              <td>{{ taskStatusLabels[task.status] || task.status }}</td>
              <td>{{ seconds(task.usage?.active_seconds) }}</td>
              <td>
                {{ task.usage?.model_calls ?? 0 }} /
                {{ task.usage?.tool_calls ?? 0 }}
              </td>
              <td>{{ task.event_counts.human_revision || 0 }} 次</td>
              <td>
                <button class="ghost" @click="inspect(task)">
                  查看 Trace<ArrowRight :size="13" />
                </button>
              </td>
            </tr>
            <tr v-if="!rows.length">
              <td colspan="6">没有匹配的执行记录</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
    <section v-if="selected" class="trace-detail" aria-label="执行追踪详情">
      <div class="detail-heading">
        <div>
          <span class="eyebrow">TRACE DETAIL</span>
          <h2>{{ selected.title }}</h2>
          <p class="mono">{{ selected.thread_id || "无线程" }}</p>
        </div>
        <button :disabled="traceLoading" @click="inspect(selected)">
          <RefreshCw :size="14" />刷新回执
        </button>
      </div>
      <div
        v-if="traceError || trace?.state_error"
        class="notice error"
        role="alert"
      >
        {{ traceError || trace?.state_error }}
      </div>
      <div v-if="traceLoading" class="card empty">
        正在读取官方检查点与调用回执…
      </div>
      <template v-else-if="trace">
        <section class="card path-card">
          <h3>Agent 调用路径</h3>
          <p>{{ trace.path_scope }}</p>
          <ol v-if="trace.call_path.length" class="call-path">
            <li
              v-for="(call, index) in trace.call_path"
              :key="`${call.call_id}-${index}`"
            >
              <span>{{ index + 1 }}</span
              ><b>{{ call.namespace.join(" / ") || "主控" }}</b
              ><ArrowRight :size="13" /><strong>{{ call.tool }}</strong
              ><em v-if="call.agent">→ {{ call.agent }}</em
              ><small class="mono">{{ call.call_id }}</small>
            </li>
          </ol>
          <p v-else>
            此线程当前检查点没有可读取的调用路径；下方展示已持久化的真实回执。
          </p>
        </section>
        <section class="card receipt-card">
          <h3>工具耗时与拦截回执</h3>
          <p>按回执完成时间排列；并行调用的耗时不相加为总处理时长。</p>
          <div class="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>工具</th>
                  <th>状态</th>
                  <th>耗时</th>
                  <th>业务版本</th>
                  <th>时间 / 原因</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(event, index) in receipts" :key="event.id || index">
                  <td>{{ event.tool }}</td>
                  <td>
                    {{
                      event.event === "tool_receipt" ? event.status : "被拦截"
                    }}
                  </td>
                  <td>{{ seconds(event.elapsed_seconds) }}</td>
                  <td>{{ event.revision ?? "—" }}</td>
                  <td>{{ event.message || formatDate(event.at) }}</td>
                </tr>
                <tr v-if="!receipts.length">
                  <td colspan="5">此任务还没有已持久化的工具完成回执。</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p v-if="trace.events_truncated">
            此处仅展示最近 1000 条事件；统计计数来自完整事件记录。
          </p>
        </section>
        <AgentPanel
          v-if="selected.thread_id"
          :key="selected.id"
          :connection-epoch="epoch"
          :task="selected"
          technical
          @refresh="refresh"
          @rejoin="epoch++"
        />
      </template>
    </section>
  </div>
</template>
<style scoped>
.trace-toolbar,
.list-heading,
.detail-heading {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  margin-bottom: 20px;
}
.trace-toolbar > span {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--muted);
}
.trace-metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}
.trace-metrics article {
  padding: 22px;
  display: grid;
  gap: 9px;
}
.trace-metrics svg {
  color: var(--primary);
  width: 19px;
  height: 19px;
  margin-bottom: 5px;
}
.trace-metrics span,
.quality-strip span {
  font-size: 12px;
  color: var(--muted);
}
.trace-metrics strong {
  font-size: 22px;
  font-weight: 500;
  font-variant-numeric: tabular-nums;
}
.trace-metrics small {
  font-size: 11px;
  color: var(--muted);
  line-height: 1.7;
}
.quality-strip {
  display: flex;
  align-items: center;
  gap: 32px;
  padding: 24px;
  margin-top: 20px;
  flex-wrap: wrap;
}
.quality-strip > div:first-child {
  flex: 1;
  min-width: 240px;
}
.quality-strip h2 {
  font-size: 17px;
  margin: 7px 0;
}
.quality-strip p,
.metric-definition,
.path-card > p,
.receipt-card > p {
  font-size: 11px;
  color: var(--muted);
  line-height: 1.8;
}
.quality-strip strong {
  display: block;
  margin-top: 8px;
  font-size: 20px;
  font-weight: 500;
}
.quality-status {
  background: #f2f3f1;
  padding: 8px 10px;
  border-radius: 6px;
}
.metric-definition {
  margin: 14px 0 24px;
}
.trace-list {
  padding: 22px 0 0;
  overflow: hidden;
}
.list-heading {
  padding: 0 22px;
}
.list-heading h2,
.detail-heading h2 {
  font-size: 19px;
}
.trace-search {
  display: flex;
  align-items: center;
  gap: 8px;
}
.trace-search input {
  max-width: 230px;
}
table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
  text-align: left;
}
th {
  font-size: 11px;
  color: var(--muted);
  background: #f7f9f8;
}
td,
th {
  padding: 14px 20px;
  border-top: 1px solid var(--line);
}
td small {
  display: block;
  margin-top: 6px;
  font-size: 10px;
  color: var(--muted);
}
td strong {
  font-weight: 500;
}
tr.selected {
  background: var(--primary-soft);
}
.trace-detail {
  margin-top: 32px;
}
.detail-heading p {
  font-size: 11px;
  color: var(--muted);
  margin-top: 8px;
}
.path-card,
.receipt-card {
  padding: 22px;
  margin-bottom: 20px;
}
.path-card h3,
.receipt-card h3 {
  font-size: 15px;
  margin-bottom: 8px;
}
.call-path {
  padding: 0;
  list-style: none;
  margin: 18px 0 0;
}
.call-path li {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  padding: 11px 0;
  border-top: 1px solid var(--line);
  font-size: 12px;
}
.call-path li > span {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: var(--primary-soft);
  display: grid;
  place-items: center;
}
.call-path em {
  font-style: normal;
  color: var(--primary);
}
.call-path small {
  color: var(--muted);
  font-size: 10px;
  margin-left: auto;
}
.receipt-card .table-scroll {
  margin-top: 18px;
}
@media (max-width: 1150px) {
  .trace-metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
@media (max-width: 600px) {
  .trace-metrics {
    grid-template-columns: 1fr;
  }
  .list-heading,
  .detail-heading {
    align-items: flex-start;
    flex-direction: column;
  }
  .quality-strip {
    gap: 20px;
  }
}
</style>
