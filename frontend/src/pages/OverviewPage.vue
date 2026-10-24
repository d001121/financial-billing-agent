<script setup lang="ts">
import { computed } from "vue";
import {
  ArrowRight,
  ArrowUpRight,
  CheckCheck,
  Clock3,
  FileStack,
  Monitor,
  Plus,
  ShieldCheck,
} from "@lucide/vue";
import { formatDate, taskStatusLabels, type Task } from "../types/contracts";
import {
  taskCategory,
  taskNextAction,
  taskTime,
  taskTitle,
  recordCount,
  type TaskFilter,
} from "../utils/taskPresentation";

const props = defineProps<{
  tasks: Task[];
  loading: boolean;
  stale: boolean;
  updatedAt: string;
}>();
const emit = defineEmits<{
  create: [];
  open: [task: Task];
  filter: [filter: TaskFilter];
  screen: [];
  exit: [];
}>();
const unavailable = computed(
  () => props.loading || (props.stale && !props.updatedAt),
);
const statusGroups = computed(() => [
  {
    id: "review" as const,
    label: "待您处理",
    color: "#d89a46",
    count: props.tasks.filter((t) => taskCategory(t) === "review").length,
  },
  {
    id: "active" as const,
    label: "正在处理",
    color: "#3b8eae",
    count: props.tasks.filter((t) => taskCategory(t) === "active").length,
  },
  {
    id: "completed" as const,
    label: "已完成",
    color: "#218273",
    count: props.tasks.filter((t) => taskCategory(t) === "completed").length,
  },
  {
    id: "attention" as const,
    label: "暂停 / 异常",
    color: "#84919b",
    count: props.tasks.filter((t) => taskCategory(t) === "attention").length,
  },
]);
const metrics = computed(() => [
  {
    id: "all" as const,
    label: "全部处理账单",
    value: props.tasks.length,
    icon: FileStack,
    detail: "查看全部业务",
    tone: "neutral",
  },
  {
    id: "review" as const,
    label: "待您处理",
    value: statusGroups.value[0]!.count,
    icon: ShieldCheck,
    detail: "复核结果或补充信息",
    tone: "amber",
  },
  {
    id: "active" as const,
    label: "正在处理",
    value: statusGroups.value[1]!.count,
    icon: Clock3,
    detail: "查看最新处理进度",
    tone: "blue",
  },
  {
    id: "completed" as const,
    label: "已完成",
    value: statusGroups.value[2]!.count,
    icon: CheckCheck,
    detail: "查看结果与导出状态",
    tone: "green",
  },
]);
const ordered = computed(() =>
  [...props.tasks].sort(
    (a, b) => Date.parse(taskTime(b)) - Date.parse(taskTime(a)),
  ),
);
const waiting = computed(() =>
  ordered.value.filter((t) => taskCategory(t) === "review").slice(0, 3),
);
const recent = computed(() => ordered.value.slice(0, 4));
const feeCount = computed(() =>
  props.tasks.reduce((total, task) => total + recordCount(task), 0),
);
const week = computed(() => {
  const now = new Date(props.updatedAt || Date.now());
  const days = Array.from({ length: 7 }, (_, index) => {
    const date = new Date(
      now.getFullYear(),
      now.getMonth(),
      now.getDate() - 6 + index,
    );
    return {
      stamp: date.getTime(),
      day: `${date.getMonth() + 1}/${date.getDate()}`,
      count: 0,
    };
  });
  for (const task of props.tasks) {
    const date = new Date(task.created_at);
    const stamp = new Date(
      date.getFullYear(),
      date.getMonth(),
      date.getDate(),
    ).getTime();
    const target = days.find((day) => day.stamp === stamp);
    if (target) target.count++;
  }
  return days;
});
const weeklyMax = computed(() =>
  Math.max(1, ...week.value.map((day) => day.count)),
);
const weeklyCount = computed(() =>
  week.value.reduce((sum, day) => sum + day.count, 0),
);
</script>

