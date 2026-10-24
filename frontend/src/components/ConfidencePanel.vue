<script setup lang="ts">
import { computed } from "vue";
import {
  ArrowUpRight,
  CircleAlert,
  LoaderCircle,
  RefreshCw,
  ShieldCheck,
} from "@lucide/vue";
import type { RecordConfidence } from "../types/contracts";

const props = defineProps<{
  value?: RecordConfidence;
  loading?: boolean;
  error?: string;
  unavailableReason?: string;
}>();
const emit = defineEmits<{ retry: []; locate: [field: string] }>();

const labels: Record<string, string> = {
  posting_type: "AR/AP",
  reference_no: "单据编号",
  charge_item: "费用名称",
  amount: "金额",
  currency: "币种",
  payment_term: "付款方式",
};
const fieldOrder = [
  "posting_type",
  "reference_no",
  "charge_item",
  "amount",
  "currency",
  "payment_term",
] as const;

function recordValue(key: string): unknown {
  const record = props.value?.record as unknown as
    | Record<string, any>
    | undefined;
  const nested: Record<string, unknown> = {
    reference_no: record?.document_info?.reference_no,
    charge_item: record?.charge_details?.charge_item,
    amount: record?.charge_details?.amount,
    currency: record?.charge_details?.currency,
    payment_term: record?.charge_details?.payment_term,
    posting_type: record?.financial_attributes?.posting_type,
  };
  return nested[key] ?? record?.[key] ?? null;
}

function displayValue(value: unknown): string {
  if (value == null || value === "") return "未提供";
  return String(value);
}

function hint(field?: { status?: string; reasons?: string[] }) {
  if (!field || field.status === "missing") return "";
  if (field.status === "supported") return "有原文依据";
  if (field.status === "ambiguous") return field.reasons?.[0] || "原文存在歧义";
  return field.reasons?.[0] || "可查看原文确认";
}

const fields = computed(() => {
  const map = props.value?.fields || {};
  const reviewItems = props.value?.review_items || [];
  return fieldOrder.map((key) => {
    const entry = Object.entries(map).find(
      ([name]) => name.split(".").at(-1) === key,
    );
    const field = entry?.[1] || { score: null, status: "missing", reasons: [] };
    const review = reviewItems.find((item) => item.field === key);
    const value = recordValue(key) ?? review?.value ?? null;
    return {
      name: entry?.[0] || key,
      key,
      label: labels[key] || key,
      score: field.score ?? null,
      missing: value == null || value === "",
      value: displayValue(value),
      hint: review?.reason || hint(field),
      observations: field.observations
        ?.map((observation) => ({
          raw: displayObservation(observation.raw),
          candidates: displayObservation(observation.candidates),
        }))
        .filter((observation) => observation.raw || observation.candidates)
        .filter(
          (observation, index, all) =>
            all.findIndex(
              (item) =>
                item.raw === observation.raw &&
                item.candidates === observation.candidates,
            ) === index,
        ),
    };
  });
});

function displayObservation(value: unknown): string {
  if (value == null) return "";
  if (Array.isArray(value))
    return value.map(displayObservation).filter(Boolean).join(" / ");
  if (typeof value === "object") {
    const object = value as Record<string, unknown>;
    const candidate =
      object.value ??
      object.amount ??
      object.normalized_value ??
      object.normalized;
    return candidate == null
      ? Object.values(object)
          .map(displayObservation)
          .filter(Boolean)
          .join(" · ")
      : displayObservation(candidate);
  }
  return String(value);
}
function displayScore(value: number | null | undefined) {
  return value == null ? "—" : Math.round(value);
}
function bandLabel(band?: string) {
  return (
    (
      {
        high: "支持充分",
        medium: "建议核对",
        low: "需要复核",
        unavailable: "依据不足",
      } as Record<string, string>
    )[band || ""] || "待核对"
  );
}
function reviewLabel(route?: string) {
  return (
    (
      {
        quick_confirm: "可直接确认当前版本",
        review_suggested: "建议查看原文后确认",
        blocked: "结果尚不能确认，请核对下方账单信息",
      } as Record<string, string>
    )[route || ""] || ""
  );
}
</script>
<template>
  <section class="confidence-panel" aria-label="当前费用置信度">
    <div class="confidence-heading">
      <div class="confidence-title">
        <ShieldCheck :size="15" />
        <h4>提取置信度</h4>
      </div>
      <div v-if="value" class="confidence-overview">
        <strong :class="['confidence-score', value.band]"
          >{{ displayScore(value.review_score ?? value.score)
          }}<small>/ 100</small></strong
        >
        <b>{{
          value.review_required === false
            ? "已有字段通过提取核验"
            : bandLabel(value.band)
        }}</b>
        <span v-if="loading" class="method-label" role="status">更新中…</span>
      </div>
    </div>
    <div v-if="loading && !value" class="confidence-state" role="status">
      <LoaderCircle class="loading-icon" />正在核对当前版本的依据…
    </div>
    <div
      v-else-if="error && !value"
      class="confidence-state failure"
      role="alert"
    >
      <CircleAlert :size="15" /><span>{{ error }}</span
      ><button
        class="icon ghost"
        aria-label="重试置信度"
        @click="emit('retry')"
      >
        <RefreshCw :size="14" />
      </button>
    </div>
    <template v-else-if="value">
      <div class="confidence-fields">
        <div
          v-for="field in fields"
          :key="field.key"
          class="confidence-field"
          :class="{
            'needs-review':
              !field.missing && field.score != null && field.score < 85,
          }"
        >
          <div class="field-head">
            <button
              class="field-locator"
              :title="field.hint || '查看字段依据'"
              @click="emit('locate', field.name)"
            >
              <span>{{ field.label }}</span
              ><ArrowUpRight :size="12" />
            </button>
            <b :class="{ deducted: field.score != null && field.score < 85 }">{{
              displayScore(field.score)
            }}</b>
          </div>
          <p class="field-value" :class="{ missing: field.missing }">
            {{ field.value }}
          </p>
          <p
            v-if="field.hint && field.hint !== '有原文依据'"
            class="field-hint"
          >
            {{ field.hint }}
          </p>
          <details v-if="field.observations?.length" class="field-observations">
            <summary>原文取值</summary>
            <div
              v-for="(observation, index) in field.observations"
              :key="index"
            >
              <p v-if="observation.raw">
                <span>原文：</span>{{ observation.raw }}
              </p>
              <p v-if="observation.candidates">
                <span>可能取值：</span>{{ observation.candidates }}
              </p>
            </div>
          </details>
        </div>
      </div>
      <p class="confidence-note">
        <span v-if="value.review_required"
          >{{
            value.review_route
              ? reviewLabel(value.review_route)
              : "请核对提示字段"
          }}
          · </span
        >分值用于辅助复核，不代表统计准确率。
      </p>
    </template>
    <p v-else class="confidence-state">
      {{ unavailableReason || "当前费用尚无评分依据。" }}
    </p>
  </section>
