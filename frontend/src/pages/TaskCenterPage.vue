<script setup lang="ts">
import { computed, nextTick, onDeactivated, ref, useId, watch } from "vue";
import {
  ArrowRight,
  Check,
  ChevronLeft,
  ChevronRight,
  CircleAlert,
  ClipboardCheck,
  FileStack,
  Inbox,
  LoaderCircle,
  Plus,
  Search,
  SlidersHorizontal,
  Trash2,
  X,
} from "@lucide/vue";
import { formatDate, taskStatusLabels, type Task } from "../types/contracts";
import {
  billAttention,
  recordCount,
  taskCategory,
  taskNextAction,
  taskTime,
  taskTitle,
  type TaskFilter,
} from "../utils/taskPresentation";
import { api, errorMessage } from "../api/client";

const props = defineProps<{
  tasks: Task[];
  loading: boolean;
  stale: boolean;
  filter: TaskFilter;
  reviewOnly?: boolean;
}>();
const emit = defineEmits<{
  open: [task: Task];
  create: [];
  filter: [filter: TaskFilter];
  deleted: [ids: string[]];
}>();
const query = ref("");
const entity = ref("");
const sort = ref("updated_desc");
const reviewKind = ref("all");
const page = ref(1);
const pageSize = 8;
const selected = ref(new Set<string>());
const deleteDialog = ref<HTMLDialogElement | null>(null);
const deleteDialogId = useId();
const pendingRemoval = ref<Task[]>([]);
const deleting = ref(false);
const deletionErrors = ref<{ id: string; title: string; message: string }[]>([]);
const operationNotice = ref("");
const selectedTasks = computed(() => props.tasks.filter((task) => selected.value.has(task.id)));
const tabs: { id: TaskFilter; label: string }[] = [
  { id: "all", label: "全部账单" },
  { id: "review", label: "待我处理" },
  { id: "active", label: "处理中" },
  { id: "completed", label: "已完成" },
  { id: "attention", label: "需关注" },
];
const inputStatuses = new Set([
  "waiting_input",
  "awaiting_input",
  "needs_input",
  "interrupted",
]);
const reviews = computed(() =>
  props.tasks.filter((task) => taskCategory(task) === "review"),
);
const baseTasks = computed(() =>
  props.reviewOnly ? reviews.value : props.tasks,
);
const entities = computed(() =>
  Array.from(
    new Set(
      baseTasks.value
        .map((task) => task.accounting_entity)
        .filter((value): value is string => Boolean(value)),
    ),
  ).sort((a, b) => a.localeCompare(b, "zh-CN")),
);
const counts = computed(() =>
  Object.fromEntries(
    tabs.map((tab) => [
      tab.id,
      tab.id === "all"
        ? props.tasks.length
        : props.tasks.filter((task) => taskCategory(task) === tab.id).length,
    ]),
  ),
);
const inputCount = computed(
  () => reviews.value.filter((task) => inputStatuses.has(task.status)).length,
);
const filtered = computed(() => {
  const keyword = query.value.trim().toLocaleLowerCase();
  const result = baseTasks.value.filter((task) => {
    if (
      !props.reviewOnly &&
      props.filter !== "all" &&
      taskCategory(task) !== props.filter
    )
      return false;
    if (props.reviewOnly && reviewKind.value !== "all") {
      if (reviewKind.value === "input" && !inputStatuses.has(task.status))
        return false;
      if (reviewKind.value === "confirm" && inputStatuses.has(task.status))
        return false;
    }
    if (
      entity.value === "__missing"
        ? Boolean(task.accounting_entity)
        : entity.value && task.accounting_entity !== entity.value
    )
      return false;
    return (
      !keyword ||
      [
        taskTitle(task),
        task.id,
        task.accounting_entity,
        ...(task.bill?.references || []),
        ...(task.bill?.parties || []),
      ]
        .join(" ")
        .toLocaleLowerCase()
        .includes(keyword)
    );
  });
  return result.sort((a, b) => {
    if (sort.value === "title")
      return taskTitle(a).localeCompare(taskTitle(b), "zh-CN");
    const direction = sort.value === "updated_asc" ? 1 : -1;
    return (
      direction *
      ((Date.parse(taskTime(a)) || 0) - (Date.parse(taskTime(b)) || 0))
    );
  });
});
const pages = computed(() =>
  Math.max(1, Math.ceil(filtered.value.length / pageSize)),
);
const currentPage = computed(() => Math.min(page.value, pages.value));
const visible = computed(() =>
  filtered.value.slice(
    (currentPage.value - 1) * pageSize,
    currentPage.value * pageSize,
  ),
);
const pageSelected = computed(() => visible.value.length > 0 && visible.value.every((task) => selected.value.has(task.id)));
const pagePartSelected = computed(() => !pageSelected.value && visible.value.some((task) => selected.value.has(task.id)));
const allFilteredSelected = computed(() => filtered.value.length > 0 && filtered.value.every((task) => selected.value.has(task.id)));
function togglePage() {
  const remove = pageSelected.value;
  visible.value.forEach((task) => remove ? selected.value.delete(task.id) : selected.value.add(task.id));
}
function toggleTask(id: string) {
  if (selected.value.has(id)) selected.value.delete(id);
  else selected.value.add(id);
}
function selectFiltered() {
  filtered.value.forEach((task) => selected.value.add(task.id));
}
async function askDelete(targets: Task[]) {
  pendingRemoval.value = [...targets];
  deletionErrors.value = [];
  operationNotice.value = "";
  await nextTick();
  deleteDialog.value?.showModal();
}
function closeDelete() {
  if (!deleting.value) deleteDialog.value?.close();
}
async function confirmDelete() {
  if (deleting.value || !pendingRemoval.value.length) return;
  deleting.value = true;
  deletionErrors.value = [];
  const removed: string[] = [];
  const failed: Task[] = [];
  const targets = [...pendingRemoval.value];
  try {
    for (let offset = 0; offset < targets.length; offset += 4) {
      const batch = targets.slice(offset, offset + 4);
      const results = await Promise.allSettled(batch.map((task) => api.deleteTask(task.id, task.revision)));
      results.forEach((result, index) => {
        const task = batch[index]!;
        if (result.status === "fulfilled") {
          removed.push(task.id);
          selected.value.delete(task.id);
        } else {
          failed.push(task);
          deletionErrors.value.push({ id: task.id, title: taskTitle(task), message: errorMessage(result.reason) });
        }
      });
    }
    if (removed.length) {
      emit("deleted", removed);
      operationNotice.value = `已删除 ${removed.length} 项账单`;
    }
    pendingRemoval.value = failed;
    if (!failed.length) deleteDialog.value?.close();
  } finally {
    deleting.value = false;
  }
}
watch(() => props.tasks.map((task) => task.id), (ids) => {
  const available = new Set(ids);
  selected.value = new Set([...selected.value].filter((id) => available.has(id)));
});
onDeactivated(() => deleteDialog.value?.close());
const hasFilters = computed(() =>
  Boolean(
    query.value ||
      entity.value ||
      (props.reviewOnly ? reviewKind.value !== "all" : props.filter !== "all"),
  ),
);
watch(
  () => [
    query.value,
    entity.value,
    sort.value,
    reviewKind.value,
    props.filter,
    props.reviewOnly,
  ],
  () => {
    page.value = 1;
    selected.value.clear();
  },
);
function resetFilters() {
  query.value = "";
  entity.value = "";
  reviewKind.value = "all";
  if (!props.reviewOnly) emit("filter", "all");
}
function changePage(delta: number) {
  page.value = Math.max(1, Math.min(pages.value, currentPage.value + delta));
}
</script>

