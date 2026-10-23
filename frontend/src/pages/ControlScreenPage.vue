<script setup lang="ts">
import { computed } from "vue";
import {
  Anchor,
  ArrowLeft,
  ArrowRight,
  ArrowUpRight,
  Building2,
  CheckCheck,
  CircleAlert,
  Clock3,
  FileStack,
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
  manage: [];
}>();
const unavailable = computed(
  () => props.loading || (props.stale && !props.updatedAt),
);
const groups = computed(() => [
  {
    id: "review" as const,
    label: "待您处理",
    color: "#d3ad6a",
    icon: ShieldCheck,
    count: props.tasks.filter((task) => taskCategory(task) === "review").length,
  },
  {
    id: "active" as const,
    label: "正在处理",
    color: "#62b8c3",
    icon: Clock3,
    count: props.tasks.filter((task) => taskCategory(task) === "active").length,
  },
  {
    id: "completed" as const,
    label: "已完成",
    color: "#71bea0",
    icon: CheckCheck,
    count: props.tasks.filter((task) => taskCategory(task) === "completed")
      .length,
  },
  {
    id: "attention" as const,
    label: "暂停 / 异常",
    color: "#8f9daa",
    icon: CircleAlert,
    count: props.tasks.filter((task) => taskCategory(task) === "attention")
      .length,
  },
]);
const feeCount = computed(() =>
  props.tasks.reduce((sum, task) => sum + recordCount(task), 0),
);
const sorted = computed(() =>
  [...props.tasks].sort(
    (a, b) => Date.parse(taskTime(b)) - Date.parse(taskTime(a)),
  ),
);
const waiting = computed(() =>
  sorted.value.filter((task) => taskCategory(task) === "review").slice(0, 5),
);
const latest = computed(() => sorted.value.slice(0, 5));
const entities = computed(() => {
  const counts = new Map<string, number>();
  props.tasks.forEach((task) => {
    const key = task.accounting_entity || "记账主体待补充";
    counts.set(key, (counts.get(key) || 0) + 1);
  });
  const ordered = [...counts].sort((a, b) => b[1] - a[1]);
  const first = ordered.slice(0, 4).map(([name, count]) => ({ name, count }));
  if (ordered.length > 4)
    first.push({
      name: "其余主体",
      count: ordered.slice(4).reduce((sum, [, value]) => sum + value, 0),
    });
  return first;
});
const entityMax = computed(() =>
  Math.max(1, ...entities.value.map((entity) => entity.count)),
);
const entityCount = computed(
  () =>
    new Set(props.tasks.map((task) => task.accounting_entity).filter(Boolean))
      .size,
);
const ringStyle = computed(() => {
  if (!props.tasks.length || unavailable.value)
    return { background: "#26404b" };
  let offset = 0;
  const stops = groups.value.map((group) => {
    const start = offset;
    offset += (group.count / props.tasks.length) * 100;
    return `${group.color} ${start}% ${offset}%`;
  });
  return { background: `conic-gradient(${stops.join(",")})` };
});
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
      label: `${date.getMonth() + 1}/${date.getDate()}`,
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
    const day = days.find((value) => value.stamp === stamp);
    if (day) day.count++;
  }
  return days;
});
const weekMax = computed(() =>
  Math.max(1, ...week.value.map((day) => day.count)),
);
</script>

