<script setup lang="ts">
import { computed, ref } from "vue";
import { ArrowRight, ArrowUpRight, CalendarDays, ChartArea, ChartColumn, ChevronDown, FileText, Search, X, SlidersHorizontal } from "@lucide/vue";
import type { EChartsCoreOption } from "echarts/core";
import AnalyticsChart from "../components/AnalyticsChart.vue";
import { formatDate, taskStatusLabels, type Task } from "../types/contracts";
import { taskCategory, taskTime, taskTitle, type TaskFilter } from "../utils/taskPresentation";
import { dashboardAnalytics, dashboardStates, localDay } from "../utils/dashboardAnalytics";

const props = defineProps<{ tasks: Task[]; loading: boolean; stale: boolean; updatedAt: string; motionActive?: boolean }>();
const emit = defineEmits<{ create: []; open: [task: Task]; filter: [filter: TaskFilter]; screen: []; exit: []; manage: [] }>();
const range = ref("7");
const kind = ref<"area" | "bar">("area");
const breakdown = ref<"entities" | "status">("entities");
const activeStatus = ref<TaskFilter>("all");
const query = ref("");
const dayFilter = ref("");
const selectedId = ref("");
let zoom = { start: 0, end: 100 };
const unavailable = computed(() => props.loading || (props.stale && !props.updatedAt));
const data = computed(() => dashboardAnalytics(props.tasks, range.value === "all" ? null : Number(range.value), new Date(props.updatedAt || Date.now())));
const selected = computed(() => rows.value.find(task => task.id === selectedId.value));
const rows = computed(() => data.value.tasks.filter(task =>
  (activeStatus.value === "all" || taskCategory(task) === activeStatus.value) &&
  (!dayFilter.value || localDay(new Date(task.created_at)) === dayFilter.value) &&
  (!query.value.trim() || [taskTitle(task), task.accounting_entity, ...(task.bill?.references || []), ...(task.bill?.parties || [])].join(" ").toLocaleLowerCase().includes(query.value.trim().toLocaleLowerCase()))
).sort((a, b) => Date.parse(taskTime(b)) - Date.parse(taskTime(a))));
const visibleRows = computed(() => rows.value.slice(0, 5));
const summary = computed(() => [
  { id: "all" as const, label: "全部", color: "#253345", count: data.value.tasks.length },
  ...dashboardStates.map(state => ({ ...state, count: data.value.counts[state.id] })),
]);
const chartFont = 'Aptos, "Microsoft YaHei", sans-serif';
const common = computed<EChartsCoreOption>(() => ({
  animation: !!props.motionActive, animationDuration: 500, animationDurationUpdate: 250,
  textStyle: { fontFamily: chartFont, fontSize: 11, color: "#6c7480" },
  tooltip: { trigger: "axis", renderMode: "richText", backgroundColor: "#fff", borderColor: "#e1e4ea", borderWidth: 1, padding: [12, 14],
    textStyle: { fontFamily: chartFont, fontSize: 11, color: "#293344" }, extraCssText: "box-shadow:0 6px 24px #24344918;border-radius:6px", confine: true,
    axisPointer: { type: "line", lineStyle: { color: "#bbc6d5", type: "dashed" } } },
}));
const mainOption = computed<EChartsCoreOption>(() => {
  const days = data.value.daily;
  const maximum = Math.max(1, ...days.map(day => day.total));
  return { ...common.value,
    grid: { top: 25, left: 38, right: 40, bottom: 77 },
    xAxis: { type: "category", data: days.map(day => day.label), boundaryGap: kind.value === "bar", axisLine: { lineStyle: { color: "#e6e9ee" } }, axisTick: { show: false }, axisLabel: { margin: 13, color: "#78808d", fontSize: 10 } },
    yAxis: { type: "value", minInterval: 1, name: "账单数", nameTextStyle: { fontSize: 10, align: "left", padding: [0, 0, 0, -18] }, splitLine: { lineStyle: { color: "#e9edf2", type: "dashed" } }, axisLabel: { fontSize: 10 } },
    dataZoom: [{ type: "slider", start: zoom.start, end: zoom.end, height: 24, bottom: 13, left: 38, right: 40, borderColor: "#dde3ec", backgroundColor: "#fafbfc", fillerColor: "#365d9912", dataBackground: { lineStyle: { color: "#cad1dc" }, areaStyle: { color: "#dfe3e9" } }, selectedDataBackground: { lineStyle: { color: "#6f87ac" }, areaStyle: { color: "#b7c5da" } }, handleStyle: { color: "#fff", borderColor: "#7b92b5" }, moveHandleSize: 0, textStyle: { fontSize: 10 }, brushSelect: false }],
    series: [ ...dashboardStates.map(state => ({ name: state.label, type: kind.value === "bar" ? "bar" : "line", stack: "current-status", data: days.map(day => day.counts[state.id]), itemStyle: { color: state.color }, lineStyle: { width: 0 }, areaStyle: { opacity: .78 }, symbol: "none", barMaxWidth: 32, emphasis: { focus: "series" } })),
      { name: "总数", type: "line", data: days.map(day => day.total), lineStyle: { width: 1.7, color: "#2d518b" }, itemStyle: { color: "#2d518b" }, symbol: "circle", symbolSize: days.length > 31 ? 3 : 5, label: { show: days.length <= 14, position: "top", fontSize: 11, color: "#354052" },
        markLine: { symbol: "none", silent: true, label: { formatter: "日均 {c}", position: "insideEndTop", color: "#778190", fontSize: 10 }, lineStyle: { color: "#aab4c2", width: 1, type: "dashed" }, data: [{ yAxis: Number((data.value.tasks.length / Math.max(days.length, 1)).toFixed(1)) }] }, z: 5 },
    ], aria: { enabled: false },
    // Retain a useful scale when every cohort is empty.
    ...(maximum === 1 && !data.value.tasks.length ? { yAxis: { type: "value", max: 4, minInterval: 1, splitLine: { lineStyle: { color: "#e9edf2", type: "dashed" } } } } : {}),
  };
});
const distribution = computed(() => breakdown.value === "entities"
  ? data.value.entities.slice(0, 5).map(([name, count]) => ({ name, count }))
  : dashboardStates.map(state => ({ name: state.label, count: data.value.counts[state.id] })));