<template>
  <section class="task-center">
    <div v-if="reviewOnly" class="review-intro">
      <div class="intro-icon"><ClipboardCheck :size="25" /></div>
      <div class="intro-copy">
        <span class="section-kicker">待办复核</span>
        <h1>
          {{
            loading
              ? "正在获取待办"
              : stale && !tasks.length
                ? "待办暂时不可用"
                : reviews.length
                  ? `${reviews.length} 项账单，等待您的判断`
                  : "待办已清空"
          }}
        </h1>
        <p>仅需核对提示的低置信度字段，或补充处理所需的必要信息；其他账单自动完成核验。</p>
      </div>
      <div v-if="!loading && (!stale || tasks.length)" class="review-breakdown">
        <span
          ><strong>{{ inputCount }}</strong> 待补充信息</span
        >
        <i />
        <span
          ><strong>{{ reviews.length - inputCount }}</strong> 待费用复核</span
        >
      </div>
    </div>

    <div v-else class="center-intro">
      <div>
        <h1>账单业务中心</h1>
        <p>按账单查看提取结果、置信度与原件，按需修改后提交。</p>
      </div>
      <button class="primary create-task" @click="emit('create')">
        <Plus :size="17" />提交新材料
      </button>
    </div>

    <div class="list-surface">
      <div v-if="!reviewOnly" class="list-tabs" aria-label="按账单状态筛选">
        <button
          v-for="tab in tabs"
          :key="tab.id"
          :class="{ chosen: filter === tab.id }"
          :aria-pressed="filter === tab.id"
          @click="emit('filter', tab.id)"
        >
          {{ tab.label
          }}<span>{{
            loading || (stale && !tasks.length) ? "—" : counts[tab.id]
          }}</span>
        </button>
      </div>
      <div v-else class="list-tabs" aria-label="按待办类型筛选">
        <button
          v-for="tab in [
            { id: 'all', label: '全部待办' },
            { id: 'input', label: '补充信息' },
            { id: 'confirm', label: '费用复核' },
          ]"
          :key="tab.id"
          :class="{ chosen: reviewKind === tab.id }"
          :aria-pressed="reviewKind === tab.id"
          @click="reviewKind = tab.id"
        >
          {{ tab.label }}<Check v-if="reviewKind === tab.id" :size="14" />
        </button>
      </div>
      <div class="list-tools">
        <label class="task-search"
          ><Search :size="17" /><input
            v-model="query"
            type="search"
            aria-label="搜索账单"
            placeholder="搜索账单名称、记账主体或编号" /><button
            v-if="query"
            class="clear-query"
            aria-label="清除搜索"
            @click="query = ''"
          >
            <X :size="14" /></button
        ></label>
        <div class="filter-select">
          <SlidersHorizontal :size="15" /><select
            v-model="entity"
            aria-label="筛选记账主体"
          >
            <option value="">全部记账主体</option>
            <option v-for="name in entities" :key="name" :value="name">
              {{ name }}
            </option>
            <option value="__missing">尚未指定主体</option>
          </select>
        </div>
        <select v-model="sort" class="sort-select" aria-label="账单排序">
          <option value="updated_desc">最近更新优先</option>
          <option value="updated_asc">最早更新优先</option>
          <option value="title">按账单名称</option>
        </select>
      </div>
      <p v-if="stale && tasks.length" class="stale-message" role="status">
        <CircleAlert
          :size="15"
        />连接暂时中断，以下保留最近一次同步的账单；操作前请重新连接。
      </p>
      <div v-if="!loading && filtered.length" class="selection-toolbar" aria-label="批量管理账单">
        <label class="selection-label">
          <input type="checkbox" :checked="pageSelected" :indeterminate="pagePartSelected"
            :disabled="stale || deleting" aria-label="全选当前页账单" @change="togglePage" />
          全选当前页
        </label>
        <button class="selection-link" :disabled="stale || deleting || allFilteredSelected" @click="selectFiltered">
          全选{{ hasFilters ? '筛选结果' : '全部' }}（{{ filtered.length }} 项）
        </button>
        <span class="selection-count" aria-live="polite">已选 {{ selectedTasks.length }} 项</span>
        <button v-if="selectedTasks.length" class="selection-link" :disabled="deleting" @click="selected.clear()">取消选择</button>
        <button class="delete-selected" :disabled="stale || deleting || !selectedTasks.length" @click="askDelete(selectedTasks)">
          <Trash2 :size="15" />删除所选
        </button>
      </div>
      <p v-if="operationNotice" class="operation-notice" role="status"><Check :size="15" />{{ operationNotice }}</p>

      <div v-if="loading" class="list-empty" role="status">
        <LoaderCircle class="loading-icon" :size="28" />
        <h3>正在读取账单</h3>
        <p>即将显示最新的处理进度。</p>
      </div>
      <div v-else-if="stale && !tasks.length" class="list-empty unavailable">
        <CircleAlert :size="30" />
        <h3>暂时无法读取账单</h3>
        <p>请使用页面顶部的重新连接，恢复后继续处理。</p>
      </div>
      <div v-else-if="!filtered.length" class="list-empty">
        <Inbox v-if="hasFilters" :size="34" /><ClipboardCheck
          v-else-if="reviewOnly"
          :size="34"
        /><FileStack v-else :size="34" />
        <h3>
          {{
            hasFilters
              ? "没有匹配的账单"
              : reviewOnly
                ? "暂时没有需要您处理的账单"
                : "从第一份材料开始"
          }}
        </h3>
        <p>
          {{
            hasFilters
              ? "试试其他关键词，或清除筛选条件。"
              : reviewOnly
                ? "低置信度复核和必要补充请求会出现在这里。"
                : "上传邮件、PDF、图片、Excel 或 Word，智能助手将协助提取与核对。"
          }}
        </p>
        <button v-if="hasFilters" @click="resetFilters">清除筛选</button
        ><button
          v-else-if="!reviewOnly"
          class="primary"
          @click="emit('create')"
        >
          <Plus :size="16" />提交材料
        </button>
      </div>
      <template v-else>
        <div class="task-table-wrap">
          <table class="task-table">
            <thead>
              <tr>
                <th>账单 / 单号 / 记账主体</th>
                <th>当前状态</th>
                <th>费用与交易方</th>
                <th>需要您处理</th>
                <th>最近更新</th>
                <th><span class="sr-only">操作</span></th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="task in visible"
                :key="task.id"
                :data-task-id="task.id"
                :class="{ 'row-selected': selected.has(task.id) }"
              >
                <td class="task-name-cell">
                  <div class="task-identity">
                    <input class="row-checkbox" type="checkbox" :checked="selected.has(task.id)"
                      :disabled="stale || deleting" :aria-label="`选择账单：${taskTitle(task)}`" @change="toggleTask(task.id)" />
                    <span :class="['document-mark', taskCategory(task)]"
                      ><FileStack :size="19"
                    /></span>
                    <div>
                      <button
                        class="task-title"
                        :title="taskTitle(task)"
                        @click="emit('open', task)"
                      >
                        {{ taskTitle(task) }}</button
                      ><span class="task-entity">{{
                        task.accounting_entity || "尚未指定记账主体"
                      }}</span
                      ><span class="task-reference"
                        >{{ task.bill?.references.join(" / ") || "单号待提取" }}
                        ·
                        {{
                          task.bill?.material_count ??
                          task.asset_ids?.length ??
                          0
                        }}
                        份参考材料</span
                      >
                    </div>
                  </div>
                </td>
                <td data-label="当前状态">
                  <span :class="['task-status', taskCategory(task)]"
                    ><i />{{
                      taskStatusLabels[task.status] || task.status
                    }}</span
                  >
                </td>
                <td data-label="已提取费用" class="count-cell">
                  <strong>{{ recordCount(task) }}</strong
                  ><span> 条</span>
                  <small class="bill-parties">{{
                    task.bill?.parties.join(" → ") || "交易方待提取"
                  }}</small>
                  <small
                    v-for="(item, index) in task.bill?.amounts.slice(0, 2)"
                    :key="index"
                    class="bill-amount"
                    >{{ item.currency || "币种待确认" }}
                    {{
                      item.amount == null
                        ? "金额待确认"
                        : item.amount.toLocaleString("zh-CN", {
                            maximumFractionDigits: 6,
                          })
                    }}</small
                  >
                </td>
                <td data-label="需要您处理" class="bill-attention">
                  <span
                    :class="{ 'issue-count': taskCategory(task) === 'review' }"
                    >{{ billAttention(task) }}</span
                  >
                </td>
                <td data-label="最近更新" class="updated-cell">
                  {{ formatDate(taskTime(task)) }}
                </td>
                <td class="action-cell">
                  <div class="row-actions">
                  <button
                    :class="[
                      'open-task',
                      { 'review-action': taskCategory(task) === 'review' },
                    ]"
                    :aria-label="`${taskNextAction(task)}：${taskTitle(task)}`"
                    @click="emit('open', task)"
                  >
                    {{ taskNextAction(task) }}<ArrowRight :size="15" />
                  </button>
                  <button class="delete-task" :disabled="stale || deleting" :aria-label="`删除账单：${taskTitle(task)}`"
                    title="删除账单" @click="askDelete([task])"><Trash2 :size="16" /></button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div class="list-pagination">
          <span
            >共 {{ filtered.length }} 项<span v-if="hasFilters">匹配账单</span
            ><span v-if="stale"> · 最近同步数据</span></span
          >
          <div class="page-controls">
            <button
              class="page-arrow"
              :disabled="currentPage <= 1"
              aria-label="上一页账单"
              @click="changePage(-1)"
            >
              <ChevronLeft :size="17" /></button
            ><span aria-live="polite">{{ currentPage }} / {{ pages }}</span
            ><button
              class="page-arrow"
              :disabled="currentPage >= pages"
              aria-label="下一页账单"
              @click="changePage(1)"
            >
              <ChevronRight :size="17" />
            </button>
          </div>
          <span class="page-size">每页 {{ pageSize }} 项</span>
        </div>
      </template>
    </div>
    <p class="center-footnote">
      每行是一份提交的账单；邮件正文及其附件共同参考，费用明细和原件在账单内查看。
    </p>
    <Teleport to="body">
      <dialog ref="deleteDialog" class="delete-bills-dialog" :aria-labelledby="`${deleteDialogId}-title`"
        :aria-describedby="`${deleteDialogId}-description`" @cancel="deleting && $event.preventDefault()">
        <div class="delete-dialog-heading">
          <div class="delete-dialog-icon"><Trash2 :size="22" /></div>
          <button class="ghost" aria-label="关闭删除确认" :disabled="deleting" @click="closeDelete"><X :size="18" /></button>
        </div>
        <h2 :id="`${deleteDialogId}-title`">删除这 {{ pendingRemoval.length }} 项账单？</h2>
        <p :id="`${deleteDialogId}-description`">删除后，账单将从工作台和待办中移除。原始材料与历史追踪仍会保留。</p>
        <ul class="delete-target-list">
          <li v-for="task in pendingRemoval" :key="task.id"><FileStack :size="16" /><span>{{ taskTitle(task) }}</span></li>
        </ul>
        <div v-if="deletionErrors.length" class="delete-errors" role="alert">
          <p v-if="operationNotice">{{ operationNotice }}，以下账单未删除：</p>
          <p v-for="item in deletionErrors" :key="item.id"><strong>{{ item.title }}</strong><span>{{ item.message }}</span></p>
        </div>
        <p v-if="deleting" class="delete-progress" role="status"><LoaderCircle :size="16" class="loading-icon" />正在删除，请稍候…</p>
        <footer>
          <button autofocus :disabled="deleting" @click="closeDelete">{{ deletionErrors.length ? '关闭' : '取消' }}</button>
          <button class="danger" :disabled="deleting || !pendingRemoval.length" @click="confirmDelete">
            <Trash2 :size="15" />{{ deleting ? '删除中…' : deletionErrors.length ? '重试未删除项' : '确认删除' }}
          </button>
        </footer>
      </dialog>
    </Teleport>
  </section>
