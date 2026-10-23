<script setup lang="ts">
import { nextTick, onMounted, ref } from "vue";
import { CircleAlert, LoaderCircle, Save, X } from "@lucide/vue";
import { ApiError, api, errorMessage } from "../api/client";
import type { Charge, Revision, Task } from "../types/contracts";
const props = defineProps<{
  task: Task;
  charge: Charge | null;
  action: "edit" | "delete" | "split" | "entity";
  focusField?: string;
}>();
const emit = defineEmits<{ close: []; saved: [task: Task] }>();
const capturedRevision = ref(props.task.revision);
const initialEntity = props.task.accounting_entity;
const acceptedRevision = ref<number | null>(null);
const conflictTask = ref<Task | null>(null);
const conflictRows = ref<{ label: string; current: string; mine: string }[]>([]);
function valueAt(record: Charge | undefined | null, path: string): unknown {
  return path.split('.').reduce<unknown>((value, key) =>
    value && typeof value === 'object' ? (value as Record<string, unknown>)[key] : undefined, record);
}
function findConflicts(latest: Task, payload: Revision) {
  if (acceptedRevision.value === latest.revision) return [];
  if (props.action === 'entity') return latest.accounting_entity !== initialEntity &&
    latest.accounting_entity !== payload.accounting_entity
      ? [{label: '记账主体', current: latest.accounting_entity || '未提供', mine: entity.value}] : [];
  const row = latest.records?.find(item => item.charge_id === props.charge?.charge_id);
  if (props.action !== 'edit') return JSON.stringify(row) === JSON.stringify(props.charge) ? [] :
    [{label: '整条费用已更新', current: '请对照最新费用内容', mine: '移除或拆分当前费用'}];
  return payload.operations.flatMap(operation => {
    const field = fields.value.find(item => item.path === operation.field);
    const label = field?.label || (operation.field?.endsWith('posting_type') ? 'AR/AP' : operation.field) || '费用';
    const current = valueAt(row, operation.field || '');
    const original = valueAt(props.charge, operation.field || '');
    return String(current ?? '') !== String(original ?? '') && String(current ?? '') !== String(operation.value ?? '')
      ? [{label, current: String(current ?? '未提供'), mine: String(operation.value ?? '清空')}] : [];
  });
}
onMounted(async () => {
  await nextTick();
  if (!props.focusField) return;
  if (props.focusField.split(".").at(-1) === "posting_type") {
    document.getElementById("revision-posting")?.focus();
    return;
  }
  const field = fields.value.find(
    (item) =>
      item.path === props.focusField ||
      item.path.split(".").at(-1) === props.focusField,
  );
  if (field) document.getElementById(field.path)?.focus();
});
const title = {
  edit: "修订费用记录",
  delete: "移除这条费用",
  split: "拆分费用记录",
  entity: "更新本次记账主体",
}[props.action];
const fields = ref([
  {
    path: "charge_details.charge_item",
    label: "费用名称",
    value: props.charge?.charge_details?.charge_item || "",
    original: props.charge?.charge_details?.charge_item || "",
  },
  {
    path: "charge_details.amount",
    label: "金额",
    value: props.charge?.charge_details?.amount?.toString() || "",
    original: props.charge?.charge_details?.amount?.toString() || "",
  },
  {
    path: "charge_details.currency",
    label: "币种",
    value: props.charge?.charge_details?.currency || "",
    original: props.charge?.charge_details?.currency || "",
  },
  {
    path: "charge_details.payment_term",
    label: "付款方式",
    value: props.charge?.charge_details?.payment_term || "",
    original: props.charge?.charge_details?.payment_term || "",
  },
  {
    path: "document_info.reference_no",
    label: "单据编号",
    value: props.charge?.document_info?.reference_no || "",
    original: props.charge?.document_info?.reference_no || "",
  },
  {
    path: "document_info.document_date",
    label: "单据日期",
    value: props.charge?.document_info?.document_date || "",
    original: props.charge?.document_info?.document_date || "",
  },
  {
    path: "transaction_party.issuer",
    label: "出具方",
    value: props.charge?.transaction_party?.issuer || "",
    original: props.charge?.transaction_party?.issuer || "",
  },
  {
    path: "transaction_party.recipient",
    label: "接收方",
    value: props.charge?.transaction_party?.recipient || "",
    original: props.charge?.transaction_party?.recipient || "",
  },
]);
const entity = ref(props.task.accounting_entity || ""),
  posting = ref(props.charge?.financial_attributes?.posting_type || ""),
  reason = ref(""),
  split = ref("[]"),
  busy = ref(false),
  error = ref(""),
  conflict = ref(false);