const entityOption = computed<EChartsCoreOption>(() => ({ ...common.value,
  grid: { top: 8, left: 120, right: 29, bottom: 24 },
  tooltip: { trigger: "item", renderMode: "richText", confine: true, backgroundColor: "#fff", borderColor: "#e1e4ea", textStyle: { color: "#293344", fontSize: 11 } },
  xAxis: { type: "value", minInterval: 1, splitNumber: 3, axisLabel: { fontSize: 10, color: "#89909b" }, splitLine: { lineStyle: { type: "dashed", color: "#edf0f4" } } },
  yAxis: { type: "category", inverse: true, data: distribution.value.map(row => row.name), axisLine: { show: false }, axisTick: { show: false }, axisLabel: { color: "#4e5663", fontSize: 10, width: 105, overflow: "truncate" } },
  series: [ { type: "bar", data: distribution.value.map(row => row.count), barWidth: 2, itemStyle: { color: "#6c87af" }, silent: true },
    { type: "scatter", symbolSize: 7, data: distribution.value.map(row => row.count), itemStyle: { color: "#365d99", opacity: 1 }, label: { show: true, position: "right", color: "#5e6877", fontSize: 10, distance: 7 }, z: 3 } ],
}));
const heatOption = computed<EChartsCoreOption>(() => ({ ...common.value,
  grid: { top: 8, left: 30, right: 6, bottom: 55 },
  tooltip: { renderMode: "richText", position: "top", backgroundColor: "#fff", borderColor: "#dfe4ec", textStyle: { color: "#293344", fontSize: 11 }, confine: true,
    formatter: (value: { value: number[] }) => `${["周一", "周二", "周三", "周四", "周五", "周六", "周日"][value.value[1]!]} ${value.value[0]}:00–${value.value[0]! + 1}:00\n创建 ${value.value[2]} 份账单` },
  xAxis: { type: "category", data: Array.from({ length: 24 }, (_, i) => i), splitArea: { show: false }, axisLine: { show: false }, axisTick: { show: false }, axisLabel: { interval: 3, fontSize: 9, color: "#89909b" } },
  yAxis: { type: "category", inverse: true, data: ["周一", "周二", "周三", "周四", "周五", "周六", "周日"], axisLine: { show: false }, axisTick: { show: false }, axisLabel: { fontSize: 9, color: "#89909b" } },
  visualMap: { min: 0, max: Math.max(1, ...data.value.heat.map(cell => cell[2]!)), calculable: false, orient: "horizontal", left: "center", bottom: 0, itemWidth: 7, itemHeight: 175, text: ["多", "少"], textStyle: { fontSize: 9, color: "#89909b" }, inRange: { color: ["#f1f3f6", "#d2dded", "#8ba6d1", "#365d99"] } },
  series: [{ type: "heatmap", data: data.value.heat, itemStyle: { borderWidth: 2, borderColor: "#fff" }, emphasis: { itemStyle: { borderColor: "#2d518b", borderWidth: 1 } } }],
}));
function selectDay(event: { name: string }) {
  dayFilter.value = data.value.daily.find(day => day.label === event.name)?.date || "";
}
function keepZoom(event: unknown) {
  const value = event as { start?: number; end?: number; batch?: { start: number; end: number }[] };
  const next = value.batch?.[0] || value;
  if (typeof next.start === "number" && typeof next.end === "number") zoom = { start: next.start, end: next.end };
}
function resetRange() { dayFilter.value = ""; zoom = { start: 0, end: 100 }; }
</script>