<template>
  <div class="overview-page">
    <header class="overview-heading">
      <div>
        <span class="overline">WORKSPACE OVERVIEW</span>
        <h1>工作总览</h1>
        <p>从这里开始，掌握账单处理的每一步。</p>
      </div>
      <button class="screen-button" @click="emit('screen')">
        <Monitor :size="17" />大屏总控<ArrowUpRight :size="14" />
      </button>
    </header>

    <section class="start-panel">
      <div class="start-copy">
        <span class="start-kicker"><span />让复杂单据，变成清晰账目</span>
        <h2>材料交给航账，<br />把判断留给您。</h2>
        <p>
          上传邮件、PDF、图片或费用表，自动提取与核对。<br
            class="wide-only"
          />原件、问题和处理结果，在同一处看清。
        </p>
        <div class="start-actions">
          <button class="start-primary" @click="emit('create')">
            <Plus :size="18" />开始处理账单<ArrowRight :size="17" /></button
          ><button class="start-secondary" @click="emit('filter', 'all')">
            进入业务中心
          </button>
        </div>
      </div>
      <div class="journey" aria-label="账单处理流程">
        <ol>
          <li>
            <span>01</span>
            <div><strong>提交材料</strong><small>邮件与附件一并处理</small></div>
          </li>
          <li>
            <span>02</span>
            <div>
              <strong>智能提取与核对</strong><small>费用、金额与来源关联</small>
            </div>
          </li>
          <li>
            <span>03</span>
            <div>
              <strong>自动核验，按需复核</strong
              ><small>支持修改、原件定位和导出</small>
            </div>
          </li>
        </ol>
      </div>
    </section>

    <section class="overview-metrics" aria-label="账单概况">
      <button
        v-for="metric in metrics"
        :key="metric.id"
        :class="['overview-metric', metric.tone]"
        @click="emit('filter', metric.id)"
      >
        <div class="metric-top">
          <span>{{ metric.label }}</span
          ><component :is="metric.icon" :size="19" />
        </div>
        <strong>{{ unavailable ? "—" : metric.value }}<small>项</small></strong>
        <div class="metric-bottom">
          <span>{{ metric.detail }}</span
          ><ArrowUpRight :size="15" />
        </div>
      </button>
    </section>

    <div class="overview-main">
      <section class="overview-card todo-panel">
        <header class="panel-heading">
          <div>
            <span class="panel-kicker">YOUR NEXT STEP</span>
            <h2>
              待您处理<span v-if="!unavailable">{{
                statusGroups[0]!.count
              }}</span>
            </h2>
          </div>
          <button class="text-link" @click="emit('filter', 'review')">
            查看全部<ArrowRight :size="15" />
          </button>
        </header>
        <div v-if="unavailable" class="panel-empty">
          <Clock3 /><strong>{{
            loading ? "正在加载您的待办" : "暂时无法获取待办"
          }}</strong>
          <p>
            {{
              loading
                ? "连接工作空间后，即可查看处理账单。"
                : "请在服务恢复后刷新查看。"
            }}
          </p>
        </div>
        <div v-else-if="!waiting.length" class="panel-empty">
          <span class="clear-icon"><CheckCheck :size="26" /></span
          ><strong>当前没有待处理事项</strong>
          <p>您可以提交新材料，或前往业务中心查看历史结果。</p>
          <button class="text-link" @click="emit('create')">
            开始新的账单处理<ArrowRight :size="15" />
          </button>
        </div>
        <div v-else class="todo-list">
          <button
            v-for="task in waiting"
            :key="task.id"
            class="todo-item"
            @click="emit('open', task)"
          >
            <span class="todo-icon"><ShieldCheck :size="20" /></span>
            <div class="todo-copy">
              <strong>{{ taskTitle(task) }}</strong>
              <p>{{ task.accounting_entity || "记账主体待补充" }}</p>
              <span>{{ taskNextAction(task) }}</span>
            </div>
            <div class="todo-action">
              <span class="mini-status">{{
                taskStatusLabels[task.status] || task.status
              }}</span
              ><span>去处理<ArrowRight :size="14" /></span>
            </div>
          </button>
        </div>
        <footer class="panel-foot">
          <ShieldCheck :size="14" /><span
            >仅低置信度字段需要复核；随时可查看原文、定位原件并修改结果。</span
          >
        </footer>
      </section>

      <section class="overview-card status-panel">
        <header class="panel-heading">
          <div>
            <span class="panel-kicker">PROCESSING STATUS</span>
            <h2>账单分布</h2>
          </div>
          <span class="scope-label">全部账单</span>
        </header>
        <template v-if="!unavailable">
          <div class="distribution-total">
            <strong>{{ tasks.length }}</strong>
            <div>
              <span>项处理账单</span><small>已提取 {{ feeCount }} 条费用</small>
            </div>
          </div>
          <div
            v-if="tasks.length"
            class="distribution-bar"
            role="img"
            :aria-label="
              statusGroups
                .map((group) => `${group.label}${group.count}项`)
                .join('，')
            "
          >
            <span
              v-for="group in statusGroups"
              :key="group.id"
              :style="{
                width: `${(group.count / tasks.length) * 100}%`,
                background: group.color,
              }"
            />
          </div>
          <div v-else class="distribution-bar empty-bar" />
          <div class="distribution-legend">
            <button
              v-for="group in statusGroups"
              :key="group.id"
              @click="emit('filter', group.id)"
            >
              <span
                ><i :style="{ background: group.color }" />{{
                  group.label
                }}</span
              ><strong>{{ group.count }}<ArrowUpRight :size="13" /></strong>
            </button>
          </div>
        </template>
        <div v-else class="panel-empty">
          <FileStack /><strong>—</strong>
          <p>等待账单数据同步</p>
        </div>
      </section>
    </div>

    <div class="overview-bottom">
      <section class="overview-card recent-panel">
        <header class="panel-heading">
          <div>
            <span class="panel-kicker">RECENT ACTIVITY</span>
            <h2>最近更新</h2>
          </div>
          <button class="text-link" @click="emit('filter', 'all')">
            全部账单<ArrowRight :size="15" />
          </button>
        </header>
        <div v-if="!unavailable && recent.length" class="recent-list">
          <button
            v-for="task in recent"
            :key="task.id"
            class="recent-item"
            @click="emit('open', task)"
          >
            <span :class="['recent-dot', taskCategory(task)]" /><span
              class="recent-title"
              >{{ taskTitle(task)
              }}<small>{{
                task.accounting_entity || "记账主体待补充"
              }}</small></span
            ><span class="recent-meta"
              ><span>{{ taskStatusLabels[task.status] || task.status }}</span
              ><small>{{ formatDate(taskTime(task)) }}</small></span
            ><ArrowUpRight :size="15" />
          </button>
        </div>
        <div v-else class="panel-empty compact">
          <FileStack />
          <p>
            {{
              unavailable
                ? "等待最新账单记录"
                : "提交第一份材料后，处理动态将在这里显示。"
            }}
          </p>
        </div>
      </section>
      <section class="overview-card volume-panel">
        <header class="panel-heading">
          <div>
            <span class="panel-kicker">PAST 7 DAYS</span>
            <h2>材料处理需求</h2>
          </div>
          <span class="volume-total"
            >{{ unavailable ? "—" : weeklyCount }}<small>项新账单</small></span
          >
        </header>
        <div
          class="week-chart"
          role="img"
          :aria-label="
            unavailable
              ? '暂无近期账单数量数据'
              : week.map((day) => `${day.day}创建${day.count}项`).join('，')
          "
        >
          <div v-for="day in week" :key="day.stamp" class="day-column">
            <span class="day-value">{{ unavailable ? "—" : day.count }}</span>
            <div class="bar-space">
              <span
                :class="{ zero: !day.count || unavailable }"
                :style="{
                  height: unavailable
                    ? '2px'
                    : `${Math.max(2, (day.count / weeklyMax) * 92)}px`,
                }"
              />
            </div>
            <span class="day-label">{{ day.day }}</span>
          </div>
        </div>
        <p class="chart-note">按账单创建日期统计，非账单金额或完成量。</p>
      </section>
    </div>
    <div class="overview-sync">
      <span :class="['sync-dot', { stale }]" />{{
        loading
          ? "正在连接工作空间"
          : stale
            ? `同步中断 · 上次更新 ${updatedAt ? formatDate(updatedAt) : "尚无数据"}`
            : `数据已同步 · ${updatedAt ? formatDate(updatedAt) : "等待首次同步"}`
      }}<span class="sync-caption">账单统计包含当前工作空间的全部记录</span>
    </div>
  </div>