</template>
<style scoped>
.confidence-panel {
  border: 1px solid var(--line);
  border-radius: 10px;
  overflow: hidden;
  container-type: inline-size;
}
.confidence-heading {
  padding: 10px 12px;
  background: var(--canvas);
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px 16px;
}
.confidence-title,
.confidence-overview {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}
.confidence-title {
  color: var(--primary);
}
h4 {
  font-size: 12px;
  margin: 0;
  color: var(--ink);
}
.method-label {
  color: var(--muted);
  font-size: 11px;
}
.confidence-state {
  padding: 14px;
  margin: 0;
  font-size: 12px;
  color: var(--muted);
  display: flex;
  align-items: center;
  gap: 8px;
}
.failure {
  color: var(--red);
}
.failure span {
  flex: 1;
}
.confidence-score {
  font-size: 18px;
  line-height: 1.2;
  color: var(--amber);
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}
.confidence-score.high {
  color: var(--green);
}
.confidence-score.low {
  color: var(--red);
}
.confidence-score small {
  font-size: 11px;
  color: var(--muted);
  margin-left: 3px;
  font-weight: 400;
}
.confidence-overview b {
  font-size: 11px;
  font-weight: 500;
  color: var(--ink);
}
.confidence-fields {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 1px;
  border-top: 1px solid var(--line);
  background: var(--line);
}
.confidence-field {
  min-width: 0;
  padding: 10px 12px;
  background: var(--surface);
  display: flex;
  flex-direction: column;
  gap: 5px;
  font-size: 11px;
}
.confidence-field.needs-review {
  background: var(--amber-soft);
}
.field-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.field-head > b {
  font-size: 12px;
  font-variant-numeric: tabular-nums;
}
.field-locator {
  padding: 0;
  min-height: 24px;
  border: 0;
  background: transparent;
  justify-content: flex-start;
  color: var(--primary);
  font-size: 11px;
}
.field-locator:focus-visible {
  outline: 2px solid var(--primary);
  outline-offset: 2px;
  border-radius: 3px;
}
.field-value {
  margin: 0;
  font-size: 13px;
  font-weight: 600;
  color: var(--ink);
  line-height: 1.45;
  overflow-wrap: anywhere;
}
.field-value.missing {
  font-weight: 400;
  color: var(--muted);
}
.field-hint {
  margin: 0;
  color: var(--amber);
  line-height: 1.5;
  overflow-wrap: anywhere;
}
.deducted {
  color: var(--amber);
}
.field-observations {
  color: var(--muted);
  line-height: 1.5;
  overflow-wrap: anywhere;
}
.field-observations summary {
  cursor: pointer;
  padding: 2px 0;
}
.field-observations > div {
  margin-top: 4px;
  border-left: 2px solid var(--line);
  padding-left: 6px;
}
.field-observations p {
  margin: 0;
}
.field-observations span {
  color: var(--ink);
}
.confidence-note {
  margin: 0;
  padding: 7px 12px;
  border-top: 1px solid var(--line);
  color: var(--muted);
  font-size: 10px;
  line-height: 1.5;
}
@container (min-width:960px) {
  .confidence-fields {
    grid-template-columns: repeat(6, minmax(0, 1fr));
  }
}
@container (max-width:520px) {
  .confidence-fields {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .confidence-overview {
    flex-wrap: wrap;
  }
}
@container (max-width:280px) {
  .confidence-fields {
    grid-template-columns: 1fr;
  }
}
</style>