<template>
  <section class="folio-dashboard" aria-label="账单分析">
    <div class="analysis-heading">
      <div class="analysis-title"><h1>账单分析</h1><span>全部工作空间 <span class="path-divider">/</span> 按创建时间</span></div>
      <div class="analysis-controls"><span class="date-extent"><CalendarDays :size="14" />{{ data.start.replaceAll('-', '/') }} — {{ data.end.replaceAll('-', '/') }}</span><label class="range-select"><select v-model="range" aria-label="账单统计范围" @change="resetRange"><option value="7">近 7 天</option><option value="30">近 30 天</option><option value="all">全部时间</option></select><ChevronDown :size="12" /></label></div>
    </div>
    <div v-if="stale" class="notice warning" role="status">{{ updatedAt ? '同步中断，当前展示上次同步的数据。' : '暂时无法获取账单数据，请检查连接。' }}</div>
    <div class="folio-stats" aria-label="所选时段账单统计">
      <button v-for="item in summary" :key="item.id" :class="{ selected: activeStatus === item.id }" :aria-pressed="activeStatus === item.id" @click="activeStatus = item.id; selectedId = ''"><strong :style="{ color: item.color }">{{ unavailable ? '—' : item.count }}</strong><span>{{ item.label }}</span></button>
    </div>
    <div class="analytics-layout">
      <div class="analytics-primary">
        <section class="analysis-surface volume-panel">
          <div class="chart-heading"><h2>按创建日统计 <span>· 当前状态分组</span></h2><div class="chart-controls"><select v-model="dayFilter" class="chart-day-select" aria-label="筛选创建日期"><option value="">全部日期</option><option v-for="day in data.daily" :key="day.date" :value="day.date">{{ day.label }}</option></select><div class="segmented"><button :class="{ active: kind === 'area' }" :aria-pressed="kind === 'area'" aria-label="面积图" title="面积图" @click="kind = 'area'"><ChartArea :size="14" /></button><button :class="{ active: kind === 'bar' }" :aria-pressed="kind === 'bar'" aria-label="柱状图" title="柱状图" @click="kind = 'bar'"><ChartColumn :size="14" /></button></div></div></div>
          <div v-if="unavailable" class="chart-unavailable">{{ loading ? '正在读取账单数据…' : '等待账单数据' }}</div>
          <AnalyticsChart v-else class="volume-chart" :option="mainOption" label="按创建日分组的账单当前状态；支持悬停、点击日期和拖动底部时间范围" @select="selectDay" @zoom="keepZoom" />
          <div class="status-breakdown"><span>当前状态分布<small>所选时段 · {{ data.tasks.length }} 份</small></span><div class="breakdown-content"><div class="breakdown-track"><span v-for="state in dashboardStates" :key="state.id" :style="{ background: state.color, width: `${data.tasks.length ? data.counts[state.id] / data.tasks.length * 100 : 0}%` }" /></div><div class="breakdown-legend"><button v-for="state in dashboardStates" :key="state.id" @click="activeStatus = state.id"><i :style="{ background: state.color }" /><span>{{ state.label }}<small>{{ data.counts[state.id] }} <span>({{ data.tasks.length ? (data.counts[state.id] / data.tasks.length * 100).toFixed(1) : '0.0' }}%)</span></small></span></button></div></div></div>
          <p v-if="!data.tasks.length && !unavailable" class="zero-note">所选时段暂无账单，您可以切换时间范围或提交新材料。</p>
        </section>
        <section class="analysis-surface recent-panel">
          <div class="table-toolbar"><div class="table-tabs"><button :class="{ active: activeStatus === 'all' }" @click="activeStatus = 'all'">最近更新</button><button :class="{ active: activeStatus === 'review' }" @click="activeStatus = 'review'">待办 <span>{{ data.counts.review }}</span></button></div><label class="table-search"><Search :size="13" /><input v-model="query" aria-label="搜索账单、主体或单据编号" placeholder="搜索账单、主体或单据编号" /><button v-if="query" aria-label="清空搜索" @click="query = ''"><X :size="12" /></button></label></div>
          <div v-if="dayFilter || !['all','review'].includes(activeStatus)" class="table-filter"><SlidersHorizontal :size="12" />{{ dayFilter }} {{ summary.find(item => item.id === activeStatus)?.label }}<button @click="dayFilter = ''; activeStatus = 'all'">清除筛选<X :size="11" /></button></div>
          <div class="recent-table-scroll"><table class="recent-table"><thead><tr><th>账单 / 文档</th><th>记账主体</th><th>状态</th><th>费用条目</th><th>最近更新</th><th><span class="sr-only">打开账单</span></th></tr></thead><tbody><template v-for="task in visibleRows" :key="task.id"><tr :class="{ 'selected-row': selectedId === task.id }" @click="selectedId = selectedId === task.id ? '' : task.id"><td><button class="row-select" :aria-expanded="selectedId === task.id" @click.stop="selectedId = selectedId === task.id ? '' : task.id"><FileText :size="13" /><span :title="taskTitle(task)">{{ taskTitle(task) }}</span></button></td><td><span class="cell-ellipsis" :title="task.accounting_entity || '未提供'">{{ task.accounting_entity || '未提供' }}</span></td><td><span class="table-state"><i :style="{ background: dashboardStates.find(state => state.id === taskCategory(task))?.color }" />{{ taskStatusLabels[task.status] || task.status }}</span></td><td>{{ task.record_count ?? task.records?.length ?? '—' }}<span class="cell-unit"> 条</span></td><td class="date-cell">{{ formatDate(taskTime(task)) }}</td><td><button class="row-open" :aria-label="`打开${taskTitle(task)}`" @click.stop="emit('open', task)"><ArrowRight :size="13" /></button></td></tr><tr v-if="selected?.id === task.id" class="selected-detail"><td colspan="6"><span>账单概览</span><span>单号 <b>{{ task.bill?.references?.join(' / ') || '未提供' }}</b></span><span>主体 <b>{{ task.accounting_entity || '未提供' }}</b></span><button @click="emit('open', task)">查看费用与原文<ArrowUpRight :size="12" /></button></td></tr></template><tr v-if="!visibleRows.length"><td colspan="6" class="table-empty">{{ unavailable ? '等待账单数据' : query || dayFilter || activeStatus !== 'all' ? '没有符合当前条件的账单' : '所选时段暂无账单' }}</td></tr></tbody></table></div>
          <div class="table-footer"><span>显示 {{ visibleRows.length }} / {{ rows.length }} 份账单</span><button @click="emit('filter', activeStatus)">进入业务中心<ArrowRight :size="12" /></button></div>
        </section>
      </div>
      <aside class="analytics-secondary">
        <section class="analysis-surface entity-panel"><div class="side-tabs" role="group" aria-label="分布统计维度"><button :class="{ active: breakdown === 'entities' }" :aria-pressed="breakdown === 'entities'" @click="breakdown = 'entities'">主体</button><button :class="{ active: breakdown === 'status' }" :aria-pressed="breakdown === 'status'" @click="breakdown = 'status'">状态</button></div><div class="side-heading"><h2>{{ breakdown === 'entities' ? '按记账主体分布（TOP 5）' : '按当前状态分布' }}</h2><span>合计 {{ unavailable ? '—' : data.tasks.length }}</span></div><AnalyticsChart v-if="!unavailable && distribution.length" class="entity-chart" :option="entityOption" label="所选时段账单数量分布，按记账主体或当前状态查看" /><div v-else class="side-empty">{{ unavailable ? '等待统计数据' : '暂无分布数据' }}</div></section>
        <section class="analysis-surface heat-panel"><div class="side-heading"><h2>材料创建时段 <span>（小时 × 星期）</span></h2></div><AnalyticsChart v-if="!unavailable" class="heat-chart" :option="heatOption" label="所选时段内按本地时间星期和小时统计的账单创建数量热力图" /><div v-else class="side-empty">等待时段数据</div><p class="heat-caption">按账单创建时间统计 · {{ Intl.DateTimeFormat().resolvedOptions().timeZone }}</p></section>
        <p class="analytics-note">统计当前工作空间内的账单。状态为当前状态，不代表历史每日完成量。<span v-if="data.undated">{{ data.undated }} 份账单缺少有效创建日期，未计入时段统计。</span></p>
      </aside>
    </div>
    <footer class="analysis-footer"><span>每笔费用，都有依据。</span><span>{{ stale ? '上次同步' : '数据更新' }} · {{ updatedAt ? formatDate(updatedAt) : '等待同步' }}</span></footer>
  </section>