<template>
  <div class="control-screen">
    <header class="screen-header">
      <div class="screen-brand">
        <span class="screen-logo"><Anchor /></span>
        <div>
          <span>HARBOR OPERATIONS</span>
          <h1>航账 · 业务总控制台</h1>
        </div>
      </div>
      <div class="screen-header-actions">
        <button class="exit-button" @click="emit('manage')">
          管理控制台<ArrowUpRight :size="15" />
        </button>
        <div :class="['sync-state', { warning: stale }]">
          <i /><span
            >{{
              loading ? "正在连接" : stale ? "数据同步中断" : "账单数据已同步"
            }}<small>{{
              updatedAt ? `上次更新 ${formatDate(updatedAt)}` : "等待首次同步"
            }}</small></span
          >
        </div>
        <button class="exit-button" @click="emit('exit')">
          <ArrowLeft :size="15" />返回工作空间
        </button>
      </div>
    </header>

    <div v-if="stale" class="screen-warning" role="status">
      <CircleAlert :size="16" />{{
        updatedAt
          ? "以下展示上次同步的数据，恢复连接后将继续更新。"
          : "当前无法获取账单数据，请检查服务连接。"
      }}
    </div>

    <section class="screen-stats" aria-label="全部账单统计">
      <button class="total-stat" @click="emit('filter', 'all')">
        <span><FileStack :size="17" />全部账单</span
        ><strong>{{ unavailable ? "—" : tasks.length }}<small>项</small></strong
        ><span class="stat-link">打开业务中心<ArrowUpRight :size="15" /></span>
      </button>
      <button
        v-for="group in groups.slice(0, 3)"
        :key="group.id"
        class="screen-stat"
        :style="{ '--stat-color': group.color }"
        @click="emit('filter', group.id)"
      >
        <span><component :is="group.icon" :size="17" />{{ group.label }}</span
        ><strong>{{ unavailable ? "—" : group.count }}<small>项</small></strong
        ><span class="stat-link"
          >{{
            group.id === "review"
              ? "查看复核与补充事项"
              : group.id === "active"
                ? "查看账单进度"
                : "查看处理结果"
          }}<ArrowUpRight :size="15"
        /></span>
      </button>
      <button class="screen-stat fee-stat" @click="emit('filter', 'all')">
        <span><FileStack :size="17" />已提取费用</span
        ><strong>{{ unavailable ? "—" : feeCount }}<small>条</small></strong
        ><span class="stat-link"
          >来自已保存的费用记录<ArrowUpRight :size="15"
        /></span>
      </button>
    </section>

    <div class="screen-content">
      <div class="screen-left">
        <section class="screen-panel state-panel">
          <div class="screen-panel-heading">
            <div>
              <span>STATUS DISTRIBUTION</span>
              <h2>账单状态分布</h2>
            </div>
            <small>全部记录</small>
          </div>
          <div class="status-visual">
            <div
              class="status-ring"
              :style="ringStyle"
              role="img"
              :aria-label="
                unavailable
                  ? '等待账单状态数据'
                  : groups
                      .map((group) => `${group.label}${group.count}项`)
                      .join('，')
              "
            >
              <div>
                <strong>{{ unavailable ? "—" : tasks.length }}</strong
                ><span>处理账单</span>
              </div>
            </div>
          </div>
          <div class="status-legend">
            <button
              v-for="group in groups"
              :key="group.id"
              @click="emit('filter', group.id)"
            >
              <span
                ><i :style="{ background: group.color }" />{{
                  group.label
                }}</span
              ><strong
                >{{ unavailable ? "—" : group.count }}<ArrowRight :size="12"
              /></strong>
            </button>
          </div>
        </section>
        <section class="screen-panel weekly-panel">
          <div class="screen-panel-heading">
            <div>
              <span>INCOMING WORK</span>
              <h2>近 7 天新增账单</h2>
            </div>
          </div>
          <div
            class="screen-week-chart"
            role="img"
            :aria-label="
              unavailable
                ? '等待近期账单数量数据'
                : week.map((day) => `${day.label}创建${day.count}项`).join('，')
            "
          >
            <div v-for="day in week" :key="day.stamp" class="screen-day">
              <span>{{ unavailable ? "—" : day.count }}</span>
              <div>
                <i
                  :class="{ zero: unavailable || !day.count }"
                  :style="{
                    height: unavailable
                      ? '2px'
                      : `${Math.max(2, (day.count / weekMax) * 64)}px`,
                  }"
                />
              </div>
              <small>{{ day.label }}</small>
            </div>
          </div>
          <p class="screen-note">按账单创建日期统计</p>
        </section>
      </div>

      <section class="screen-panel queue-panel">
        <div class="screen-panel-heading">
          <div>
            <span>ACTION REQUIRED</span>
            <h2>需要您的下一步</h2>
          </div>
          <button class="screen-text-link" @click="emit('filter', 'review')">
            查看全部<ArrowRight :size="14" />
          </button>
        </div>
        <div class="queue-summary">
          <span class="summary-icon"><ShieldCheck :size="22" /></span>
          <p>
            材料已整理，等待您的判断。<small
              >可核对原件、修改费用，或补充处理所需信息。</small
            >
          </p>
          <strong
            >{{ unavailable ? "—" : groups[0]!.count
            }}<small>项待办</small></strong
          >
        </div>
        <div v-if="!unavailable && waiting.length" class="screen-queue">
          <button
            v-for="(task, index) in waiting"
            :key="task.id"
            class="queue-item"
            @click="emit('open', task)"
          >
            <span class="queue-number">{{
              String(index + 1).padStart(2, "0")
            }}</span>
            <div class="queue-copy">
              <strong :title="taskTitle(task)">{{ taskTitle(task) }}</strong
              ><small>{{ task.accounting_entity || "记账主体待补充" }}</small
              ><span>{{ taskNextAction(task) }}</span>
            </div>
            <div class="queue-item-action">
              <span>{{ taskStatusLabels[task.status] || task.status }}</span
              ><i><ArrowUpRight :size="16" /></i>
            </div>
          </button>
        </div>
        <div v-else class="screen-empty">
          <CheckCheck :size="29" />
          <h3>{{ unavailable ? "等待待办数据" : "当前没有待处理事项" }}</h3>
          <p>
            {{
              unavailable
                ? "连接工作空间后显示最新账单。"
                : "新的复核或补充信息请求会在这里出现。"
            }}
          </p>
          <button
            v-if="!unavailable"
            class="screen-text-link"
            @click="emit('create')"
          >
            提交一份新材料<Plus :size="14" />
          </button>
        </div>
        <div class="queue-footer">
          <span>先看结果，再决定是否打开原件</span
          ><button
            class="screen-text-link"
            @click="emit('filter', 'attention')"
          >
            暂停与异常 {{ unavailable ? "—" : groups[3]!.count
            }}<ArrowRight :size="14" />
          </button>
        </div>
      </section>

      <div class="screen-right">
        <section class="screen-panel entity-panel">
          <div class="screen-panel-heading">
            <div>
              <span>ACCOUNTING ENTITIES</span>
              <h2>记账主体分布</h2>
            </div>
            <Building2 :size="18" />
          </div>
          <div class="entity-summary">
            <strong>{{ unavailable ? "—" : entityCount }}</strong
            ><span>个已指定主体<small>按处理账单数量统计</small></span>
          </div>
          <div v-if="!unavailable && entities.length" class="entity-list">
            <div
              v-for="(entity, index) in entities"
              :key="entity.name"
              class="entity-row"
            >
              <div>
                <span
                  ><i>{{ String(index + 1).padStart(2, "0") }}</i
                  ><span :title="entity.name">{{ entity.name }}</span></span
                ><strong>{{ entity.count }}</strong>
              </div>
              <div class="entity-track">
                <i :style="{ width: `${(entity.count / entityMax) * 100}%` }" />
              </div>
            </div>
          </div>
          <div v-else class="screen-empty compact">
            <Building2 />
            <p>
              {{
                unavailable ? "等待主体数据" : "提交材料时，按次指定记账主体。"
              }}
            </p>
          </div>
        </section>
        <section class="screen-panel entry-panel">
          <span class="entry-overline">START A NEW TASK</span>
          <h2>下一份账单，<br />现在开始。</h2>
          <p>邮件、PDF、图片、Excel、Word<br />集中提交，一次处理。</p>
          <button @click="emit('create')">
            <Plus :size="16" />提交新材料<ArrowRight :size="16" />
          </button>
        </section>
      </div>
    </div>

    <section class="screen-panel activity-panel">
      <div class="screen-panel-heading">
        <div>
          <span>LATEST ACTIVITY</span>
          <h2>最近账单动态</h2>
        </div>
        <button class="screen-text-link" @click="emit('filter', 'all')">
          全部账单<ArrowRight :size="14" />
        </button>
      </div>
      <div v-if="!unavailable && latest.length" class="activity-list">
        <button
          v-for="task in latest"
          :key="task.id"
          class="activity-item"
          @click="emit('open', task)"
        >
          <span :class="['activity-dot', taskCategory(task)]" />
          <div>
            <strong :title="taskTitle(task)">{{ taskTitle(task) }}</strong
            ><span
              >{{ taskStatusLabels[task.status] || task.status }}<i>·</i
              >{{ formatDate(taskTime(task)) }}</span
            >
          </div>
          <ArrowUpRight :size="14" />
        </button>
      </div>
      <div v-else class="screen-empty activity-empty">
        <p>
          {{
            unavailable
              ? "等待最新账单记录"
              : "暂无处理动态，提交材料后即可查看。"
          }}
        </p>
      </div>
    </section>
    <footer class="screen-footer">
      <span>HARBOR · 航运智能账单助手</span
      ><span>当前工作空间全部账单 · 不合并不同币种金额</span>
    </footer>
  </div>
