<script setup lang="ts">
import { computed, defineAsyncComponent, ref, watch } from "vue";
import {
  ArrowUpRight,
  CircleAlert,
  Download,
  File,
  FileCheck,
  FileText,
  LoaderCircle,
  Pause,
  Pencil,
  Play,
  ScanLine,
  Search,
  ShieldCheck as ShieldCheckIcon,
  Sparkles,
  Square,
  Trash2,
} from "@lucide/vue";
import { api, downloadJson, errorMessage } from "../api/client";
import {
  formatDate,
  taskStatusLabels,
  type Asset,
  type Charge,
  type Evidence,
  type Issue,
  type Task,
} from "../types/contracts";
import RevisionDialog from "./RevisionDialog.vue";
import ConfidencePanel from "./ConfidencePanel.vue";
import { useConfidence } from "../composables/useConfidence";
import { formatChargeAmount } from "../utils/amountPresentation";
import {
  taskCategory,
  taskNextAction,
  taskIsProcessing,
} from "../utils/taskPresentation";
const AgentPanel = defineAsyncComponent(() => import("./AgentPanel.vue"));
const MaterialPreviewDrawer = defineAsyncComponent(
  () => import("./MaterialPreviewDrawer.vue"),
);
const props = defineProps<{ task: Task; assets: Asset[] }>();
const emit = defineEmits<{ updated: [task: Task]; refresh: []; improve: [] }>();
const tab = ref("charges"),
  query = ref(""),
  selectedCharge = ref(""),
  busy = ref(""),
  error = ref(""),
  revision = ref<Charge | null>(null),
  editAction = ref<"edit" | "delete" | "split" | "entity">("edit"),
  editOpen = ref(false);
const streamEpoch = ref(0),
  editField = ref("");
const previewTarget = ref<Evidence | null>(null),
  previewChargeId = ref("");