</template>

<style scoped>
.folio-dashboard { display: grid; gap: 10px; color: #29313d; font-size: 12px; }
.analysis-heading,.analysis-title,.analysis-controls,.chart-heading,.chart-controls,.table-toolbar,.table-search,.side-heading,.analysis-footer { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.analysis-heading { min-height: 30px; margin-bottom: 0; }
.analysis-title { justify-content: flex-start; gap: 28px; }
.analysis-title h1 { font-size: 18px; line-height: 1.3; font-weight: 650; letter-spacing: -.4px; }
.analysis-title > span { font-size: 11px; color: #808590; }
.path-divider { padding: 0 10px; color: #b6bbc4; }
.analysis-controls { gap: 8px; }
.date-extent { display: flex; align-items: center; gap: 8px; background: white; border: 1px solid #e4e7ec; border-radius: 5px; height: 30px; padding: 0 11px; color: #5b6471; font-size: 11px; font-variant-numeric: tabular-nums; }
.range-select { position: relative; }
.range-select select { appearance: none; width: 96px; padding: 5px 24px 5px 10px; height: 30px; border-radius: 5px; font-size: 11px; }
.range-select svg { position: absolute; right: 8px; top: 9px; pointer-events: none; color: #8a929c; }
.folio-stats { display: grid; grid-template-columns: repeat(5,minmax(0,1fr)); background: #fff; border: 1px solid #e6e8ed; border-radius: 6px; box-shadow: 0 2px 5px #23344b04; padding: 6px 0; }
.folio-stats button { position: relative; border: 0; border-right: 1px solid #eceef2; border-radius: 0; background: transparent; padding: 1px 12px; height: 26px; gap: 8px; }
.folio-stats button:last-child { border-right: 0; }
.folio-stats button strong { font-size: 22px; line-height: 1; font-weight: 600; letter-spacing: -.7px; font-variant-numeric: tabular-nums; }
.folio-stats button > span { font-size: 11px; color: #777f8c; }
.folio-stats button:hover { background: #f5f7fa; }
.folio-stats button.selected::after { content: ''; position: absolute; height: 2px; width: 18px; background: #365d99; bottom: -6px; left: calc(50% - 9px); }
.analytics-layout { display: grid; grid-template-columns: minmax(0, 2.25fr) minmax(285px, 1fr); gap: 10px; align-items: start; }
.analytics-primary { display: grid; gap: 10px; min-width: 0; }
.analysis-surface { background: #fff; border: 1px solid #e7e9ef; border-radius: 7px; box-shadow: 0 3px 10px #29384c04; min-width: 0; }
.chart-heading { padding: 10px 14px 0; }
.chart-heading h2 { font-size: 12px; font-weight: 600; }
.chart-heading h2 span { color: #707986; font-weight: 400; }
.chart-controls { gap: 8px; }
.chart-day-select { width: 83px; height: 25px; padding: 3px 4px; border-radius: 4px; color: #788292; font-size: 10px; }
.segmented { display: flex; border: 1px solid #e2e6ec; border-radius: 4px; padding: 2px; gap: 2px; }
.segmented button { height: 19px; width: 25px; border: 0; border-radius: 3px; padding: 0; color: #8b929c; }
.segmented button.active { background: #edf1f8; color: #365d99; box-shadow: 0 1px 3px #23344b12; }
.volume-chart { height: clamp(250px, 25.5vw, 370px); margin-top: 0; }
.chart-unavailable { height: 331px; display: grid; place-content: center; color: #858e9b; }
.status-breakdown { display: flex; gap: 24px; padding: 9px 14px 12px; border-top: 1px solid #f3f4f6; align-items: start; }
.status-breakdown > span { font-size: 10px; font-weight: 600; white-space: nowrap; }
.status-breakdown > span small { display: block; margin-top: 4px; font-weight: 400; color: #89919c; font-size: 9px; }
.breakdown-content { flex: 1; min-width: 0; }
.breakdown-track { display: flex; height: 5px; border-radius: 3px; background: #eff1f5; overflow: hidden; margin: 1px 0 9px; }
.breakdown-track span { height: 100%; transition: width 250ms; }
.breakdown-legend { display: grid; grid-template-columns: repeat(4,minmax(0,1fr)); gap: 8px; }
.breakdown-legend button { padding: 0; border: 0; background: none; justify-content: flex-start; align-items: flex-start; gap: 5px; text-align: left; font-size: 10px; color: #5d6675; font-weight: 400; }
.breakdown-legend i,.table-state i { width: 5px; height: 5px; border-radius: 50%; margin-top: 4px; flex-shrink: 0; }
.breakdown-legend small { display: block; font-size: 9px; margin-top: 2px; color: #657080; font-variant-numeric: tabular-nums; }
.breakdown-legend small span { color: #8c94a0; }
.zero-note { padding: 0 17px 12px; font-size: 11px; color: #8b929c; }
.table-toolbar { padding: 0 12px 0 16px; border-bottom: 1px solid #e8ebf0; min-height: 36px; }
.table-tabs { display: flex; gap: 20px; height: 36px; }
.table-tabs button { border: 0; background: none; border-radius: 0; border-bottom: 2px solid transparent; font-size: 11px; padding: 0 0 0; color: #7a818d; }
.table-tabs button.active { border-bottom-color: #365d99; color: #303d50; }
.table-tabs span { background: #f0f2f5; font-size: 9px; padding: 0 4px; border-radius: 3px; color: #6f7785; }
.table-search { border: 1px solid #e6e9ee; border-radius: 4px; padding: 0 7px; gap: 5px; color: #9aa1ac; width: 220px; height: 26px; }
.table-search:focus-within { border-color: #7995bf; box-shadow: 0 0 0 2px #365d9910; }
.table-search input { padding: 0; font-size: 10px; height: 23px; border: 0; box-shadow: none; min-width: 0; }
.table-search input:focus-visible { outline: none; }
.table-search button { border: 0; padding: 0; }
.recent-table-scroll { overflow-x: auto; }
.recent-table { border-collapse: collapse; width: 100%; table-layout: fixed; font-size: 11px; text-align: left; }
.recent-table th { font-weight: 500; color: #7c8490; background: #fcfcfd; height: 29px; padding: 0 8px; border-bottom: 1px solid #eff1f5; white-space: nowrap; }
.recent-table th:first-child { width: 31%; padding-left: 16px; }.recent-table th:nth-child(2) { width: 20%; }.recent-table th:nth-child(3) { width: 15%; }.recent-table th:nth-child(4) { width: 10%; }.recent-table th:nth-child(5) { width: 19%; }.recent-table th:last-child { width: 32px; }
.recent-table td { height: clamp(24px, 2.3vw, 33px); padding: 0 8px; color: #535d6b; border-bottom: 1px solid #f1f3f6; font-variant-numeric: tabular-nums; }
.recent-table tr:not(.selected-detail):hover td { background: #f7f9fc; }
.recent-table .selected-row td { background: #eaf0fa !important; }
.row-select { width: 100%; border: 0; border-radius: 0; background: none; padding: 0 0 0 8px; justify-content: flex-start; gap: 7px; color: #4b5768; font-size: 11px; font-weight: 400; min-height: clamp(24px, 2.3vw, 33px); }
.row-select svg { color: #8a97aa; width: 13px; height: 13px; }
.row-select span,.cell-ellipsis { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; display: block; }
.table-state { display: flex; align-items: center; gap: 6px; white-space: nowrap; }
.table-state i { margin-top: 0; }
.cell-unit { color: #9ba2ac; }.date-cell { font-size: 10px; white-space: nowrap; }
.row-open { width: 23px; height: 22px; padding: 0; border: 0; background: none; border-radius: 4px; color: #7b8ba1; }.row-open:hover { background: #365d99 !important; color: #fff; }
.selected-detail td { height: auto; background: #f7f9fc; padding: 13px 16px; }
.selected-detail td > span { display: inline-block; margin-right: 18px; color: #7b8593; font-size: 9px; }.selected-detail b { font-weight: 400; color: #4c596b; margin-left: 6px; }.selected-detail button { border: 0; padding: 0; background: none; font-size: 9px; color: #365d99; }
.table-footer { display: flex; justify-content: space-between; align-items: center; padding: 7px 16px; color: #939ba7; font-size: 9px; }.table-footer button { font-size: 10px; border: 0; padding: 2px 0; background: none; color: #637b9d; }
.table-empty { text-align: center; padding: 30px !important; height: 92px !important; color: #8b929e !important; }
.table-filter { display: flex; align-items: center; gap: 8px; font-size: 10px; padding: 6px 16px; background: #f8fafd; color: #6d7d93; }.table-filter button { background: none; border: 0; font-size: 10px; padding: 0; color: #365d99; }
.analytics-secondary { display: grid; gap: 10px; min-width: 0; }
.side-tabs { display: flex; border-bottom: 1px solid #e8ebf0; padding: 0 12px; gap: 4px; height: 35px; }
.side-tabs button { border: 0; border-radius: 0; border-bottom: 2px solid transparent; padding: 0 18px; font-size: 11px; font-weight: 400; color: #8a919c; }.side-tabs button.active { color: #365d99; border-bottom-color: #365d99; background: #f9fafd; }
.side-heading { padding: 14px 14px 9px; gap: 6px; }.side-heading h2 { font-size: 11px; font-weight: 500; }.side-heading h2 span { font-size: 10px; font-weight: 400; color: #8b929c; }.side-heading > span { font-size: 9px; color: #939ba6; white-space: nowrap; }
.entity-chart { height: clamp(145px, 14.4vw, 208px); }.side-empty { height: 172px; display: grid; place-content: center; color: #98a0ab; font-size: 11px; }
.heat-chart { height: clamp(155px, 16.1vw, 232px); }.heat-caption { color: #929aa6; font-size: 9px; padding: 8px 14px 13px; border-top: 1px solid #f4f5f7; }
.analytics-note { padding: 0 4px; font-size: 10px; color: #969da7; line-height: 1.8; }.analytics-note span { display: block; }
.analysis-footer { font-size: 10px; color: #929aa5; padding: 2px 4px; margin-top: 0; }
@media (min-width: 1550px) { .volume-chart { height: 370px; }.entity-chart { height: 192px; }.heat-chart { height: 242px; } }
@media (max-width: 1050px) { .status-breakdown { gap: 14px; }.recent-table { min-width: 590px; }.analysis-title { gap: 14px; } }
@media (max-width: 800px) { .analysis-title > span { display: none; } .breakdown-legend { grid-template-columns: repeat(2,1fr); } .analytics-layout { grid-template-columns: minmax(0,1fr); }.analytics-secondary { grid-template-columns: 1fr 1fr; }.analytics-note { grid-column: 1/-1; }.volume-chart { height: 300px; }.entity-chart { height: 202px; }.heat-chart { height: 192px; }.date-extent { display: none; } }
@media (max-width: 500px) { .folio-dashboard { gap: 11px; }.analysis-title h1 { font-size: 17px; }.folio-stats { padding: 7px 0; }.folio-stats button { flex-direction: column; gap: 5px; height: 41px; padding: 0 3px; }.folio-stats button strong { font-size: 19px; }.folio-stats button > span { font-size: 9px; }.folio-stats button.selected::after { bottom: -7px; }.chart-heading { padding: 12px 12px 0; }.chart-heading h2 { font-size: 11px; }.chart-heading h2 span { font-size: 10px; }.chart-day-select { width: 64px; font-size: 9px; }.status-breakdown { padding: 10px 12px; gap: 12px; }.status-breakdown > span { font-size: 9px; }.breakdown-legend { gap: 8px; }.table-toolbar { padding-left: 12px; gap: 8px; flex-wrap: wrap; padding-bottom: 7px; }.table-tabs { height: 36px; }.table-search { width: 100%; }.analytics-secondary { grid-template-columns: minmax(0,1fr); }.analysis-footer { flex-wrap: wrap; gap: 4px; }.volume-chart { height: 270px; }.entity-chart { height: 180px; }.heat-chart { height: 215px; } }
</style>