</template>

<style scoped>
.control-screen {
  --screen-bg: #0c202b;
  --screen-panel: #132b36;
  --screen-line: #26414a;
  --screen-muted: #77919a;
  color: #d3e3e5;
  background: var(--screen-bg);
  min-height: 100vh;
  padding: 26px 34px 20px;
  display: grid;
  align-content: start;
  gap: 20px;
  background-image: radial-gradient(
    ellipse at 50% -30%,
    #24515b5e,
    transparent 65%
  );
}
.screen-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 20px;
  padding-bottom: 22px;
  border-bottom: 1px solid #23404a;
}
.screen-brand {
  display: flex;
  align-items: center;
  gap: 13px;
}
.screen-logo {
  display: grid;
  place-items: center;
  width: 45px;
  height: 45px;
  background: #1a3c42;
  border: 1px solid #35646a;
  border-radius: 10px;
  color: #9bcab9;
}
.screen-logo svg {
  width: 23px;
  height: 23px;
}
.screen-brand div > span {
  font-size: 11px;
  color: #759ba0;
  letter-spacing: 2.6px;
}
.screen-brand h1 {
  font-size: 23px;
  font-weight: 500;
  letter-spacing: 1px;
  margin-top: 4px;
  color: #d1e5e6;
}
.screen-header-actions {
  display: flex;
  align-items: center;
  gap: 28px;
}
.sync-state {
  display: flex;
  align-items: center;
  gap: 9px;
  color: #9ab8ae;
  font-size: 13px;
}
.sync-state > i {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #7eb99d;
  box-shadow: 0 0 0 4px #8bbb9b0d;
}
.sync-state small {
  display: block;
  font-size: 11px;
  color: #557b81;
  margin-top: 4px;
}
.sync-state.warning {
  color: #c1a46c;
}
.sync-state.warning > i {
  background: #c1a46c;
}
.control-screen button {
  color: inherit;
}
.exit-button {
  background: #142e38;
  border-color: #34515a;
  color: #9bb7ba;
  padding: 9px 13px;
  font-size: 13px;
}
.exit-button:hover:not(:disabled) {
  border-color: #618b89;
  background: #1a3b43;
}
.screen-warning {
  display: flex;
  align-items: center;
  gap: 9px;
  color: #d1b476;
  border: 1px solid #735f383e;
  background: #71542f16;
  padding: 11px 15px;
  border-radius: 6px;
  font-size: 13px;
}
.screen-stats {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 16px;
}
.screen-stats button {
  display: block;
  text-align: left;
  padding: 18px 22px 12px;
  background: #16303b;
  border: 1px solid #29454e;
  border-radius: 10px;
}
.screen-stats button:hover:not(:disabled) {
  border-color: #517e7b;
  background: #193944;
}
.screen-stats button > span:first-child {
  color: #92b0b4;
  font-size: 13px;
  display: flex;
  align-items: center;
  gap: 8px;
}
.screen-stats button > strong {
  display: block;
  color: var(--stat-color, #d3e3e5);
  font-size: 37px;
  font-weight: 500;
  line-height: 1.3;
  letter-spacing: -0.5px;
  margin: 11px 0 12px;
  font-variant-numeric: tabular-nums;
}
.screen-stats strong > small {
  color: #577780;
  font-size: 12px;
  margin-left: 9px;
  font-weight: 400;
}
.screen-stats .stat-link {
  display: flex;
  align-items: center;
  justify-content: space-between;
  color: #5c828a;
  font-size: 11px;
  border-top: 1px solid #29434b;
  padding-top: 11px;
}
.screen-stats .total-stat {
  background: #1b3e44;
  border-color: #345a5c;
}
.screen-content {
  display: grid;
  grid-template-columns: minmax(240px, 1fr) minmax(350px, 1.65fr) minmax(
      250px,
      1fr
    );
  gap: 20px;
  align-items: stretch;
}
.screen-left,
.screen-right {
  display: grid;
  gap: 20px;
  align-content: start;
}
.screen-panel {
  background: var(--screen-panel);
  border: 1px solid var(--screen-line);
  border-radius: 11px;
  min-width: 0;
  overflow: hidden;
}
.screen-panel-heading {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding: 20px 21px 15px;
}
.screen-panel-heading div > span {
  color: #50757e;
  font-size: 10px;
  letter-spacing: 1.6px;
}
.screen-panel-heading h2 {
  color: #b9d1d2;
  font-size: 14px;
  font-weight: 500;
  margin-top: 5px;
}
.screen-panel-heading > small {
  color: #426975;
  font-size: 11px;
}
.screen-panel-heading > svg {
  color: #49717b;
}
.status-visual {
  display: grid;
  place-items: center;
  padding: 8px 0 10px;
}
.status-ring {
  display: grid;
  place-items: center;
  width: 145px;
  height: 145px;
  border-radius: 50%;
  padding: 10px;
  position: relative;
}
.status-ring::after {
  content: "";
  position: absolute;
  inset: 3px;
  border: 1px solid #19384477;
  border-radius: 50%;
}
.status-ring > div {
  position: relative;
  z-index: 1;
  height: 100%;
  width: 100%;
  background: var(--screen-panel);
  border-radius: 50%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  box-shadow: 0 0 0 4px var(--screen-panel);
}
.status-ring strong {
  font-size: 36px;
  font-weight: 500;
  line-height: 1.2;
  font-variant-numeric: tabular-nums;
}
.status-ring span {
  font-size: 11px;
  color: #648993;
  letter-spacing: 1px;
  margin-top: 5px;
}
.status-legend {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  padding: 12px 20px 18px;
  gap: 9px 17px;
}
.status-legend button {
  background: transparent;
  border: 0;
  padding: 0;
  justify-content: space-between;
  border-radius: 0;
  font-size: 11px;
  color: #74969e;
}
.status-legend button:hover:not(:disabled) {
  background: transparent;
  color: #c0dcdd;
}
.status-legend button > span,
.status-legend strong {
  display: flex;
  align-items: center;
  gap: 6px;
}
.status-legend i {
  height: 5px;
  width: 5px;
  border-radius: 1px;
}
.status-legend strong {
  font-weight: 400;
  color: #9fbec0;
  gap: 5px;
}
.status-legend strong > svg {
  color: #3d616d;
}
.weekly-panel .screen-panel-heading {
  padding-bottom: 7px;
}
.screen-week-chart {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  padding: 6px 20px 0;
  gap: 9px;
}
.screen-day {
  text-align: center;
  min-width: 0;
}
.screen-day > span {
  font-size: 11px;
  color: #729ba0;
  font-variant-numeric: tabular-nums;
}
.screen-day > div {
  height: 72px;
  display: flex;
  align-items: flex-end;
  justify-content: center;
  border-bottom: 1px solid #294651;
}
.screen-day i {
  width: 16px;
  background: #417f83;
  border-radius: 2px 2px 0 0;
  max-width: 100%;
}
.screen-day i.zero {
  background: #2a4b55;
}
.screen-day:last-child i:not(.zero) {
  background: #7ab5a3;
}
.screen-day small {
  display: block;
  font-size: 10px;
  color: #4c727e;
  margin-top: 8px;
}
.screen-note {
  padding: 13px 20px 16px;
  color: #416b77;
  font-size: 10px;
}
.queue-panel {
  display: flex;
  flex-direction: column;
}
.screen-text-link {
  padding: 6px 0;
  background: transparent;
  border: 0;
  color: #6e9c9c !important;
  font-size: 12px;
  font-weight: 400;
  white-space: nowrap;
}
.screen-text-link:hover:not(:disabled) {
  background: transparent;
  color: #abd2c9 !important;
}
.queue-summary {
  margin: 3px 21px 5px;
  display: flex;
  align-items: center;
  gap: 11px;
  border: 1px solid #3a53493d;
  border-radius: 7px;
  padding: 15px;
  background: #263e382e;
}
.summary-icon {
  width: 33px;
  height: 36px;
  display: grid;
  place-items: center;
  color: #b0b48b;
  flex-shrink: 0;
}
.queue-summary p {
  color: #9cafa3;
  font-size: 13px;
  flex: 1;
  line-height: 1.7;
}
.queue-summary p small {
  display: block;
  color: #597b74;
  font-size: 10px;
  margin-top: 3px;
}
.queue-summary > strong {
  color: #c3b47d;
  font-size: 27px;
  font-weight: 400;
  text-align: center;
  flex-shrink: 0;
}
.queue-summary > strong small {
  display: block;
  font-size: 10px;
  color: #8c966f;
  margin-top: 2px;
}
.screen-queue {
  padding: 0 21px;
  flex: 1;
}
.queue-item {
  width: 100%;
  display: flex;
  gap: 13px;
  align-items: flex-start;
  text-align: left;
  background: transparent;
  border: 0;
  border-top: 1px solid #29454d;
  border-radius: 0;
  padding: 17px 0;
}
.queue-item:first-child {
  border-top: 0;
}
.queue-item:hover:not(:disabled) {
  background: #1a3640;
  border-color: #29454d;
}
.queue-number {
  margin-top: 1px;
  font-family: Georgia, serif;
  font-size: 13px;
  color: #4d7680;
}
.queue-copy {
  min-width: 0;
  flex: 1;
}
.queue-copy strong {
  display: block;
  font-size: 13px;
  font-weight: 500;
  color: #b0cbca;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.queue-copy > small {
  display: block;
  font-size: 10px;
  color: #557f88;
  margin-top: 5px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.queue-copy > span {
  display: block;
  font-size: 11px;
  color: #76968d;
  margin-top: 8px;
}
.queue-item-action {
  display: grid;
  justify-items: end;
  gap: 10px;
  color: #b0aa7d;
  font-size: 10px;
  flex-shrink: 0;
}
.queue-item-action i {
  display: grid;
  place-items: center;
  width: 24px;
  height: 24px;
  border: 1px solid #385d59;
  color: #74a89b;
  border-radius: 5px;
}
.queue-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-top: 1px solid #28444c;
  gap: 12px;
  padding: 12px 21px;
  margin-top: auto;
}
.queue-footer > span {
  font-size: 10px;
  color: #476e77;
}
.screen-empty {
  min-height: 260px;
  flex: 1;
  display: grid;
  place-content: center;
  justify-items: center;
  padding: 28px;
  text-align: center;
  color: #517e83;
  gap: 10px;
}
.screen-empty h3 {
  font-size: 14px;
  color: #86aaa5;
  font-weight: 400;
}
.screen-empty p {
  font-size: 11px;
  color: #547e83;
  line-height: 1.8;
}
.screen-empty.compact {
  min-height: 180px;
}
.screen-empty.activity-empty {
  min-height: 72px;
  padding: 10px;
}
.entity-summary {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 3px 21px 16px;
}
.entity-summary > strong {
  font-size: 31px;
  font-weight: 400;
  color: #9cbfb3;
  line-height: 1.3;
}
.entity-summary > span {
  font-size: 12px;
  color: #6e9693;
}
.entity-summary small {
  display: block;
  color: #456e77;
  font-size: 10px;
  margin-top: 4px;
}
.entity-list {
  display: grid;
  gap: 16px;
  padding: 2px 21px 24px;
}
.entity-row > div:first-child {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 14px;
}
.entity-row span {
  display: flex;
  align-items: center;
  gap: 10px;
  color: #83a29e;
  font-size: 11px;
  min-width: 0;
}
.entity-row span > span {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.entity-row i {
  font-style: normal;
  font-family: Georgia, serif;
  color: #456f78;
  font-size: 12px;
}
.entity-row strong {
  font-size: 12px;
  color: #7da99b;
  font-weight: 400;
}
.entity-track {
  height: 4px;
  border-radius: 2px;
  background: #1d3d47;
  margin: 8px 0 0 24px;
}
.entity-track > i {
  display: block;
  height: 100%;
  border-radius: 2px;
  background: #417b79;
}
.entry-panel {
  padding: 23px;
  background: #17343c;
  border-color: #2a4e54;
  position: relative;
}
.entry-panel::after {
  content: "";
  position: absolute;
  height: 135px;
  width: 135px;
  border: 1px solid #34585b77;
  border-radius: 50%;
  right: -70px;
  bottom: 20px;
  pointer-events: none;
  box-shadow:
    0 0 0 20px #2c525433,
    0 0 0 40px #2c525417;
}
.entry-overline {
  font-size: 10px;
  letter-spacing: 1.7px;
  color: #507a7c;
}
.entry-panel h2 {
  font-size: 21px;
  line-height: 1.6;
  color: #a9c7be;
  font-weight: 400;
  letter-spacing: 1px;
  margin-top: 10px;
}
.entry-panel p {
  font-size: 11px;
  color: #618b87;
  line-height: 1.9;
  margin-top: 12px;
}
.entry-panel button {
  position: relative;
  z-index: 1;
  background: #284e4e;
  border-color: #3c6863;
  width: 100%;
  justify-content: space-between;
  color: #b5d7c9;
  font-size: 12px;
  padding: 10px 12px;
  margin-top: 20px;
}
.entry-panel button:hover:not(:disabled) {
  background: #315f5c;
  border-color: #568879;
}
.activity-panel .screen-panel-heading {
  padding-bottom: 10px;
}
.activity-list {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  padding: 0 21px 17px;
}
.activity-item {
  background: transparent;
  border: 0;
  border-left: 1px solid #29454e;
  border-radius: 0;
  text-align: left;
  justify-content: flex-start;
  padding: 6px 16px;
  gap: 9px;
  min-width: 0;
}
.activity-item:first-child {
  border-left: 0;
  padding-left: 0;
}
.activity-item:hover:not(:disabled) {
  background: #1a3640;
  border-color: #29454e;
}
.activity-dot {
  width: 5px;
  height: 5px;
  background: #8497a5;
  border-radius: 50%;
  flex-shrink: 0;
}
.activity-dot.review {
  background: #d3ad6a;
}
.activity-dot.active {
  background: #62b8c3;
}
.activity-dot.completed {
  background: #71bea0;
}
.activity-item > div {
  min-width: 0;
  flex: 1;
}
.activity-item strong {
  display: block;
  color: #86a9a7;
  font-size: 11px;
  font-weight: 400;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.activity-item div > span {
  display: flex;
  gap: 5px;
  color: #486e78;
  font-size: 10px;
  margin-top: 7px;
  white-space: nowrap;
}
.activity-item i {
  font-style: normal;
  color: #3c6570;
}
.activity-item > svg {
  color: #3d6b74;
}
.screen-footer {
  display: flex;
  justify-content: space-between;
  font-size: 10px;
  letter-spacing: 0.6px;
  color: #3a626e;
  padding: 2px 0;
  gap: 12px;
}
.control-screen button:focus-visible {
  outline: 2px solid #b9d4ac;
  outline-offset: 4px;
}
@media (min-width: 1800px) {
  .control-screen {
    padding: 34px 45px 24px;
    gap: 25px;
  }
  .screen-content {
    gap: 25px;
  }
  .screen-panel-heading {
    padding: 24px 26px 18px;
  }
  .screen-panel-heading h2 {
    font-size: 17px;
  }
  .queue-item {
    padding: 23px 0;
  }
  .queue-copy strong {
    font-size: 13px;
  }
  .queue-copy > span {
    font-size: 13px;
  }
  .queue-copy > small {
    font-size: 12px;
  }
  .queue-item-action {
    font-size: 12px;
  }
  .status-ring {
    width: 170px;
    height: 170px;
  }
  .status-legend {
    padding: 20px 26px 25px;
    gap: 15px;
  }
  .status-legend button {
    font-size: 13px;
  }
  .entity-row span {
    font-size: 13px;
  }
  .entity-list {
    gap: 22px;
  }
  .entry-panel {
    padding: 30px;
  }
  .entry-panel h2 {
    font-size: 24px;
  }
  .activity-item strong {
    font-size: 13px;
  }
}
@media (max-width: 1200px) {
  .control-screen {
    padding: 24px;
  }
  .screen-stats {
    gap: 12px;
  }
  .screen-stats button {
    padding: 16px;
  }
  .screen-content {
    grid-template-columns: minmax(225px, 1fr) minmax(330px, 1.6fr);
  }
  .screen-right {
    grid-column: 1 / -1;
    grid-template-columns: 1.6fr 1fr;
  }
  .entity-list {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .entry-panel h2 br {
    display: none;
  }
  .entry-panel {
    padding: 20px 24px;
  }
  .entry-panel h2 {
    font-size: 19px;
  }
  .entry-panel p {
    margin-top: 5px;
  }
  .entry-panel button {
    margin-top: 13px;
  }
  .activity-list {
    grid-template-columns: repeat(3, minmax(0, 1fr));
    row-gap: 14px;
  }
  .activity-item:nth-child(4) {
    border-left: 0;
    padding-left: 0;
  }
}
@media (max-width: 760px) {
  .control-screen {
    padding: 18px;
    gap: 16px;
  }
  .screen-header {
    flex-wrap: wrap;
    padding-bottom: 17px;
    gap: 18px;
  }
  .screen-header-actions {
    flex: 1;
    justify-content: space-between;
    gap: 15px;
  }
  .screen-brand h1 {
    font-size: 20px;
  }
  .screen-stats {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 10px;
  }
  .screen-stats button {
    padding: 14px;
  }
  .screen-stats .fee-stat {
    grid-column: 1 / -1;
    display: grid;
    grid-template-columns: 1fr auto;
    align-items: center;
  }
  .screen-stats .fee-stat > strong {
    font-size: 26px;
    margin: 0;
  }
  .screen-stats .fee-stat .stat-link {
    display: none;
  }
  .screen-content {
    grid-template-columns: 1fr;
    gap: 16px;
  }
  .screen-left {
    grid-template-columns: 1fr 1fr;
    gap: 16px;
  }
  .screen-right {
    grid-template-columns: 1fr;
    gap: 16px;
  }
  .entity-list {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .status-ring {
    width: 115px;
    height: 115px;
  }
  .status-ring strong {
    font-size: 28px;
  }
  .status-legend {
    grid-template-columns: 1fr;
    gap: 7px;
    padding: 9px 16px 17px;
  }
  .screen-panel-heading {
    padding: 17px;
  }
  .screen-panel-heading h2 {
    font-size: 13px;
  }
  .screen-panel-heading div > span {
    font-size: 7px;
    letter-spacing: 0.8px;
  }
  .screen-week-chart {
    padding: 32px 15px 0;
    gap: 5px;
  }
  .screen-day > div {
    height: 105px;
  }
  .screen-day i {
    width: 12px;
  }
  .screen-note {
    padding: 18px 15px;
  }
  .activity-list {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    padding: 2px 17px 17px;
  }
  .activity-item:nth-child(odd) {
    border-left: 0;
    padding-left: 0;
  }
  .activity-item:nth-child(even) {
    border-left: 1px solid #29454e;
    padding-left: 16px;
  }
  .screen-footer {
    flex-wrap: wrap;
  }
  .screen-empty {
    min-height: 230px;
  }
}
@media (max-width: 420px) {
  .control-screen {
    padding: 14px;
  }
  .screen-logo {
    width: 38px;
    height: 38px;
  }
  .screen-brand h1 {
    font-size: 18px;
  }
  .screen-brand div > span {
    font-size: 10px;
  }
  .sync-state {
    font-size: 11px;
  }
  .sync-state small {
    font-size: 10px;
  }
  .exit-button {
    font-size: 12px;
    padding: 8px;
  }
  .screen-stats button > span:first-child {
    font-size: 12px;
  }
  .screen-stats button > strong {
    font-size: 31px;
  }
  .screen-stats .stat-link {
    font-size: 10px;
  }
  .screen-left {
    grid-template-columns: 1fr;
  }
  .status-legend {
    grid-template-columns: repeat(2, 1fr);
  }
  .screen-week-chart {
    padding-top: 7px;
  }
  .screen-day > div {
    height: 72px;
  }
  .queue-summary {
    margin: 0 15px 5px;
    padding: 12px 10px;
    gap: 8px;
  }
  .queue-summary p {
    font-size: 12px;
  }
  .queue-summary p small {
    font-size: 10px;
  }
  .summary-icon {
    display: none;
  }
  .screen-queue {
    padding: 0 16px;
  }
  .queue-item {
    gap: 8px;
  }
  .queue-number {
    font-size: 13px;
  }
  .queue-copy strong {
    font-size: 12px;
  }
  .queue-footer {
    padding: 10px 16px;
  }
  .queue-footer > span {
    max-width: 140px;
  }
  .entity-list {
    grid-template-columns: 1fr;
  }
  .activity-list {
    grid-template-columns: 1fr;
    gap: 9px;
  }
  .activity-item:nth-child(n) {
    border-left: 0;
    border-top: 1px solid #29454e;
    padding: 9px 0;
  }
  .activity-item:first-child {
    border-top: 0;
  }
  .activity-item strong {
    font-size: 12px;
  }
  .activity-item div > span {
    font-size: 11px;
  }
}
</style>