</template>

<style scoped>
.selection-toolbar { display:flex; align-items:center; gap:16px; flex-wrap:wrap; padding:13px 24px; border-top:1px solid var(--line); background:#fafcfb; }
.selection-label { display:flex; align-items:center; gap:9px; font-size:12px; color:var(--navy); white-space:nowrap; cursor:pointer; }
.selection-label input, .row-checkbox { width:17px; height:17px; padding:0; margin:0; flex-shrink:0; accent-color:var(--teal); cursor:pointer; }
.selection-link { border:0; padding:6px 0; background:transparent; color:var(--teal); font-size:12px; }
.selection-count { margin-left:auto; color:var(--subtle); font-size:12px; white-space:nowrap; }
.delete-selected { color:#b94038; border-color:#edceca; background:#fff; font-size:12px; padding:8px 12px; }
.operation-notice { display:flex; align-items:center; gap:8px; padding:12px 24px; margin:0; color:#116c51; background:#f4f7fc; font-size:12px; }
.row-actions { display:flex; align-items:center; justify-content:flex-end; gap:7px; }
.delete-task { padding:8px; border:0; color:#8a9691; background:transparent; flex-shrink:0; }
.delete-task:hover:not(:disabled) { color:#b94038; background:#fff0ee; }
.task-table tbody tr.row-selected { background:#edf2fa; }
.task-table tbody tr.row-selected:hover { background:#e5edf9; }
.delete-bills-dialog { width:min(480px,calc(100vw - 32px)); box-sizing:border-box; max-height:85dvh; overflow:auto; border:1px solid #e4e9e5; border-radius:18px; padding:26px; color:var(--ink); box-shadow:0 24px 80px #122d3438; }
.delete-bills-dialog::backdrop { background:#15372d66; backdrop-filter:blur(3px); }
.delete-dialog-heading { display:flex; align-items:center; justify-content:space-between; }
.delete-dialog-icon { display:grid; place-items:center; width:46px; height:46px; border-radius:13px; background:#fff0ed; color:#b94038; }
.delete-bills-dialog h2 { font-size:21px; margin:18px 0 10px; }
.delete-bills-dialog > p { color:var(--muted); line-height:1.8; font-size:13px; }
.delete-target-list { list-style:none; padding:0; max-height:180px; overflow:auto; border:1px solid var(--line); border-radius:9px; margin:18px 0; }
.delete-target-list li { display:flex; align-items:center; gap:9px; padding:10px 12px; font-size:12px; border-bottom:1px solid var(--line); }
.delete-target-list li:last-child { border-bottom:0; }
.delete-target-list svg { flex-shrink:0; color:var(--muted); }
.delete-target-list span { overflow-wrap:anywhere; }
.delete-bills-dialog footer { display:flex; gap:10px; justify-content:flex-end; padding-top:14px; }
.delete-bills-dialog footer button { min-height:40px; }
.delete-errors { border-radius:9px; padding:2px 12px; background:#fff4ef; font-size:12px; color:#a43f33; }
.delete-errors p { margin:10px 0; }
.delete-errors strong,.delete-errors span { display:block; overflow-wrap:anywhere; line-height:1.8; }
.delete-progress { display:flex; align-items:center; gap:8px; }
@media(max-width:650px) {
  .selection-toolbar { gap:9px 12px; padding:12px 16px; }
  .selection-count { margin-left:0; }
  .delete-selected { margin-left:auto; }
  .row-actions .open-task { flex:1; }
  .row-actions .delete-task { min-width:40px; min-height:40px; }
  .delete-bills-dialog { padding:21px; }
}
.bill-parties,
.bill-amount,
.bill-attention small {
  display: block;
  margin-top: 6px;
  font-size: 11px;
  color: var(--muted);
  font-weight: 400;
}
.bill-attention {
  max-width: 270px;
  font-size: 12px;
  line-height: 1.7;
}
.bill-attention .issue-count {
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.task-center {
  --navy: #2d4361;
  --teal: var(--primary);
  --subtle: var(--muted);
}
.center-intro {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 20px;
  margin: 2px 0 18px;
}
.section-kicker {
  color: #6a898c;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.16em;
}
.center-intro h1 {
  margin: 2px 0 6px;
  color: var(--navy);
  font-size: 20px;
  font-weight: 650;
  letter-spacing: -0.05em;
}
.center-intro p,
.intro-copy p {
  margin: 0;
  color: #718086;
  font-size: 13px;
}
.create-task {
  padding: 8px 12px;
  white-space: nowrap;
}
.review-intro {
  display: flex;
  align-items: center;
  gap: 18px;
  margin-bottom: 25px;
  padding: 16px 18px;
  background: #f3f6fa;
  border: 1px solid #e1e7ef;
  border-radius: 7px;
}
.intro-icon {
  display: grid;
  place-items: center;
  width: 38px;
  height: 38px;
  color: #365d99;
  background: #e8eef7;
  border-radius: 7px;
  flex-shrink: 0;
}
.intro-copy h1 {
  margin: 5px 0 7px;
  font-size: 22px;
  color: #2d4361;
  letter-spacing: -0.03em;
}
.review-breakdown {
  display: flex;
  gap: 21px;
  align-items: center;
  margin-left: auto;
  white-space: nowrap;
  color: #5a746d;
  font-size: 12px;
}
.review-breakdown span {
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.review-breakdown strong {
  color: #365d99;
  font-size: 22px;
  font-weight: 600;
  line-height: 1.2;
  font-variant-numeric: tabular-nums;
}
.review-breakdown i {
  height: 36px;
  width: 1px;
  background: #caded6;
}
.list-surface {
  overflow: hidden;
  background: #fff;
  border: 1px solid #e4e8ef;
  border-radius: 7px;
  box-shadow: 0 5px 18px #102e2a03;
}
.list-tabs {
  display: flex;
  gap: 23px;
  padding: 0 24px;
  border-bottom: 1px solid #e8ecf2;
  overflow-x: auto;
}
.list-tabs button {
  padding: 12px 2px 10px;
  border: 0;
  border-bottom: 2px solid transparent;
  border-radius: 0;
  background: none;
  color: #77878a;
  white-space: nowrap;
  font-size: 13px;
  font-weight: 500;
}
.list-tabs button.chosen {
  color: #365d99;
  border-bottom-color: #365d99;
  font-weight: 650;
}
.list-tabs button:hover {
  color: #365d99;
  background: none;
}
.list-tabs button span {
  min-width: 22px;
  padding: 1px 6px;
  background: #f2f4f7;
  border-radius: 5px;
  font-size: 11px;
  color: #7a8986;
}
.list-tabs button.chosen span {
  color: #365d99;
  background: #edf2fa;
}
.list-tools {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
}
.task-search {
  display: flex;
  align-items: center;
  flex: 1;
  max-width: 450px;
  gap: 9px;
  min-width: 170px;
  padding: 0 12px;
  border: 1px solid #e4e8ef;
  border-radius: 8px;
  color: #7a8c8e;
  background: #fcfdfc;
}
.task-search:focus-within {
  border-color: #5c9c91;
  box-shadow: 0 0 0 3px #365d9912;
}
.task-search input {
  padding: 10px 0;
  border: 0;
  outline: none;
  background: none;
  box-shadow: none;
  font-size: 12px;
  color: #24403f;
  min-width: 0;
}
.task-search input::placeholder {
  color: #96a19f;
}
.clear-query {
  border: 0;
  padding: 2px;
  background: transparent;
  color: #718781;
}
.filter-select {
  display: flex;
  align-items: center;
  gap: 5px;
  margin-left: auto;
  max-width: 230px;
  color: #7f8c88;
  padding: 0 10px;
  border: 1px solid #e4e8ef;
  border-radius: 8px;
}
.filter-select select {
  border: 0;
  box-shadow: none;
  font-size: 12px;
  padding: 10px 0;
  min-width: 118px;
  color: #687b77;
  background: transparent;
  text-overflow: ellipsis;
}
.sort-select {
  width: auto;
  color: #687b77;
  padding: 10px 9px;
  border-color: #e4e8ef;
  font-size: 12px;
}
.stale-message {
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 11px 24px;
  margin: 0;
  color: #9a6d20;
  background: #fff9ec;
  font-size: 12px;
  border-top: 1px solid #f1e9d8;
}
.task-table-wrap {
  overflow-x: auto;
}
.task-table {
  width: 100%;
  min-width: 900px;
  table-layout: fixed;
  border-collapse: collapse;
  text-align: left;
}
.task-table th:nth-child(1) {
  width: 25%;
}
.task-table th:nth-child(2) {
  width: 12%;
}
.task-table th:nth-child(3) {
  width: 19%;
}
.task-table th:nth-child(4) {
  width: 23%;
}
.task-table th:nth-child(5) {
  width: 9%;
}
.task-table th:nth-child(6) {
  width: 12%;
}
.bill-parties {
  white-space: normal;
  overflow-wrap: anywhere;
}
.bill-attention span {
  white-space: normal;
}
.task-table thead {
  background: #f8f9fb;
}
.task-table th {
  color: #83918c;
  padding: 12px 16px;
  font-size: 11px;
  font-weight: 500;
  border-bottom: 1px solid #e9eeea;
  white-space: nowrap;
}
.task-table th:first-child,
.task-table td:first-child {
  padding-left: 16px;
}
.task-table td {
  padding: 12px 14px;
  border-bottom: 1px solid #edf0ed;
  color: #576273;
  font-size: 12px;
  vertical-align: middle;
}
.task-table tbody tr:hover {
  background: #fbfdfb;
}
.task-table tbody tr:last-child td {
  border-bottom: 0;
}
.task-identity {
  display: flex;
  align-items: center;
  gap: 12px;
}
.document-mark {
  display: grid;
  place-items: center;
  color: #6b8884;
  background: #f1f4f9;
  border: 1px solid #e3e8f0;
  border-radius: 6px;
  width: 30px;
  height: 34px;
  flex-shrink: 0;
}
.document-mark.review {
  color: #b08441;
  background: #fbf3e4;
  border-color: #f2e8d4;
}
.document-mark.active {
  color: #447b93;
  background: #edf5fa;
  border-color: #e0edf3;
}
.document-mark.attention {
  color: #987679;
  background: #f7f0ef;
  border-color: #eee4e2;
}
.task-identity > div {
  min-width: 0;
}
.task-title {
  display: block;
  max-width: 330px;
  padding: 0;
  border: 0;
  border-radius: 3px;
  background: none;
  color: #3c4a5e;
  font-size: 13px;
  font-weight: 600;
  text-align: left;
  text-overflow: ellipsis;
  overflow: hidden;
  white-space: nowrap;
}
.task-title:hover {
  background: none !important;
  color: var(--teal);
  text-decoration: underline;
}
.task-entity {
  display: block;
  max-width: 330px;
  margin-top: 4px;
  color: #809088;
  font-size: 11px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.task-reference {
  display: block;
  color: #a0aaa5;
  font-size: 10px;
  margin-top: 2px;
  letter-spacing: 0.02em;
}
.task-status {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 8px;
  border-radius: 6px;
  color: #a87826;
  background: #fff6e6;
  font-size: 11px;
  white-space: nowrap;
}
.task-status i {
  width: 5px;
  height: 5px;
  border-radius: 100%;
  background: currentColor;
}
.task-status.active {
  color: #437c9d;
  background: #edf5fc;
}
.task-status.completed {
  color: #2c8268;
  background: #eaf5ee;
}
.task-status.attention {
  color: #a56d60;
  background: #faf0ec;
}
.count-cell {
  white-space: nowrap;
}
.count-cell strong {
  color: #45566e;
  font-size: 15px;
  font-weight: 550;
  font-variant-numeric: tabular-nums;
}
.count-cell > span {
  font-size: 10px;
  color: #99a69f;
}
.issue-count {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  color: #ac7c31;
  white-space: nowrap;
  font-size: 11px;
}
.neutral-count {
  color: #a0aba5;
  font-size: 11px;
  white-space: nowrap;
}
.updated-cell {
  color: #8c9a92 !important;
  white-space: nowrap;
  font-size: 11px !important;
  font-variant-numeric: tabular-nums;
}
.action-cell {
  text-align: right;
}
.open-task {
  padding: 7px 10px;
  color: #526f99;
  border: 1px solid #dce4f0;
  background: #fff;
  font-size: 11px;
  white-space: nowrap;
}
.open-task.review-action {
  color: #fff;
  background: var(--primary);
  border-color: var(--primary);
}
.open-task.review-action:hover {
  background: var(--primary-hover);
  border-color: var(--primary-hover);
}
.list-pagination {
  padding: 16px 24px;
  border-top: 1px solid #edf0ed;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 15px;
  color: #8b9b93;
  font-size: 11px;
}
.page-controls {
  display: flex;
  align-items: center;
  gap: 16px;
  color: #61776c;
  font-variant-numeric: tabular-nums;
}
.page-arrow {
  padding: 5px;
  width: 29px;
  height: 28px;
  border-color: #e1e9e4;
  border-radius: 5px;
  color: #618174;
}
.list-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-direction: column;
  text-align: center;
  gap: 13px;
  padding: 77px 25px 82px;
  min-height: 300px;
  color: #9cb0a8;
}
.list-empty > svg {
  width: 34px;
  height: 34px;
}
.list-empty h3 {
  color: #526e61;
  font-size: 17px;
  font-weight: 550;
  margin: 0;
}
.list-empty p {
  margin: 0;
  max-width: 460px;
  line-height: 1.8;
  color: #9ba79f;
  font-size: 12px;
}
.list-empty button {
  margin-top: 8px;
}
.unavailable {
  color: #ad8e57;
}
.center-footnote {
  margin: 20px 0 0;
  color: #98a59c;
  text-align: center;
  font-size: 11px;
}
.task-center button:focus-visible,
.task-center select:focus-visible {
  outline: 2px solid #365d99;
  outline-offset: 3px;
}
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}
@media (max-width: 1300px) {
  .task-title,
  .task-entity {
    max-width: 235px;
  }
  .list-tools {
    flex-wrap: wrap;
  }
  .task-table td {
    padding-left: 12px;
    padding-right: 12px;
  }
  .review-intro {
    padding: 22px;
  }
  .review-breakdown {
    gap: 12px;
  }
}
@media (max-width: 900px) {
  .center-intro h1 {
    font-size: 20px;
  }
  .review-intro {
    flex-wrap: wrap;
  }
  .review-breakdown {
    margin-left: 76px;
  }
  .task-search {
    flex-basis: 100%;
    max-width: none;
  }
  .filter-select {
    margin-left: 0;
    flex: 1;
    max-width: none;
  }
  .filter-select select {
    width: 100%;
  }
  .list-tabs {
    gap: 17px;
    padding: 0 18px;
  }
  .task-title,
  .task-entity {
    max-width: 240px;
  }
}
@media (max-width: 650px) {
  .task-table {
    min-width: 0;
    table-layout: auto;
  }
  .center-intro {
    flex-direction: column;
    align-items: flex-start;
    gap: 17px;
    margin-bottom: 20px;
  }
  .center-intro h1 {
    font-size: 18px;
  }
  .center-intro p {
    font-size: 12px;
  }
  .create-task {
    width: 100%;
  }
  .list-tools {
    padding: 16px;
    gap: 10px;
  }
  .review-intro {
    padding: 20px 17px;
    gap: 12px;
  }
  .intro-icon {
    width: 42px;
    height: 46px;
    border-radius: 11px;
  }
  .intro-copy {
    flex: 1;
  }
  .intro-copy h1 {
    font-size: 18px;
  }
  .intro-copy p {
    line-height: 1.8;
    font-size: 11px;
  }
  .review-breakdown {
    margin-left: 54px;
  }
  .review-breakdown span {
    flex-direction: row;
    align-items: baseline;
    gap: 9px;
  }
  .review-breakdown strong {
    font-size: 22px;
  }
  .review-breakdown i {
    height: 22px;
  }
  .task-table,
  .task-table tbody {
    display: block;
  }
  .task-table thead {
    display: none;
  }
  .task-table tr {
    display: grid;
    grid-template-columns: 1fr 1fr;
    padding: 20px 17px;
    gap: 16px 12px;
    border-top: 1px solid #e9eeea;
  }
  .task-table td,
  .task-table th:first-child,
  .task-table td:first-child {
    padding: 0;
    border: 0;
  }
  .task-table td::before {
    content: attr(data-label);
    display: block;
    font-size: 10px;
    color: #9ba99f;
    margin-bottom: 6px;
  }
  .task-table td.task-name-cell::before,
  .task-table td.action-cell::before {
    display: none;
  }
  .task-name-cell {
    grid-column: 1 / -1;
  }
  .task-title,
  .task-entity {
    max-width: calc(100vw - 125px);
  }
  .task-table td.action-cell {
    grid-column: 1 / -1;
    padding-top: 1px;
  }
  .open-task {
    width: 100%;
    padding: 10px;
  }
  .list-pagination {
    padding: 15px 17px;
  }
  .page-size {
    display: none;
  }
  .stale-message {
    padding: 11px 16px;
    align-items: flex-start;
    line-height: 1.8;
  }
  .center-footnote {
    padding: 0 10px;
    line-height: 1.8;
  }
}
</style>