const showAllEvidence = ref(false);
const {
  report: confidenceReport,
  loading: confidenceLoading,
  error: confidenceError,
  byCharge: confidenceByCharge,
  candidates,
  quickConfirm,
  unavailableReason,
  reload: reloadConfidence,
} = useConfidence(() => props.task);
const candidateMode = computed(
  () => !props.task.records?.length && candidates.value.length > 0,
);
const records = computed(() =>
  props.task.records?.length ? props.task.records : candidates.value,
);
const initialRows = computed(() =>
  records.value.length || !taskIsProcessing(props.task)
    ? []
    : (props.task.intake_preview || []).flatMap((source) =>
        source.rows.map((row) => ({ ...row, source: source.name })),
      ),
);
const intakeStatus = computed(() => {
  const labels: Record<string, string> = {
    local_ready: "已读取本地内容，正在核对识别结果",
    uploading: "正在准备材料供识别服务读取",
    requesting: "正在等待识别服务返回，已读内容可先查看",
    cache_hit: "已复用此前识别结果，正在核对当前材料",
    ocr_complete: "识别已返回，正在整理费用和证据",
  };
  return (
    labels[props.task.intake_progress?.stage || ""] ||
    props.task.summary ||
    "正在读取材料"
  );
});
const previewCharge = computed(() =>
  records.value.find((row) => row.charge_id === previewChargeId.value),
);
const currentConfidence = computed(() =>
  current.value
    ? confidenceByCharge.value.get(current.value.charge_id)
    : undefined,
);
const filtered = computed(() =>
  records.value.filter((r) =>
    [
      r.charge_details?.charge_item,
      r.charge_details?.currency,
      r.document_info?.reference_no,
      r.operation,
    ]
      .join(" ")
      .toLowerCase()
      .includes(query.value.toLowerCase()),
  ),
);
// A re-extraction can publish records=[] for one poll before the next save.
// Keep the last non-empty list so the review panel does not unmount and
// remount while the bill is still being processed.
const lastRecords = ref<Charge[]>([]);
watch(
  records,
  (rows) => {
    if (rows.length) lastRecords.value = rows;
  },
  { immediate: true },
);
const current = computed(() => {
  const rows = records.value;
  const picked =
    rows.find((r) => r.charge_id === selectedCharge.value) || rows[0];
  if (picked) return picked;
  if (!taskIsProcessing(props.task)) return undefined;
  return (
    lastRecords.value.find((r) => r.charge_id === selectedCharge.value) ||
    lastRecords.value[0]
  );
});
const taskAssets = computed<Asset[]>(() =>
  props.task.sources?.length
    ? props.task.sources.map((source) => ({
        id: source.source_id,
        name: source.name,
        size: source.size_bytes,
        media_type: source.mime_type,
        parent_id: source.parent_source_id,
        status: source.status,
        text: source.text,
        preview_text: source.preview_text,
        content_url:
          "/api/tasks/" +
          encodeURIComponent(props.task.id) +
          "/sources/" +
          encodeURIComponent(source.source_id) +
          "/content",
      }))
    : props.task.assets ||
      props.assets.filter((a) => props.task.asset_ids?.includes(a.id)),
);
const evidence = computed<Evidence[]>(() => {
  const items =
    current.value?.evidence || current.value?.audit_trail?.evidence || [];
  const seen = new Set<string>();
  return items.filter((item) => {
    const key = JSON.stringify([
      item.source_id || item.asset_id,
      item.page,
      item.anchor,
      item.quote || item.text,
    ]);
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
});
const visibleEvidence = computed(() =>
  showAllEvidence.value ? evidence.value : evidence.value.slice(0, 2),
);
const resultFields = [
  ["document_info", "document_type", "单据类型"],
  ["document_info", "reference_no", "单据编号"],
  ["document_info", "document_date", "单据日期"],
  ["transaction_party", "issuer", "签发方"],
  ["transaction_party", "recipient", "接收方"],
  ["charge_details", "charge_item", "费用项目"],
  ["charge_details", "original_charge_item", "原始费用名称"],
  ["charge_details", "quantity", "数量"],
  ["charge_details", "unit_price", "单价"],
  ["charge_details", "amount", "金额"],
  ["charge_details", "currency", "币种"],
  ["charge_details", "payment_term", "付款方式"],
  ["financial_attributes", "accounting_entity", "记账主体"],
  ["financial_attributes", "posting_type", "收付方向"],
] as const;
function fieldValue(record: Charge, group: string, field: string) {
  const values = record[group] as Record<string, unknown> | undefined;
  const value =
    values?.[field] ??
    (["quantity", "unit_price"].includes(field)
      ? record[field]
      : field === "original_charge_item"
        ? record.raw_charge_item
        : undefined);
  return value == null || value === "" ? "待确认 / 未提供" : String(value);
}
const active = computed(() => taskIsProcessing(props.task));
const entityDisplay = computed(
  () => props.task.accounting_entity || "尚未指定记账主体",
);
const confirmed = computed(
  () =>
    (props.task.approval?.decision === "approve" &&
      props.task.approval.binding?.revision === props.task.revision) ||
    (props.task.auto_review?.decision === "passed" &&
      props.task.auto_review.binding?.revision === props.task.revision),
);
const reviewCompleted = computed(
  () => props.task.review_confirmation?.revision === props.task.revision,
);
// Any settled bill whose review has produced records can be closed with the
// gaps left as null.  Waiting/blocked states are excluded: they still expect a
// concrete answer, not an acknowledgement of what was extracted.
const settledReviewStatuses = new Set([
  "completed_with_gaps",
  "awaiting_review",
  "needs_review",
  "waiting_review",
  "ready_for_review",
  "review_deferred",
]);
const canCompleteReview = computed(
  () =>
    !active.value &&
    !confirmed.value &&
    !reviewCompleted.value &&
    !props.task.confidence_interrupt &&
    !candidateMode.value &&
    !!props.task.records?.length &&
    settledReviewStatuses.has(props.task.status),
);
const canExport = computed(
  () =>
    confirmed.value &&
    !active.value &&
    !props.task.confidence_interrupt &&
    !!props.task.records?.length,
);
const canReview = computed(
  () =>
    !active.value &&
    !props.task.confidence_interrupt &&
    !candidateMode.value &&
    !!props.task.records?.length &&
    [
      "waiting_review",
      "awaiting_review",
      "needs_review",
      "ready_for_review",
      "review_deferred",
    ].includes(props.task.status),
);
const reviewState = computed(() =>
  active.value
    ? "处理中"
    : confirmed.value
      ? props.task.auto_review?.mode === "automatic"
        ? "自动核验完成"
        : "已确认"
      : reviewCompleted.value
        ? "已审核完成"
        : [
              "waiting_input",
              "awaiting_input",
              "needs_input",
              "interrupted",
            ].includes(props.task.status)
          ? "待补充"
          : props.task.status === "paused"
            ? "已暂停"
            : canReview.value
              ? "待确认"
              : props.task.status === "awaiting_review"
                ? "待针对性复核"
                : props.task.status === "completed_with_gaps"
                  ? "已提取"
                  : "处理未完成",
);
const nextAction = computed(() =>
  props.task.status === "awaiting_input"
    ? "请在下方补充所需信息，提交后继续处理材料。"
    : confirmed.value
      ? "当前版本已完成核验，可查看原文、直接修改或导出结果。"
      : reviewCompleted.value
        ? "审核已完成；未提供的字段保持为空，可随时修订补充。"
        : active.value
          ? "正在处理材料，您可以离开页面，稍后回来查看。"
          : quickConfirm.value && canReview.value
            ? "费用依据充分，您可以直接确认当前版本。"
            : taskCategory(props.task) === "review"
              ? "请只核对提示的低置信度字段，可定位原文并直接修改。"
              : props.task.status === "completed_with_gaps"
                ? "提取结果已保存，未提供的信息不要求逐项审批；您可按需查看原文或补全。"
                : taskNextAction(props.task),
);
watch(
  () => props.task.id,
  () => {
    selectedCharge.value = "";
    error.value = "";
    tab.value = "charges";
    previewTarget.value = null;
  },
);
watch(
  () => props.task.revision,
  () => {
    error.value = "";
  },
);
function selectRecord(r: Charge) {
  if (selectedCharge.value !== r.charge_id) showAllEvidence.value = false;
  selectedCharge.value = r.charge_id;
}
const postingGap = computed(() => {
  const record = current.value;
  if (!record || record.financial_attributes?.posting_type) return "";
  const issues = props.task.validation?.issues;
  return (
    [
      ...(record.issues || []),
      ...(Array.isArray(issues) ? (issues as Issue[]) : []),
    ].find(
      (issue) =>
        issue.field?.split(".").at(-1) === "posting_type" &&
        (!issue.charge_id || issue.charge_id === record.charge_id),
    )?.message || ""
  );
});
function sourceStatus(status?: string): string {
  const labels: Record<string, string> = {
    ready: "已解析",
    complete: "已解析",
    completed: "已解析",
    partial: "部分解析",
    waiting_url: "待补充 OCR 链接",
    failed: "解析失败",
    error: "解析失败",
    pending: "等待解析",
    processing: "解析中",
  };
  return status ? labels[status] || status : "尚无解析状态";
}
function edit(
  action: "edit" | "delete" | "split" | "entity",
  record?: Charge,
  field = "",
) {
  if (action !== "entity" && candidateMode.value) return;
  if (action === "edit") {
    // Edit directly in the revision form; the conversation is for questions
    // and confirmations, not for retyping field values.
    editAction.value = action;
    revision.value = record || current.value || null;
    editField.value = field;
    editOpen.value = true;
    return;
  }
  if (props.task.thread_id) {
    void reviewInConversation(action, record || current.value, field);
    return;
  }
  editAction.value = action;
  revision.value = record || current.value || null;
  editField.value = field;
  editOpen.value = true;
}
async function reviewInConversation(
  action: string,
  record?: Charge,
  field = "",
) {
  if (busy.value) return;
  busy.value = "conversation";
  error.value = "";
  try {
    const task = await api.reviewConversation(props.task.id, {
      expected_revision: props.task.revision,
      action,
      charge_id: record?.charge_id,
      field,
    });
    emit("updated", task);
    streamEpoch.value++;
    document
      .getElementById("agent-conversation")
      ?.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (e) {
    error.value = errorMessage(e);
  } finally {
    busy.value = "";
  }
}
function openEvidence(record?: Charge, selected?: Evidence, field?: string) {
  if (record) selectRecord(record);
  const name = field?.split(".").at(-1);
  const references = record?.evidence || record?.audit_trail?.evidence || [];
  const scored = record
    ? confidenceByCharge.value.get(record.charge_id)?.evidence_targets || []
    : [];
  const source =
    selected ||
    scored.find((item) => item.field?.split(".").at(-1) === name) ||
    references.find((item) => item.field?.split(".").at(-1) === name) ||
    scored[0] ||
    references[0] ||
    {};
  const target: Evidence = {
    ...source,
    quote: source.quote || source.text,
    field: name || source.field,
    charge_id: record?.charge_id,
  };
  if (name && record) {
    const value = [
      record.charge_details,
      record.document_info,
      record.transaction_party,
      record.financial_attributes,
      record,
    ]
      .map((group) => group?.[name])
      .find((value) => value != null);
    if (typeof value === "number" || typeof value === "string")
      target.value = String(value);
  }
  previewChargeId.value = record?.charge_id || "";
  previewTarget.value = target;
}
function revisionSaved(task: Task) {
  emit("updated", task);
  editOpen.value = false;
  if (!previewTarget.value) return;
  const changed = task.records?.find(
    (row) => row.charge_id === previewChargeId.value,
  );
  if (!changed) {
    previewTarget.value = null;
    return;
  }
  const field = previewTarget.value.field?.split(".").at(-1);
  if (field) {
    const value = [
      changed.charge_details,
      changed.document_info,
      changed.transaction_party,
      changed.financial_attributes,
      changed,
    ]
      .map((group) => group?.[field])
      .find((value) => value != null);
    previewTarget.value = {
      ...previewTarget.value,
      value: value == null ? undefined : String(value),
    };
  }
}
function scoreLabel(record: Charge) {
  const result = confidenceByCharge.value.get(record.charge_id);
  const value = result?.review_score ?? result?.score;
  return value == null ? "—" : `${Math.round(value)} 分`;
}
async function confirmCurrentVersion() {
  if (!quickConfirm.value || active.value || busy.value || candidateMode.value)
    return;
  busy.value = "approve";
  error.value = "";
  const expectedRevision = props.task.revision;
  try {
    emit(
      "updated",
      await api.approve(props.task.id, {
        expected_revision: expectedRevision,
        decision: "approve",
        reason: `调用方点击确认当前版本 R${expectedRevision} 的全部费用；参考当前证据与规则支持度 ${confidenceReport.value?.score ?? "—"}/100。`,
      }),
    );
  } catch (failure) {
    error.value = errorMessage(failure);
  } finally {
    busy.value = "";
  }
}
async function completeReview() {
  if (!canCompleteReview.value || busy.value) return;
  busy.value = "complete";
  error.value = "";
  try {
    emit(
      "updated",
      await api.completeReview(props.task.id, {
        expected_revision: props.task.revision,
        reason: "调用方完成审核；未提供的字段保持为空",
      }),
    );
  } catch (failure) {
    error.value = errorMessage(failure);
  } finally {
    busy.value = "";
  }
}
async function control(action: string) {
  busy.value = action;
  error.value = "";
  try {
    emit("updated", await api.control(props.task.id, action));
  } catch (e) {
    error.value = errorMessage(e);
  } finally {
    busy.value = "";
  }
}
async function exportResult(draft = false) {
  busy.value = "export";
  error.value = "";
  try {
    downloadJson(
      await api.export(props.task.id, draft),
      `harbor-${props.task.id}-r${props.task.revision}${draft ? "-DRAFT" : ""}.json`,
    );
  } catch (e) {
    error.value = errorMessage(e);
  } finally {
    busy.value = "";
  }
}
</script>
<template>
  <div class="task-workspace">
    <div class="task-banner">
      <div class="task-title">
        <div class="task-icon"><FileCheck /></div>
        <div>
          <div class="flex">
            <h1>{{ task.title || "账单详情" }}</h1>
            <span :class="['badge', task.status]">{{
              taskStatusLabels[task.status] || task.status
            }}</span>
          </div>
          <p>
            <span>{{ entityDisplay }}</span
            ><i />创建于 {{ formatDate(task.created_at) }}<i /><span
              class="mono"
              >版本 {{ task.revision }}</span
            >
          </p>
        </div>
      </div>
      <div class="task-actions" role="group" aria-label="账单操作">
        <button
          v-if="quickConfirm && canReview && !confirmed"
          class="primary"
          :disabled="active || !!busy"
          @click="confirmCurrentVersion"
        >
          <LoaderCircle
            v-if="busy === 'approve'"
            class="loading-icon"
          /><ShieldCheckIcon v-else :size="14" />确认当前版本
        </button>
        <button
          v-else-if="!confirmed && canReview"
          :disabled="active || !!busy || !task.records?.length"
          @click="reviewInConversation('confirm')"
        >
          <ShieldCheckIcon :size="14" />复核与确认
        </button>
        <button
          v-else-if="canCompleteReview"
          class="primary"
          :disabled="!!busy"
          title="审核结束；未提供的字段保持为空，账单进入已完成状态"
          @click="completeReview"
        >
          <ShieldCheckIcon :size="14" />完成审核
        </button>
        <button v-if="active" :disabled="!!busy" @click="control('pause')">
          <Pause :size="14" />暂停</button
        ><button
          v-else-if="
            task.status === 'paused' ||
            (task.feedback &&
              ['failed', 'incomplete'].includes(task.feedback.state))
          "
          :disabled="!!busy"
          @click="control('resume')"
        >
          <Play :size="14" />{{
            task.status === "paused" ? "恢复" : "继续处理"
          }}</button
        ><button
          v-else-if="task.status === 'incomplete'"
          :disabled="!!busy"
          @click="control('restart')"
        >
          <Play :size="14" />重新处理</button
        ><button
          v-if="active || task.status === 'paused'"
          class="icon ghost"
          :disabled="!!busy"
          aria-label="取消任务"
          title="取消任务"
          @click="control('cancel')"
        >
          <Square :size="14" /></button
        ><button
          :class="{ primary: canExport }"
          :disabled="!!busy || !canExport"
          :title="
            canExport
              ? '下载当前版本的正式账单 JSON，服务端会重新校验'
              : '自动核验或针对性复核通过后可导出；现有结果可下载草稿'
          "
          @click="exportResult()"
        >
          <LoaderCircle
            v-if="busy === 'export'"
            class="loading-icon"
          /><Download v-else :size="14" />导出账单
        </button>
        <button
          class="ghost"
          :disabled="active || !!busy"
          @click="emit('improve')"
        >
          <Sparkles :size="14" />总结这次纠错
        </button>
      </div>
    </div>
    <div class="review-overview" aria-label="本次账单概况">
      <div class="review-guidance">
        <ShieldCheckIcon />
        <div>
          <strong>{{ nextAction }}</strong>
        </div>
      </div>
      <div class="review-stat">
        <span>费用条目</span
        ><strong>{{ records.length }}<small>条</small></strong>
      </div>
      <div class="review-stat">
        <span>本次置信度</span
        ><strong :class="confidenceReport?.band"
          >{{
            active
              ? "提取中"
              : confidenceLoading
                ? "…"
                : active || confidenceReport?.score == null
                  ? "—"
                  : Math.round(
                      confidenceReport.review_score ?? confidenceReport.score,
                    )
          }}<small v-if="!active && confidenceReport?.score != null"
            >/ 100</small
          ></strong
        >
      </div>
      <div class="review-stat">
        <span>账单状态</span
        ><strong class="review-state">{{ reviewState }}</strong>
      </div>
    </div>
    <div v-if="error" class="notice error" role="alert">{{ error }}</div>
    <div
      v-if="
        active &&
        task.intake_progress &&
        task.intake_progress.stage !== 'complete'
      "
      class="notice"
      role="status"
    >
      <LoaderCircle :size="16" class="spin" /><span>{{ intakeStatus }}</span>
    </div>
    <div v-if="task.error || task.status === 'error'" class="notice error">
      <CircleAlert /><span>{{
        task.error ||
        task.summary ||
        "智能体本次执行未完成，请查看工具与校验信息。"
      }}</span>
    </div>
    <div v-if="task.status === 'recovery_required'" class="notice warning">
      <CircleAlert /><span>{{
        task.summary ||
        "历史执行状态需要恢复，材料与业务修订仍已保留。请核对材料与当前结果后重新处理。"
      }}</span>
    </div>
    <div
      v-else-if="
        task.feedback &&
        !['completed', 'completed_with_gaps'].includes(task.feedback.state)
      "
      class="notice warning"
      role="status"
    >
      <CircleAlert /><span>{{
        task.summary || "您的修改已保存，智能体将根据当前版本继续核对。"
      }}</span>
    </div>
    <div class="bill-review-layout" :class="{ 'has-assistant': !!task.thread_id }">
    <AgentPanel
      id="agent-conversation"
      v-if="task.thread_id"
      :key="task.thread_id"
      :connection-epoch="streamEpoch"
      :task="task"
      @updated="emit('updated', $event)"
      @refresh="emit('refresh')"
      @rejoin="streamEpoch++"
      @locate="
        (chargeId, field) =>
          openEvidence(
            records.find((row) => row.charge_id === chargeId),
            undefined,
            field,
          )
      "
      @edit="
        (chargeId, field) =>
          edit(
            'edit',
            records.find((row) => row.charge_id === chargeId),
            field,
          )
      "
    />
    <div class="card results-card">
      <div class="results-heading">
        <div class="section-heading">
          <FileCheck :size="18" />
          <h2>费用清单</h2>
        </div>
        <div class="tabs">
          <button
            :class="{ active: tab === 'charges' }"
            @click="tab = 'charges'"
          >
            账单核对 <span>{{ records.length }}</span></button
          ><button
            :class="{ active: tab === 'fields' }"
            @click="tab = 'fields'"
          >
            更多信息
          </button>
        </div>
      </div>
      <template v-if="tab === 'charges'"
        ><div class="result-toolbar">
          <div class="search">
            <Search /><input
              v-model="query"
              placeholder="搜索费用名称、币种或单号"
              aria-label="搜索费用"
            />
          </div>
          <span class="small muted"
            >{{ records.length }} 条费用 · {{ taskAssets.length }} 份材料</span
          >
        </div>
        <p class="review-focus">
          {{
            active
              ? "费用仍在提取中，完成后再确认。"
              : canReview
                ? "核对 AR/AP、单据编号、费用名称、金额、币种和付款方式，无误后确认即可。"
                : confirmed
                  ? "当前账单已确认，可按需查看原件。"
                  : task.status === 'completed_with_gaps' || reviewCompleted
                    ? "费用已保存；未提供的信息保持为空，可按需核对或修订。"
                  : "处理尚未完成，以下信息仅供查看。"
          }}
        </p>
        <div v-if="candidateMode" class="candidate-notice">
          当前展示提取候选，尚未形成正式费用；可先查看支持度与原件证据。
        </div>
        <div v-if="unavailableReason" class="candidate-notice">
          {{ unavailableReason }}
        </div>
        <div v-if="initialRows.length" class="table-scroll">
          <p class="candidate-notice">
            已读取以下费用内容，正在等待识别核对完成。
          </p>
          <table class="charges-table" aria-label="正在核对的费用内容">
            <thead>
              <tr>
                <th>费用名称</th>
                <th>金额</th>
                <th>币种</th>
                <th>来源</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(row, index) in initialRows" :key="index">
                <td>{{ row.description }}</td>
                <td>{{ row.raw_amount ?? row.amount ?? "—" }}</td>
                <td>{{ row.currency || "未提供" }}</td>
                <td>
                  {{ row.source
                  }}<span v-if="row.page"> · 第{{ row.page }}页</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-else-if="!records.length" class="empty">
          <ScanLine />
          <h3>{{ active ? "正在从材料中提取费用" : "暂无费用记录" }}</h3>
          <p>
            {{
              active
                ? "处理计划可在上方“处理进度”中查看，费用生成后会自动显示。"
                : "请查看上方补充请求或参考材料。"
            }}
          </p>
        </div>
        <div v-else-if="!filtered.length" class="empty">
          <Search />
          <h3>没有匹配的费用</h3>
          <p>调整搜索条件查看其他记录。</p>
        </div>
        <div v-else class="table-scroll">
          <table class="charges-table">
            <thead>
              <tr>
                <th>AR/AP</th>
                <th>单据编号</th>
                <th>费用名称</th>
                <th>金额</th>
                <th>币种</th>
                <th>付款方式</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="record in filtered"
                :key="record.charge_id"
                :class="{
                  selected: current?.charge_id === record.charge_id,
                }"
                tabindex="0"
                @click="selectRecord(record)"
                @keydown.enter="selectRecord(record)"
              >
                <td>
                  <span
                    :class="[
                      'posting',
                      record.financial_attributes?.posting_type,
                    ]"
                    >{{
                      record.financial_attributes?.posting_type === "AR"
                        ? "AR 应收"
                        : record.financial_attributes?.posting_type === "AP"
                          ? "AP 应付"
                          : "待确认"
                    }}</span
                  >
                </td>
                <td>
                  <button
                    class="ghost"
                    title="查看单据编号原文"
                    @click.stop="
                      openEvidence(record, undefined, 'reference_no')
                    "
                  >
                    {{ record.document_info?.reference_no || "未提供" }}
                  </button>
                </td>
                <td>
                  <button
                    class="ghost"
                    title="查看费用名称原文"
                    @click.stop="openEvidence(record, undefined, 'charge_item')"
                  >
                    <strong>{{
                      record.charge_details?.charge_item || "待确认"
                    }}</strong>
                  </button>
                  <button :class="['score-badge', confidenceByCharge.get(record.charge_id)?.band]" title="查看置信度与原文" @click.stop="selectRecord(record)">{{ active ? '提取中' : confidenceLoading ? '计算中' : scoreLabel(record) }}</button>
                </td>
                <td>
                  <button
                    class="amount amount-link"
                    title="定位金额原文"
                    @click.stop="openEvidence(record, undefined, 'amount')"
                  >
                    {{ formatChargeAmount(record) }}<ArrowUpRight :size="11" />
                  </button>
                </td>
                <td>
                  <button
                    class="ghost"
                    title="查看币种原文"
                    @click.stop="openEvidence(record, undefined, 'currency')"
                  >
                    {{ record.charge_details?.currency || "待确认" }}
                  </button>
                </td>
                <td>
                  <button
                    class="ghost"
                    title="查看付款方式原文"
                    @click.stop="
                      openEvidence(record, undefined, 'payment_term')
                    "
                  >
                    {{ record.charge_details?.payment_term || "未提供" }}
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div class="table-foot">
          <span v-if="postingGap && !active" class="posting-gap"
            >AR/AP 尚未确定：{{ postingGap }}。
            请在下方所选费用的“修订费用”中补充。
          </span>
          <span
            ><ShieldCheckIcon />{{
              active ? "请等待提取完成" : "有疑问可查看原件或修改"
            }}</span
          >
          <div class="flex">
            <span v-if="confirmed" class="confirmed-label"
              ><ShieldCheckIcon :size="14" />当前版本已确认</span
            ><span v-else-if="reviewCompleted" class="confirmed-label"
              ><ShieldCheckIcon :size="14" />已审核完成</span
            >
          </div>
        </div>
      </template>
      <div v-else class="card-body">
        <div class="json-caption">
          <FileText :size="15" /><span
            >当前版本 {{ task.revision }} ·
            每行一项费用，金额可直接定位原件。</span
          >
        </div>
        <div v-if="records.length" class="record-fields-list">
          <section
            v-for="record in records"
            :key="record.charge_id"
            class="record-fields-card"
          >
            <div class="record-fields-heading">
              <h4>{{ record.charge_details?.charge_item || "费用信息" }}</h4>
              <button class="ghost" @click="selectRecord(record)">
                {{
                  current?.charge_id === record.charge_id
                    ? "已选中"
                    : "选择此费用"
                }}
              </button>
            </div>
            <dl class="record-fields">
              <div v-for="field in resultFields" :key="field[1]">
                <dt>{{ field[2] }}</dt>
                <dd>
                  <button
                    v-if="
                      ['amount', 'currency', 'reference_no'].includes(field[1])
                    "
                    class="ghost"
                    @click="openEvidence(record, undefined, field[1])"
                  >
                    {{ fieldValue(record, field[0], field[1])
                    }}<ArrowUpRight :size="12" /></button
                  ><span v-else>{{
                    fieldValue(record, field[0], field[1])
                  }}</span>
                </dd>
              </div>
            </dl>
          </section>
        </div>
        <div v-else class="empty">材料处理完成后，业务字段会在这里展示。</div>
      </div>
      <details
        v-if="taskAssets.length"
        class="bundle-materials"
        aria-label="本次账单参考材料"
      >
        <summary>
          <FileText :size="14" />参考材料 {{ taskAssets.length
          }}<span>正文与全部附件共同核对 · 点击查看原件</span>
        </summary>
        <div class="material-chips">
          <button
            v-for="asset in taskAssets"
            :key="asset.id"
            class="ghost"
            @click="
              previewChargeId = '';
              previewTarget = { source_id: asset.id };
            "
          >
            <FileText :size="14" /><span
              >{{ asset.name
              }}<small
                >{{ asset.parent_id ? "附件 / 嵌入材料" : "主材料 / 正文" }} ·
                {{ sourceStatus(asset.status) }}</small
              ></span
            ><ArrowUpRight :size="12" />
          </button>
        </div>
      </details>
      <section
        v-if="current"
        class="review-evidence"
        aria-label="费用原文与置信度"
      >
        <div class="evidence-body">
          <div class="evidence-toolbar">
            <div class="evidence-charge">
              <span class="review-section-title"
                ><ShieldCheckIcon :size="15" />原文复核</span
              >
              <h3>{{ current.charge_details?.charge_item || "未命名费用" }}</h3>
              <p>{{ current.document_info?.reference_no || "单号未确定" }}</p>
              <small>点击上方费用行切换</small>
            </div>
            <div class="fee-actions" role="group" aria-label="所选费用操作">
              <button
                :disabled="active || candidateMode"
                @click="edit('edit', current)"
              >
                <Pencil :size="13" />修订费用</button
              ><button
                class="ghost"
                :disabled="active || candidateMode"
                @click="edit('split', current)"
              >
                拆分</button
              ><button
                class="danger"
                aria-label="删除费用"
                :disabled="active || candidateMode"
                @click="edit('delete', current)"
              >
                <Trash2 :size="13" />删除
              </button>
            </div>
          </div>
          <div class="review-evidence-grid">
            <ConfidencePanel
              :value="currentConfidence"
              :loading="confidenceLoading"
              :error="confidenceError"
              :unavailable-reason="unavailableReason"
              @retry="reloadConfidence"
              @locate="openEvidence(current, undefined, $event)"
            />
            <details :key="current.charge_id" class="review-quotes">
              <summary>
                <FileText :size="14" /><span>提取原文与原件</span
                ><small>{{
                  evidence.length
                    ? `${evidence.length} 处原文 · 按需展开`
                    : "暂无原文"
                }}</small>
              </summary>
              <div class="quote-list">
                <template v-if="evidence.length"
                  ><div
                    v-for="(item, index) in visibleEvidence"
                    :key="index"
                    class="evidence-quote"
                  >
                    <div class="evidence-source">
                      <File :size="12" /><span>{{
                        item.filename ||
                        taskAssets.find(
                          (a) => a.id === (item.asset_id || item.source_id),
                        )?.name ||
                        "来源材料"
                      }}</span
                      ><b v-if="item.page != null">P{{ item.page }}</b>
                    </div>
                    <blockquote>
                      {{ item.quote || item.text || "此条证据未返回原文片段" }}
                    </blockquote>
                    <p v-if="item.anchor">{{ item.anchor }}</p>
                    <button class="ghost" @click="openEvidence(current, item)">
                      查看原件<ArrowUpRight :size="12" />
                    </button></div
                ></template>
                <div v-else class="notice warning">
                  此费用尚未关联可展示的原文证据。
                </div>
                <button
                  v-if="evidence.length > 2"
                  class="ghost evidence-more"
                  @click="showAllEvidence = !showAllEvidence"
                >
                  {{
                    showAllEvidence
                      ? "收起其他原文"
                      : `查看其余 ${evidence.length - 2} 处原文`
                  }}
                </button>
              </div>
            </details>
          </div>
          <details
            v-if="current.audit_trail?.ai_reasoning"
            class="reasoning-details"
          >
            <summary>查看核对依据</summary>
            <div v-if="current.audit_trail?.ai_reasoning" class="reasoning">
              <h4>核对依据</h4>
              <ul v-if="Array.isArray(current.audit_trail.ai_reasoning)">
                <li
                  v-for="(reason, i) in current.audit_trail.ai_reasoning"
                  :key="i"
                >
                  {{ reason }}
                </li>
              </ul>
              <p v-else>{{ current.audit_trail.ai_reasoning }}</p>
            </div>
          </details>
          <details v-if="current.changes">
            <summary>查看修改差异</summary>
            <pre class="code-block">{{
              JSON.stringify(current.changes, null, 2)
            }}</pre>
          </details>
        </div>
      </section>
    </div>
    </div>
    <MaterialPreviewDrawer
      v-if="previewTarget"
      :task="task"
      :charge="previewCharge"
      :target="previewTarget"
      :editable="!!previewCharge && !active && !candidateMode"
      @close="previewTarget = null"
      @edit="edit('edit', previewCharge, $event)"
    />
    <RevisionDialog
      v-if="editOpen"
      :task="task"
      :charge="revision"
      :action="editAction"
      :focus-field="editField"
      @close="editOpen = false"
      @saved="revisionSaved"
    />
  </div>
</template>
<style scoped>
.bill-review-layout { display: grid; gap: 20px; min-width: 0; align-items: start; }
.bill-review-layout > * { min-width: 0; }
@media (min-width: 1160px) {
  .bill-review-layout.has-assistant { grid-template-columns: minmax(0, 1fr) clamp(380px, 31vw, 560px); }
  .bill-review-layout.has-assistant > .agent-panel { grid-column: 2; grid-row: 1; }
  .bill-review-layout.has-assistant > .results-card { grid-column: 1; grid-row: 1; }
  .bill-review-layout.has-assistant .charges-table:not(.full-fields) { min-width: 640px; }
  .bill-review-layout.has-assistant .charges-table th,
  .bill-review-layout.has-assistant .charges-table td { padding-left: 12px; padding-right: 12px; }
}
.results-card {
  margin-top: 0;
}
.review-evidence {
  border-top: 1px solid var(--line);
}
.review-evidence-grid {
  display: grid;
  gap: 10px;
  min-width: 0;
}
.review-evidence :deep(.confidence-panel) {
  margin: 0;
}
.review-quotes {
  min-width: 0;
}
.review-quotes > summary {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 7px;
  padding: 10px 0;
  font-size: 12px;
  color: var(--primary);
  cursor: pointer;
}
.review-quotes > summary::after {
  content: "展开";
  margin-left: auto;
  font-size: 11px;
}
.review-quotes[open] > summary::after {
  content: "收起";
}
.review-quotes > summary small {
  color: var(--muted);
  font-size: 11px;
  font-weight: 400;
}
.quote-list {
  max-height: 320px;
  overflow: auto;
  overscroll-behavior: contain;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  padding: 2px 2px 8px;
}
.quote-list .notice,
.quote-list .evidence-more {
  grid-column: 1 / -1;
}
.review-quotes .evidence-more {
  justify-self: start;
}
.review-quotes .evidence-quote {
  margin: 0 0 14px;
}
.review-quotes blockquote {
  overflow-wrap: anywhere;
}
.reasoning-details {
  margin: 4px 0 0;
  font-size: 11px;
  color: var(--muted);
}
.reasoning-details > summary {
  padding: 7px 0;
  cursor: pointer;
}
@media (max-width: 800px) {
  .quote-list {
    grid-template-columns: 1fr;
  }
  .bundle-materials {
    padding: 14px 16px;
  }
}

.bundle-materials {
  margin: 0;
  padding: 16px 22px;
  border-top: 1px solid var(--line);
}
.bundle-materials summary {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  cursor: pointer;
  color: var(--ink);
  font-weight: 600;
}
.bundle-materials summary span {
  color: var(--muted);
  font-weight: 400;
  font-size: 11px;
}
.bundle-materials p {
  color: var(--muted);
  font-size: 11px;
  margin: 6px 0 14px;
}
.material-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}
.material-chips button {
  border: 1px solid var(--line);
  max-width: 100%;
  justify-content: flex-start;
}
.material-chips span {
  overflow-wrap: anywhere;
  text-align: left;
}
.material-chips small {
  display: block;
  color: var(--muted);
  font-size: 10px;
  margin-top: 4px;
}
.record-fields-list {
  display: grid;
  gap: 16px;
}
.record-fields-card {
  border: 1px solid var(--line);
  border-radius: 10px;
  overflow: hidden;
  min-width: 0;
}
.record-fields-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  background: var(--surface-soft, #f5f8f6);
}
.record-fields-heading h4 {
  margin: 0;
  font-size: 14px;
  overflow-wrap: anywhere;
}
.record-fields {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 260px), 1fr));
  margin: 0;
}
.record-fields > div {
  display: grid;
  grid-template-columns: 90px minmax(0, 1fr);
  gap: 12px;
  padding: 12px 16px;
  border-top: 1px solid var(--line);
  align-items: start;
}
.record-fields dt {
  color: var(--muted);
  font-size: 12px;
}
.record-fields dd {
  margin: 0;
  font-size: 13px;
  overflow-wrap: anywhere;
  min-width: 0;
}
.record-fields button {
  white-space: normal;
  text-align: left;
  padding: 0;
  min-height: 24px;
}
.review-overview {
  display: flex;
  gap: 28px;
  align-items: center;
  padding: 20px 22px;
  background: #f1f4f9;
  border: 1px solid #e0e8e1;
  border-radius: 12px;
}
.review-guidance {
  display: flex;
  gap: 11px;
  align-items: flex-start;
  flex: 1;
}
.review-guidance > svg {
  color: var(--primary);
  margin-top: 2px;
}
.review-guidance strong {
  font-size: 13px;
  font-weight: 600;
}
.review-guidance p {
  font-size: 11px;
  color: var(--muted);
  margin-top: 6px;
}
.review-stat {
  padding-left: 24px;
  border-left: 1px solid #d6e2da;
  white-space: nowrap;
}
.review-stat > span {
  color: var(--muted);
  font-size: 11px;
  display: block;
}
.review-stat > strong,
.review-stat > button {
  font-size: 18px;
  line-height: 1.2;
  display: flex;
  gap: 5px;
  align-items: baseline;
  margin-top: 7px;
  font-weight: 500;
  font-variant-numeric: tabular-nums;
  padding: 0;
}
.review-stat small {
  font-size: 11px;
  color: var(--muted);
  font-weight: 400;
}
.review-stat .high {
  color: var(--green);
}
.review-stat .medium {
  color: var(--amber);
}
.review-stat .low {
  color: var(--red);
}
.task-title h1 {
  font-size: 18px;
  letter-spacing: -0.5px;
  overflow-wrap: anywhere;
  line-height: 1.5;
  font-weight: 600;
}
.task-title > div {
  min-width: 0;
}
.task-title .flex {
  flex-wrap: wrap;
}
.task-icon {
  color: var(--primary);
  border-color: #d4e5d9;
}
.audit-artifacts {
  margin-top: 0;
  overflow: hidden;
}
.audit-artifacts > summary {
  padding: 18px 22px;
  cursor: pointer;
  color: var(--muted);
  font-size: 12px;
}
.audit-artifacts > summary span {
  margin-left: 7px;
  color: #8fa29a;
  font-size: 11px;
}
@media (max-width: 1100px) {
  .review-overview {
    flex-wrap: wrap;
    gap: 18px;
  }
  .review-guidance {
    flex-basis: 100%;
  }
  .review-stat {
    padding: 0 22px 0 0;
    border-left: 0;
    border-right: 1px solid #d6e2da;
  }
  .review-stat:last-child {
    border: 0;
  }
  .task-banner {
    flex-wrap: wrap;
  }
}
@media (max-width: 600px) {
  .review-overview {
    padding: 18px;
    gap: 15px;
  }
  .review-stat {
    padding-right: 13px;
  }
  .review-stat > strong,
  .review-stat > button {
    font-size: 18px;
  }
  .task-title h1 {
    font-size: 17px;
  }
  .task-icon {
    display: none;
  }
}
.candidate-notice {
  padding: 10px 22px;
  color: var(--amber);
  background: var(--amber-soft);
  font-size: 11px;
  line-height: 1.7;
  border-top: 1px solid var(--line);
}
.charges-table .amount-link {
  border: 0;
  padding: 0;
  min-height: 0;
  background: transparent;
  color: var(--primary);
  font-weight: 600;
  font-size: 13px;
  gap: 4px;
  white-space: nowrap;
}
.score-badge {
  padding: 4px 7px;
  font-size: 10px;
  white-space: nowrap;
  background: #f3f2f6;
  color: var(--muted);
  border: 0;
  min-height: 0;
}
.score-badge.high {
  background: var(--green-soft);
  color: var(--green);
}
.score-badge.medium {
  background: var(--amber-soft);
  color: var(--amber);
}
.score-badge.low {
  background: var(--red-soft);
  color: var(--red);
}
.confirmed-label {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  color: var(--green);
  font-size: 11px;
  white-space: nowrap;
}
.source-locate {
  margin: 0 0 14px;
  font-size: 11px;
  width: 100%;
}
.table-foot .quick-confirm {
  white-space: nowrap;
  color: #fff;
  background: var(--primary);
  padding: 6px 8px;
}
.table-foot > .flex {
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
}
.evidence-body :deep(.confidence-panel) {
  margin: 0;
}
.validation-report {
  padding: 16px 22px;
}
.validation-report summary {
  font-size: 12px;
  cursor: pointer;
  color: var(--muted);
}
.validation-report pre {
  margin-top: 12px;
  max-height: 400px;
  overflow: auto;
}
.source-notice {
  font-size: 11px;
  margin: 12px 0;
}
.task-workspace {
  display: grid;
  gap: 16px;
}
.task-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 18px 21px;
}
.task-title {
  display: flex;
  align-items: center;
  gap: 13px;
  min-width: 0;
}
.task-title h2 {
  font-size: 14px;
  max-width: 330px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.task-icon {
  width: 38px;
  height: 42px;
  display: grid;
  place-items: center;
  background: var(--primary-soft);
  color: var(--primary);
  border: 1px solid #d4e5d9;
  border-radius: 9px;
}
.task-icon svg {
  width: 20px;
}
.task-title p {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--muted);
  font-size: 11px;
  margin-top: 6px;
  flex-wrap: wrap;
}
.task-title p i {
  width: 2px;
  height: 2px;
  background: var(--line);
  border-radius: 50%;
}
.task-actions {
  display: flex;
  gap: 7px;
  flex-shrink: 0;
}
.task-actions button {
  font-size: 12px;
  padding: 7px 11px;
}
.results-card {
  overflow: hidden;
}
.tabs {
  gap: 24px;
}
.tabs button {
  font-size: 12px;
}
.tabs span {
  font-size: 11px;
  margin-left: 2px;
}
.issue-count {
  color: var(--amber);
  background: var(--amber-soft);
  border-radius: 3px;
  padding: 1px 4px;
}
.result-toolbar {
  padding: 13px 18px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid #f2eff7;
}
.result-toolbar > .small {
  font-size: 11px;
}
.search {
  position: relative;
}
.search svg {
  position: absolute;
  left: 9px;
  top: 8px;
  width: 13px;
  color: var(--muted);
}
.search input {
  font-size: 12px;
  padding: 7px 8px 7px 29px;
  border-color: #efebf5;
  background: #fcfbfe;
  width: 240px;
}
.table-scroll {
  overflow: auto;
}
.charges-table {
  width: 100%;
  border-collapse: collapse;
  text-align: left;
}
.charges-table th {
  font-size: 11px;
  color: var(--muted);
  background: #fcfbfe;
  font-weight: 400;
  padding: 11px 14px;
}
.charges-table td {
  font-size: 12px;
  padding: 16px 14px;
  border-bottom: 1px solid #f1edf5;
  color: #6f647d;
  cursor: pointer;
}
.charges-table tr.selected td {
  background: #faf8ff;
}
.charges-table tr:hover td {
  background: #f9f7fe;
}
.charges-table th:first-child,
.charges-table td:first-child {
  padding-left: 21px;
}
.charges-table:not(.full-fields) {
  min-width: 780px;
}
.charges-table th {
  white-space: nowrap;
}
.review-focus {
  padding: 0 22px 14px;
  font-size: 12px;
  color: var(--muted);
  line-height: 1.7;
}
.review-stat > .review-state {
  font-size: 17px;
}
.charges-table strong {
  display: block;
  font-weight: 500;
  color: #544660;
}
.charges-table small {
  font-size: 10px;
  color: var(--muted);
  display: block;
  margin-top: 4px;
}
.charges-table .amount {
  font-family: Inter, Consolas, sans-serif;
  font-size: 13px;
  font-weight: 550;
  color: var(--ink);
  font-variant-numeric: tabular-nums;
}
.charges-table button {
  padding: 4px;
  color: var(--muted);
}
.charges-table .badge {
  font-size: 11px;
  padding: 3px 6px;
}
.posting {
  font-size: 11px;
  color: var(--muted);
}
.posting.AR {
  color: #568c7c;
}
.posting.AP {
  color: #9c7eb3;
}
.table-foot {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  justify-content: space-between;
  padding: 10px 19px;
}
.table-foot > span {
  font-size: 10px;
  color: var(--muted);
  display: flex;
  align-items: center;
  gap: 4px;
}
.table-foot > .posting-gap {
  flex-basis: 100%;
  flex-wrap: wrap;
  font-size: 12px;
  line-height: 1.7;
}
.table-foot svg {
  width: 11px;
  height: 11px;
}
.table-foot button {
  font-size: 11px;
  padding: 3px;
  color: #9a86b1;
}
.json-caption {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: var(--muted);
  margin-bottom: 13px;
}
.evidence-body {
  padding: 18px;
}
.evidence-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 10px 16px;
  margin-bottom: 12px;
}
.evidence-charge {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 5px 10px;
  min-width: 0;
}
.evidence-charge > span {
  font-size: 11px;
  color: var(--muted);
}
.evidence-charge h3 {
  margin: 0;
  font-size: 13px;
  color: var(--ink);
  overflow-wrap: anywhere;
}
.evidence-charge p {
  margin: 0;
  font-size: 11px;
  color: var(--muted);
  overflow-wrap: anywhere;
}
.evidence-quote {
  margin-bottom: 15px;
}
.evidence-source {
  display: flex;
  align-items: center;
  gap: 5px;
  color: var(--muted);
  font-size: 11px;
}
.evidence-source span {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  min-width: 0;
}
.evidence-source b {
  font-size: 10px;
  padding: 1px 4px;
  background: #f1edf7;
  border-radius: 3px;
  font-weight: 400;
  margin-left: auto;
}
.evidence-quote blockquote {
  margin: 9px 0 5px;
  border-left: 2px solid #cdb8ed;
  padding: 9px 11px;
  background: #f7faf7;
  color: #9b86ad;
  font-size: 12px;
  line-height: 1.9;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
.evidence-quote > p {
  font-size: 10px;
  color: var(--muted);
  overflow-wrap: anywhere;
}
.evidence-quote button {
  font-size: 11px;
  padding: 6px 0;
  color: var(--muted);
}
.reasoning {
  border-top: 1px solid #f0e8f7;
  padding-top: 13px;
  color: var(--muted);
  font-size: 12px;
}
.reasoning h4 {
  font-size: 12px;
  font-weight: 500;
  color: #8c729f;
  margin: 0 0 8px;
}
.reasoning ul {
  padding-left: 14px;
  margin: 0;
  line-height: 1.9;
}
.reasoning p {
  line-height: 1.9;
}
.evidence-edit {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin: 0;
}
.evidence-edit button {
  font-size: 11px;
  padding: 6px 9px;
  color: #9a80b3;
}
.evidence-edit button:last-child {
  color: var(--red);
}
.notice > button {
  margin-left: auto;
  padding: 0;
  color: inherit;
  font-size: 12px;
  white-space: nowrap;
}
.artifact-list {
  padding: 8px 20px;
}
.artifact-list button {
  width: 100%;
  border: 0;
  border-radius: 0;
  background: transparent;
  justify-content: flex-start;
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 12px 0;
  color: #9c80b3;
  font-size: 12px;
  border-bottom: 1px solid #f2eaf7;
}
.artifact-list button:last-child {
  border: 0;
}
.artifact-list small {
  display: block;
  font-size: 10px;
  color: var(--muted);
  margin-top: 3px;
}
.artifact-list button > svg:last-child {
  margin-left: auto;
}
details {
  font-size: 12px;
  color: var(--muted);
  margin-top: 15px;
}
details .code-block {
  margin-top: 9px;
}

@media (max-width: 1200px) {
  .task-banner {
    align-items: flex-start;
  }
  .task-title .flex {
    flex-wrap: wrap;
    gap: 7px;
  }
  .task-title h2 {
    max-width: 240px;
  }
  .task-actions {
    flex-wrap: wrap;
    justify-content: flex-end;
  }
  .task-actions button {
    font-size: 11px;
    padding: 6px 8px;
  }
  .result-toolbar > .small {
    display: none;
  }
  .search input {
    width: 220px;
  }
  .charges-table th,
  .charges-table td {
    padding: 12px 9px;
  }
  .table-foot > span {
    max-width: 190px;
  }
  .table-foot {
    padding: 10px 14px;
  }
  .table-foot > span {
    font-size: 9px;
  }
}

@media (max-width: 1000px) {
  .evidence-charge,
  .evidence-quote {
    margin: 0;
  }
  .evidence-edit {
    margin: 0;
    align-self: end;
  }

  .task-title h2 {
    max-width: 240px;
  }
}
@media (max-width: 600px) {
  .task-banner {
    flex-direction: column;
    align-items: stretch;
  }
  .task-actions {
    justify-content: flex-start;
  }

  .task-title h2 {
    max-width: 190px;
  }
  .tabs {
    gap: 20px;
    padding: 0 16px;
  }
  .tabs button {
    font-size: 12px;
  }
  .charges-table th,
  .charges-table td {
    padding: 12px 9px;
  }
  .charges-table td:first-child {
    min-width: 130px;
  }
  .charges-table th:first-child,
  .charges-table td:first-child {
    padding-left: 16px;
  }
  .table-foot > span {
    max-width: 160px;
  }
  .task-title p {
    font-size: 10px;
  }
  .task-title p i:nth-of-type(1) {
    display: none;
  }
}

/* Keep actions inside their own section; use one restrained color family. */
.task-workspace {
  --section-border: var(--line);
  gap: 16px;
}
.task-banner {
  background: transparent;
  border-color: var(--section-border);
  align-items: center;
  padding: 2px 0 4px;
}
.task-banner .task-title {
  flex: 1;
}
.task-actions,
.fee-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 7px;
  margin: 0;
}
.task-actions {
  flex-shrink: 1;
}
.task-actions button,
.fee-actions button {
  min-height: 34px;
  padding: 6px 10px;
  font-size: 12px;
  white-space: nowrap;
}
.task-actions > .ghost,
.fee-actions > .ghost {
  border-color: var(--line);
  background: var(--surface);
  color: var(--ink);
}
.fee-actions {
  flex-shrink: 0;
  margin-left: auto;
}
.fee-actions > button:first-child {
  color: var(--primary);
  background: var(--surface);
  border-color: #b9cfc1;
}
.fee-actions > .danger {
  color: var(--red);
  border-color: var(--line);
  background: var(--surface);
}
.task-workspace :deep(.agent-panel) {
  border-color: var(--section-border);
  background: var(--surface);
}
.task-workspace :deep(.agent-panel > .card-head) {
  background: var(--section-tint);
  border-color: var(--section-border);
}
.task-workspace :deep(.agent-panel .agent-symbol) {
  background: var(--line);
  color: var(--primary);
}
.task-workspace :deep(.agent-panel .conversation-footer) {
  background: var(--section-tint);
}
.review-overview {
  background: var(--primary-soft);
  border-color: var(--line);
  padding: 12px 18px;
}
.review-stat { display: flex; align-items: center; gap: 8px; padding-left: 16px; }
.review-stat > strong { font-size: 18px; margin-top: 0; }
.review-stat > .review-state { font-size: 14px; }
.posting.AP { color: var(--primary); }
.charges-table td, .charges-table strong { color: var(--ink); }
.results-card {
  border-color: var(--section-border);
}
.results-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 0 20px;
  background: var(--section-tint);
  border-bottom: 1px solid var(--section-border);
}
.section-heading {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--ink);
}
.section-heading h2 {
  margin: 0;
  font-size: 14px;
  font-weight: 650;
}
.results-heading .tabs {
  padding: 0;
  border: 0;
  gap: 18px;
}
.results-heading .tabs button {
  padding: 14px 0;
}
.result-toolbar {
  background: var(--surface);
}
.review-focus {
  padding: 0 20px 12px;
  margin: 0;
}
.search input {
  border-color: var(--section-border);
  background: var(--surface);
  color: var(--ink);
}
.charges-table th {
  background: #f7f9fc;
  color: #52665a;
  font-weight: 550;
}
.charges-table td {
  border-bottom-color: var(--line);
}
.charges-table tr.selected td {
  background: var(--primary-soft);
}
.charges-table tr.selected td:first-child {
  box-shadow: inset 3px 0 var(--primary);
}
.charges-table tr:hover td {
  background: var(--section-tint);
}
.table-foot {
  background: #fafbfd;
}
.bundle-materials {
  margin: 16px 18px;
  padding: 12px 14px;
  background: var(--section-tint);
  border: 1px solid var(--section-border);
  border-radius: 8px;
}
.bundle-materials summary {
  color: var(--ink);
}
.bundle-materials summary span {
  color: var(--muted);
}
.bundle-materials[open] .material-chips {
  margin-top: 12px;
}
.review-evidence {
  margin: 16px 18px 18px;
  border: 1px solid var(--section-border);
  border-radius: 10px;
  background: #fafbfd;
  overflow: hidden;
}
.evidence-body {
  padding: 14px;
}
.evidence-toolbar {
  margin: -14px -14px 14px;
  padding: 12px 14px;
  border-bottom: 1px solid var(--section-border);
  background: var(--section-tint);
}
.evidence-charge {
  flex: 1;
}
.review-section-title {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-weight: 600;
}
.evidence-charge > .review-section-title {
  color: var(--primary);
  font-size: 12px;
}
.evidence-charge h3 {
  color: var(--ink);
}
.evidence-charge small {
  color: var(--muted);
  font-size: 10px;
}
.review-evidence :deep(.confidence-panel) {
  background: var(--surface);
  border-color: var(--line);
}
.review-evidence :deep(.confidence-heading),
.review-evidence :deep(.confidence-note) {
  background: #fafbfd;
}
.review-quotes {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 0 12px;
}
.review-quotes > summary {
  color: var(--ink);
}
.review-quotes blockquote {
  color: #596b61;
  background: #f5f7fb;
  border-color: #afc4b6;
}
.evidence-source b {
  background: #f1f4f9;
  color: #617568;
}
.reasoning {
  border-color: var(--line);
}
.reasoning h4 {
  color: var(--ink);
}
.reasoning-details {
  padding: 0 2px;
}
@media (max-width: 1100px) {
  .task-banner {
    align-items: flex-start;
    flex-direction: column;
  }
  .task-actions {
    align-self: flex-end;
  }
}
@media (max-width: 600px) {
  .task-banner {
    padding: 0;
    gap: 14px;
  }
  .task-actions {
    width: 100%;
    gap: 5px;
    padding-top: 12px;
    border-top: 1px solid var(--line);
  }
  .review-overview { gap: 12px; }
  .review-stat { border: 0; padding: 0; }
  .review-stat:last-child { display: none; }
  .task-actions button,
  .fee-actions button {
    min-height: 34px;
    font-size: 11px;
    padding: 6px 7px;
  }
  .results-heading {
    padding: 0 14px;
    gap: 10px;
  }
  .section-heading h2 {
    font-size: 13px;
  }
  .results-heading .tabs {
    gap: 12px;
  }
  .results-heading .tabs button {
    font-size: 11px;
  }
  .bundle-materials {
    margin: 12px;
    padding: 10px;
  }
  .review-evidence {
    margin: 12px;
  }
  .evidence-body {
    padding: 10px;
  }
  .evidence-toolbar {
    margin: -10px -10px 12px;
    padding: 10px;
  }
  .evidence-charge {
    flex-basis: 100%;
    gap: 4px 8px;
  }
  .evidence-charge small {
    flex-basis: 100%;
  }
  .fee-actions {
    width: 100%;
  }
}
</style>