async function save() {
  error.value = "";
  if (!reason.value.trim()) {
    error.value = "请填写修订依据，便于后续追溯。";
    return;
  }
  const payload: Revision = {
    expected_revision: capturedRevision.value,
    reason: reason.value.trim(),
    operations: [],
  };
  if (props.action === "entity") {
    if (!entity.value.trim()) {
      error.value = "请填写明确的记账主体。";
      return;
    }
    payload.accounting_entity = entity.value.trim();
  } else if (props.action === "delete") {
    payload.operations = [{ op: "delete", charge_id: props.charge?.charge_id }];
  } else if (props.action === "split") {
    try {
      const value: unknown = JSON.parse(split.value);
      if (
        !Array.isArray(value) ||
        value.length < 2 ||
        value.some((v) => !v || typeof v !== "object" || Array.isArray(v))
      )
        throw Error();
      payload.operations = [
        { op: "split", charge_id: props.charge?.charge_id, value },
      ];
    } catch {
      error.value = "请填写至少两个完整费用对象组成的 JSON 数组。";
      return;
    }
  } else {
    for (const field of fields.value) {
      if (field.value === field.original) continue;
      let value: string | number | null = field.value.trim() || null;
      if (field.path === "charge_details.amount" && value !== null) {
        value = Number(value);
        if (!Number.isFinite(value)) {
          error.value = "金额需要为有效数字。";
          return;
        }
      }
      payload.operations.push({
        op: "set",
        charge_id: props.charge?.charge_id,
        field: field.path,
        value,
      });
    }
    if ((posting.value || "") !== (props.charge?.financial_attributes?.posting_type || "")) {
      payload.operations.push({
        op: "set",
        charge_id: props.charge?.charge_id,
        field: "financial_attributes.posting_type",
        value: posting.value || null,
      });
    }
    if (!payload.operations.length) {
      error.value = "请先修改需要纠正的字段。";
      return;
    }
  }
  busy.value = true;
  try {
    const latest = await api.task(props.task.id);
    const conflicts = findConflicts(latest, payload);
    if (conflicts.length) {
      conflictTask.value = latest;
      conflictRows.value = conflicts;
      conflict.value = true;
      error.value = '您修改的字段也被更新了。输入已保留，请在下方对照后选择如何提交。';
      return;
    }
    capturedRevision.value = latest.revision;
    payload.expected_revision = latest.revision;
    conflict.value = false;
    conflictRows.value = [];
    emit("saved", await api.revise(props.task.id, payload));
  } catch (e) {
    const code = e instanceof ApiError ? (e.details as {error?: string})?.error : undefined;
    conflict.value = false;
    error.value = code === 'REVISION_CONFLICT'
      ? '提交期间内容又有更新，输入已保留。再次提交会核对最新字段，避免覆盖他人的修改。'
      : errorMessage(e);
  } finally {
    busy.value = false;
  }
}
async function submitMyValues() {
  if (!conflictTask.value) return;
  acceptedRevision.value = conflictTask.value.revision;
  conflict.value = false;
  await save();
}
</script>
<template>
  <div
    class="modal-overlay"
    @click.self="!busy && emit('close')"
    @keydown.esc="!busy && emit('close')"
  >
    <form
      class="modal revision-modal"
      role="dialog"
      aria-modal="true"
      aria-labelledby="revision-title"
      @submit.prevent="save"
    >
      <div class="modal-head">
        <div>
          <span class="eyebrow">HUMAN REVIEW · R{{ capturedRevision }}</span>
          <h2 id="revision-title">{{ title }}</h2>
        </div>
        <button
          type="button"
          class="icon ghost"
          aria-label="关闭"
          :disabled="busy"
          @click="emit('close')"
        >
          <X />
        </button>
      </div>
      <div class="modal-body">
        <div v-if="action === 'delete'" class="notice warning">
          <CircleAlert /><span
            >将移除“{{
              charge?.charge_details?.charge_item || "当前费用"
            }}”。服务端会重新校验本次结果，并保留修订记录。</span
          >
        </div>
        <div v-else-if="action === 'entity'" class="field">
          <label for="revision-entity">本次记账主体</label
          ><input
            id="revision-entity"
            v-model="entity"
            placeholder="公司完整名称"
          /><span class="field-hint"
            >依赖主体的方向与校验由服务端重新计算。</span
          >
        </div>
        <div v-else-if="action === 'split'" class="field">
          <label for="split-records">分拆后的费用对象数组</label>
          <p class="field-hint">
            填写与当前费用相同的五段 JSON
            结构；服务端负责校验分拆后的金额与依据。
          </p>
          <textarea id="split-records" v-model="split" rows="12" class="mono" />
          <details>
            <summary>查看当前记录结构</summary>
            <pre class="code-block">{{ JSON.stringify(charge, null, 2) }}</pre>
          </details>
        </div>
        <template v-else>
          <div class="form-grid">
            <div class="field">
              <label for="revision-posting">AR/AP</label>
              <select id="revision-posting" v-model="posting">
                <option value="">待确认</option>
                <option value="AR">AR 应收</option>
                <option value="AP">AP 应付</option>
              </select>
              <span class="field-hint"
                >方向有误时，可核对本次记账主体和下方交易双方。</span
              >
            </div>
            <div
              v-for="field in fields.slice(0, 5)"
              :key="field.path"
              class="field"
            >
              <label :for="field.path">{{ field.label }}</label
              ><input
                :id="field.path"
                v-model="field.value"
                :inputmode="field.path.endsWith('amount') ? 'decimal' : 'text'"
                placeholder="留空表示未知"
              />
            </div>
          </div>
          <details class="party-fields">
            <summary>核对交易双方与单据日期</summary>
            <div class="form-grid">
              <div
                v-for="field in fields.slice(5)"
                :key="field.path"
                class="field"
              >
                <label :for="field.path">{{ field.label }}</label>
                <input
                  :id="field.path"
                  v-model="field.value"
                  placeholder="留空表示未知"
                />
              </div>
            </div>
          </details>
        </template>
        <div class="field">
          <label for="revision-reason">修订依据</label
          ><textarea
            id="revision-reason"
            v-model="reason"
            rows="2"
            placeholder="例如：核对原始账单第 2 页，币种应为 USD。"
          />
        </div>
        <div v-if="error" class="notice error" role="alert">{{ error }}</div>
        <div v-if="conflictRows.length && conflict" class="conflict-comparison">
          <div v-for="row in conflictRows" :key="row.label">
            <strong>{{ row.label }}</strong>
            <p>当前内容：{{ row.current }}</p><p>您的输入：{{ row.mine }}</p>
          </div>
          <button type="button" :disabled="busy" @click="submitMyValues">保留我的输入，提交到最新版本</button>
        </div>
        <div v-if="!conflict" class="notice">
          <CircleAlert :size="16" /><span
            >修改将生成新的
            Revision，触发相关校验。人工确认的字段与修改依据会随本次任务保留。</span
          >
        </div>
      </div>
      <div class="modal-foot">
        <button type="button" :disabled="busy" @click="emit('close')">
          取消</button
        ><button
          type="submit"
          :disabled="busy || conflict"
          :class="action === 'delete' ? 'danger' : 'primary'"
        >
          <LoaderCircle v-if="busy" class="loading-icon" /><Save
            v-else
            :size="16"
          />{{ busy ? "正在校验…" : "提交修订" }}
        </button>
      </div>
    </form>
  </div>
</template>
<style scoped>
.revision-modal {
  width: min(690px, calc(100vw - 32px));
  max-height: calc(100dvh - 32px);
  display: flex;
  flex-direction: column;
}
.modal-body { min-height: 0; overflow-y: auto; }
.modal-head, .modal-foot { flex-shrink: 0; }
.conflict-comparison { border: 1px solid var(--line); padding: 14px; border-radius: 8px; overflow-wrap: anywhere; }
.conflict-comparison p { margin: 5px 0; font-size: 13px; }
@media (max-width: 600px) { .form-grid { grid-template-columns: 1fr; } }
.modal-head .eyebrow {
  font-size: 11px;
}
.modal-head h2 {
  margin-top: 4px;
}
.mono {
  font-size: 12px;
}
details {
  font-size: 12px;
  color: #9c85ae;
  margin-top: 8px;
}
details summary {
  cursor: pointer;
}
.party-fields > .form-grid {
  margin-top: 12px;
}
details pre {
  margin-top: 10px;
}
</style>