</template>

<style scoped>
.overview-page {
  display: grid;
  gap: 24px;
}
.overview-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
}
.overline,
.panel-kicker {
  color: #82908f;
  font-size: 12px;
  letter-spacing: 1.8px;
  font-weight: 600;
}
.overview-heading h1 {
  font-size: 29px;
  margin: 5px 0 6px;
  color: #173634;
  letter-spacing: -0.8px;
}
.overview-heading p {
  color: #7a8586;
  font-size: 13px;
}
.screen-button {
  background: #fff;
  color: #33514e;
  min-height: 42px;
}
.start-panel {
  position: relative;
  display: grid;
  grid-template-columns: 1.3fr 1fr;
  gap: 30px;
  overflow: hidden;
  border: 1px solid #dce9e5;
  border-radius: var(--radius);
  background: #edf4f1;
  padding: 26px 30px;
}
.start-copy {
  position: relative;
  z-index: 1;
}
.start-kicker {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  color: #4a7970;
}
.start-kicker > span {
  height: 5px;
  width: 5px;
  background: #478e7d;
  border-radius: 100%;
}
.start-copy h2 {
  font-size: clamp(25px, 2.1vw, 32px);
  line-height: 1.45;
  letter-spacing: -0.8px;
  color: #183e37;
  font-weight: 600;
  margin-top: 15px;
}
.start-copy p {
  color: #698079;
  font-size: 14px;
  line-height: 1.9;
  margin-top: 13px;
}
.start-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 25px;
  flex-wrap: wrap;
}
.start-primary {
  color: #fff;
  border-color: #246758;
  background: #246758;
  min-height: 44px;
  padding: 11px 18px;
  box-shadow: 0 3px 6px #163e3610;
}
.start-primary:hover:not(:disabled) {
  background: #1e594c;
  border-color: #1e594c;
}
.start-secondary {
  background: transparent;
  border-color: transparent;
  color: #456b60;
}
.journey {
  display: flex;
  align-items: center;
  gap: 30px;
  justify-content: flex-end;
  position: relative;
}
.journey ol {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 24px;
}
.journey li {
  display: flex;
  align-items: center;
  gap: 12px;
  position: relative;
}
.journey li:not(:last-child)::after {
  content: "";
  position: absolute;
  top: 34px;
  left: 13px;
  height: 22px;
  border-left: 1px solid #c5d9cd;
}
.journey li > span {
  width: 28px;
  height: 28px;
  border: 1px solid #c4dacf;
  color: #648a79;
  display: grid;
  place-items: center;
  font-family: Georgia, serif;
  font-size: 14px;
  border-radius: 100%;
  background: #f5f9f6;
}
.journey strong {
  display: block;
  color: #325b4e;
  font-size: 14px;
  font-weight: 600;
}
.journey small {
  display: block;
  color: #83998c;
  font-size: 12px;
  margin-top: 4px;
}
.overview-metrics {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}
.overview-metric {
  display: block;
  text-align: left;
  padding: 20px 22px 15px;
  border: 1px solid #e0e6e3;
  border-radius: 12px;
  background: #fff;
  min-width: 0;
  font-weight: 400;
}
.overview-metric:hover:not(:disabled) {
  border-color: #aac9bd;
  background: #fcfdfc;
}
.metric-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  color: #667877;
  font-size: 14px;
}
.metric-top svg {
  color: #90a19e;
}
.overview-metric > strong {
  display: block;
  font-size: 34px;
  font-weight: 500;
  letter-spacing: -1px;
  margin: 9px 0 12px;
  color: #263f3d;
  font-variant-numeric: tabular-nums;
}
.overview-metric > strong small {
  font-size: 13px;
  margin-left: 7px;
  color: #8c9996;
  font-weight: 400;
  letter-spacing: 0;
}
.metric-bottom {
  display: flex;
  align-items: center;
  justify-content: space-between;
  color: #8b9693;
  font-size: 13px;
  padding-top: 11px;
  border-top: 1px solid #f0f2f0;
}
.amber .metric-top svg,
.amber > strong {
  color: #ac7a2d;
}
.blue .metric-top svg,
.blue > strong {
  color: #397d98;
}
.green .metric-top svg,
.green > strong {
  color: #348675;
}
.overview-main {
  display: grid;
  grid-template-columns: 1.65fr 1fr;
  gap: 20px;
}
.overview-card {
  background: #fff;
  border: 1px solid #e1e7e3;
  border-radius: 14px;
  min-width: 0;
  overflow: hidden;
}
.panel-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 22px 24px 16px;
  gap: 12px;
}
.panel-kicker {
  font-size: 11px;
  letter-spacing: 1.4px;
  color: #9aa5a1;
}
.panel-heading h2 {
  font-size: 16px;
  color: #344d47;
  margin-top: 5px;
  display: flex;
  align-items: center;
  gap: 10px;
  font-weight: 600;
}
.panel-heading h2 > span {
  color: #a78549;
  background: #faf2e6;
  padding: 1px 7px;
  font-size: 13px;
  border-radius: 4px;
  font-weight: 500;
}
.text-link {
  background: transparent;
  color: #658378;
  border: 0;
  padding: 7px 0;
  font-size: 13px;
  white-space: nowrap;
}
.text-link:hover:not(:disabled) {
  color: #246758;
  background: transparent;
}
.todo-list {
  padding: 0 24px;
}
.todo-item {
  width: 100%;
  display: flex;
  justify-content: flex-start;
  align-items: center;
  gap: 13px;
  text-align: left;
  background: transparent;
  border: 0;
  border-radius: 0;
  border-bottom: 1px solid #eef1ee;
  padding: 15px 0;
}
.todo-item:last-child {
  border-bottom: 0;
}
.todo-item:hover:not(:disabled),
.recent-item:hover:not(:disabled) {
  background: #f6f9f5;
  border-color: #eef1ee;
}
.todo-icon {
  width: 38px;
  height: 42px;
  display: grid;
  place-items: center;
  color: #a58a59;
  background: #f8f3e9;
  border-radius: 7px;
  flex-shrink: 0;
}
.todo-copy {
  min-width: 0;
  flex: 1;
}
.todo-copy strong {
  display: block;
  font-weight: 500;
  font-size: 14px;
  color: #394e48;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.todo-copy p {
  color: #9aa49d;
  font-size: 12px;
  margin-top: 4px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.todo-copy > span {
  display: block;
  color: #879387;
  font-size: 12px;
  margin-top: 6px;
}
.todo-action {
  display: grid;
  justify-items: end;
  gap: 11px;
  flex-shrink: 0;
}
.mini-status {
  color: #a58a59;
  font-size: 12px;
  font-weight: 400;
}
.todo-action > span:last-child {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: #648777;
  font-size: 13px;
}
.panel-foot {
  display: flex;
  align-items: center;
  gap: 7px;
  color: #98a199;
  font-size: 12px;
  border-top: 1px solid #eef1eb;
  margin-top: 7px;
  padding: 12px 24px;
  background: #fdfefa;
}
.scope-label {
  font-size: 12px;
  color: #9ba59e;
}
.distribution-total {
  display: flex;
  gap: 15px;
  align-items: center;
  padding: 9px 24px 20px;
}
.distribution-total > strong {
  font-size: 45px;
  font-weight: 400;
  line-height: 1;
  color: #304c45;
  letter-spacing: -1.5px;
  font-variant-numeric: tabular-nums;
}
.distribution-total span,
.distribution-total small {
  display: block;
  color: #8a978d;
  font-size: 12px;
}
.distribution-total small {
  margin-top: 4px;
  color: #a6aea6;
}
.distribution-bar {
  display: flex;
  height: 9px;
  border-radius: 5px;
  margin: 0 24px 16px;
  overflow: hidden;
  gap: 3px;
  background: #eef2ee;
}
.empty-bar {
  background: #eef2ee;
}
.distribution-legend {
  display: grid;
  padding: 0 24px 20px;
}
.distribution-legend button {
  display: flex;
  justify-content: space-between;
  color: #839185;
  font-size: 13px;
  border: 0;
  background: transparent;
  padding: 8px 0;
}
.distribution-legend button:hover:not(:disabled) {
  background: #f7faf6;
}
.distribution-legend span,
.distribution-legend strong {
  display: flex;
  align-items: center;
  gap: 9px;
}
.distribution-legend i {
  width: 7px;
  height: 7px;
  border-radius: 2px;
}
.distribution-legend strong {
  color: #536b5f;
  font-weight: 500;
  gap: 12px;
}
.distribution-legend svg {
  color: #afb9b0;
}
.panel-empty {
  display: grid;
  justify-items: center;
  align-content: center;
  gap: 9px;
  min-height: 205px;
  text-align: center;
  padding: 26px;
  color: #9aa69b;
}
.panel-empty strong {
  color: #6b8173;
  font-weight: 500;
  font-size: 14px;
}
.panel-empty p {
  color: #a1aba0;
  font-size: 13px;
  max-width: 300px;
  line-height: 1.8;
}
.clear-icon {
  background: #f0f6ef;
  color: #7fa283;
  border-radius: 50%;
  padding: 12px;
}
.overview-bottom {
  display: grid;
  grid-template-columns: 1.25fr 1fr;
  gap: 20px;
}
.recent-list {
  padding: 0 24px 14px;
}
.recent-item {
  width: 100%;
  display: flex;
  text-align: left;
  gap: 11px;
  border: 0;
  border-top: 1px solid #f0f2ef;
  border-radius: 0;
  padding: 12px 0;
}
.recent-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #84919b;
  flex-shrink: 0;
}
.recent-dot.review {
  background: #d89a46;
}
.recent-dot.active {
  background: #3b8eae;
}
.recent-dot.completed {
  background: #218273;
}
.recent-title {
  min-width: 0;
  flex: 1;
  color: #566f61;
  font-size: 13px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.recent-title small {
  display: block;
  color: #a1ada2;
  font-size: 12px;
  margin-top: 4px;
}
.recent-meta {
  display: grid;
  text-align: right;
  gap: 3px;
  color: #8f9f92;
  font-size: 12px;
  flex-shrink: 0;
}
.recent-meta small {
  color: #b1bbb1;
  font-size: 11px;
  font-variant-numeric: tabular-nums;
}
.recent-item > svg {
  color: #b1bdb3;
}
.compact {
  min-height: 200px;
}
.volume-total {
  font-size: 22px;
  color: #617e6b;
  font-variant-numeric: tabular-nums;
}
.volume-total small {
  display: block;
  font-size: 11px;
  color: #a0afa2;
  margin-top: 2px;
  text-align: right;
}
.week-chart {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  padding: 8px 25px 0;
  gap: 12px;
}
.day-column {
  text-align: center;
  min-width: 0;
}
.day-value {
  font-size: 12px;
  color: #8fa08d;
  font-variant-numeric: tabular-nums;
}
.bar-space {
  height: 98px;
  display: flex;
  align-items: flex-end;
  justify-content: center;
  margin-top: 8px;
  border-bottom: 1px solid #edf1ec;
}
.bar-space > span {
  width: 20px;
  max-width: 90%;
  background: #9ebfa9;
  border-radius: 3px 3px 0 0;
}
.bar-space > span.zero {
  background: #e6ede5;
}
.day-column:last-child .bar-space > span:not(.zero) {
  background: #3d8e72;
}
.day-label {
  display: block;
  color: #9ba998;
  font-size: 11px;
  margin-top: 8px;
}
.chart-note {
  font-size: 11px;
  color: #a5b0a0;
  padding: 15px 24px 17px;
}
.overview-sync {
  display: flex;
  gap: 7px;
  align-items: center;
  font-size: 12px;
  color: #a2afa3;
  padding: 0 3px;
  flex-wrap: wrap;
}
.sync-dot {
  width: 5px;
  height: 5px;
  background: #76a487;
  border-radius: 50%;
}
.sync-dot.stale {
  background: #c49958;
}
.sync-caption {
  margin-left: auto;
  color: #b2bcb0;
}
@media (min-width: 1600px) {
  .start-panel {
    padding: 42px 45px;
  }
  .journey {
    gap: 42px;
  }
  .start-copy h2 {
    font-size: 39px;
  }
}
@media (max-width: 1150px) {
  .journey {
    justify-content: center;
  }
  .start-panel {
    grid-template-columns: 1.5fr 1fr;
    padding: 28px;
  }
  .overview-metric {
    padding: 17px;
  }
  .overview-main {
    grid-template-columns: 1.4fr 1fr;
  }
  .panel-heading {
    padding: 20px 20px 15px;
  }
  .todo-list {
    padding: 0 20px;
  }
}
@media (max-width: 850px) {
  .overview-main,
  .overview-bottom {
    grid-template-columns: 1fr;
  }
  .overview-metrics {
    grid-template-columns: repeat(2, 1fr);
  }
  .start-panel {
    grid-template-columns: 1fr;
  }
  .journey {
    display: none;
  }
  .overview-heading h1 {
    font-size: 25px;
  }
  .overview-page {
    gap: 18px;
  }
}
@media (max-width: 480px) {
  .overview-heading {
    align-items: flex-start;
    gap: 12px;
  }
  .overview-heading p {
    max-width: 190px;
    font-size: 13px;
  }
  .screen-button {
    font-size: 13px;
    padding: 8px 10px;
    min-height: 36px;
  }
  .screen-button > svg:last-child {
    display: none;
  }
  .overview-heading h1 {
    font-size: 24px;
  }
  .start-panel {
    padding: 24px 22px;
  }
  .start-copy h2 {
    font-size: 27px;
  }
  .start-copy p {
    font-size: 13px;
  }
  .wide-only {
    display: none;
  }
  .overview-metrics {
    gap: 10px;
  }
  .overview-metric {
    padding: 14px;
  }
  .metric-top {
    font-size: 12px;
  }
  .metric-bottom {
    font-size: 11px;
  }
  .metric-bottom > svg {
    display: none;
  }
  .overview-metric > strong {
    font-size: 30px;
  }
  .panel-heading {
    padding: 18px;
  }
  .todo-list,
  .recent-list {
    padding-left: 18px;
    padding-right: 18px;
  }
  .todo-icon {
    display: none;
  }
  .todo-copy > span {
    font-size: 11px;
  }
  .todo-action {
    gap: 7px;
  }
  .todo-copy strong {
    font-size: 13px;
  }
  .panel-foot {
    padding-left: 18px;
    font-size: 11px;
  }
  .overview-sync {
    font-size: 11px;
  }
  .sync-caption {
    display: none;
  }
  .recent-meta > span {
    font-size: 11px;
  }
}
</style>
