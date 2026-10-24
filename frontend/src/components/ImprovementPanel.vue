<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import {
  ArrowRight,
  Check,
  CircleAlert,
  FlaskConical,
  GitBranch,
  History,
  LoaderCircle,
  Plus,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  X,
} from "@lucide/vue";
import { api, errorMessage } from "../api/client";
import EvaluationDatasets from "./EvaluationDatasets.vue";
const datasetId = ref("builtin");
const removeAlias = ref(false);
import {
  formatDate,
  type ImprovementCandidate,
  type ImprovementRegistry,
  type Task,
} from "../types/contracts";

const props = defineProps<{ tasks: Task[]; initialTaskId?: string }>();
const candidates = ref<ImprovementCandidate[]>([]);
const registry = ref<ImprovementRegistry>({});
const selectedId = ref("");
const loading = ref(true),
  busy = ref(""),
  error = ref(""),
  notice = ref("");
const createOpen = ref(false),
  rollbackOpen = ref(false);
const taskId = ref(props.initialTaskId || ""),
  sourceTask = ref<Task | null>(null);
const alias = ref(""),
  standardName = ref("");
const entity = ref(""),
  proposer = ref(""),
  optedIn = ref(false);
const reviewer = ref(""),
  reason = ref(""),
  approved = ref(false);
const targetVersion = ref(""),
  rollbackApproved = ref(false);
const selected = computed(() =>
  candidates.value.find((x) => candidateId(x) === selectedId.value),
);
const mappingChanges = computed(() => {
  const before = selected.value?.before || {},
    after = selected.value?.after || {};
  return [...new Set([...Object.keys(before), ...Object.keys(after)])]
    .filter((alias) => before[alias] !== after[alias])
    .map((alias) => ({ alias, before: before[alias], after: after[alias] }));
});
const versions = computed(() => {
  const raw = registry.value.versions;
  if (Array.isArray(raw))
    return raw
      .map((item) => {
        if (typeof item === "string") return item;
        const value = item as Record<string, unknown>;
        return String(value.version || value.id || "");
      })
      .filter(Boolean);
  return raw && typeof raw === "object" ? Object.keys(raw) : [];
});
function candidateId(value: ImprovementCandidate): string {
  return value.id || value.candidate_id || "";
}
function statusLabel(value: string): string {
  return (
    (
      {
        draft: "候选草稿",
        candidate: "候选草稿",
        evaluated: "已评测",
        passed: "评测通过",
        rejected: "未通过",
        published: "已发布",
        failed: "评测未通过",
      } as Record<string, string>
    )[value] || value
  );
}
function issueText(value: unknown): string {
  if (value && typeof value === "object") {
    const issue = value as { code?: string; message?: string };
    return (
      [issue.code, issue.message].filter(Boolean).join(" · ") ||
      JSON.stringify(value)
    );
  }
  return String(value);
}
async function load() {
  error.value = "";
  try {
    const result = await api.improvements();
    candidates.value = result.candidates;
    registry.value = result.registry;
    if (!selectedId.value || !selected.value)
      selectedId.value = result.candidates[0]
        ? candidateId(result.candidates[0])
        : "";
  } catch (e) {
    error.value = errorMessage(e);
  } finally {
    loading.value = false;
  }
}
watch(
  taskId,
  async (id) => {
    sourceTask.value = null;
    if (!id) return;
    try {
      const task = await api.task(id);
      if (taskId.value !== id) return;
      sourceTask.value = task;
      entity.value = task.accounting_entity || "";
    } catch (e) {
      error.value = errorMessage(e);
    }
  },
  { immediate: true },
);
watch(selectedId, () => {
  approved.value = false;
  reason.value = "";
});
function openCreate() {
  notice.value = "";
  createOpen.value = true;
}
async function propose() {
  error.value = "";
  if (
    !sourceTask.value ||
    !entity.value.trim() ||
    !alias.value.trim() ||
    (!removeAlias.value && !standardName.value.trim()) ||
    !proposer.value.trim() ||
    !optedIn.value
  ) {
    error.value =
      "请选择来源任务、填写主体与映射，并明确选择将本次反馈沉淀为候选。";
    return;
  }
  busy.value = "create";
  try {
    const active = await api.activeMapping(entity.value.trim());
    const after = { ...active.mapping };
    if (removeAlias.value) delete after[alias.value.trim()];
    else after[alias.value.trim()] = standardName.value.trim();
    const result = await api.proposeImprovement({
      task_id: sourceTask.value.id,
      expected_revision: sourceTask.value.revision,
      opt_in: true,
      kind: "charge_mapping",
      scope: { accounting_entity: entity.value.trim() },
      proposed_by: proposer.value.trim(),
      before: active.mapping,
      after,
    });
    selectedId.value = candidateId(result.candidate);
    createOpen.value = false;
    optedIn.value = false;
    notice.value = "候选已保存，当前任务的账单与规则版本保持原样。";
    await load();
  } catch (e) {
    error.value = errorMessage(e);
  } finally {
    busy.value = "";
  }
}
async function evaluate() {
  if (!selected.value) return;
  error.value = "";
  notice.value = "";
  busy.value = "evaluate";
  try {
    await api.evaluateImprovement(candidateId(selected.value), datasetId.value);
    await load();
    notice.value = "评测已完成，请核对具体覆盖与失败样例后决定是否发布。";
  } catch (e) {
    await load();
    error.value = errorMessage(e);
  } finally {
    busy.value = "";
  }
}
async function publish() {
  if (!selected.value) return;
  error.value = "";
  notice.value = "";
  if (!reviewer.value.trim() || !reason.value.trim() || !approved.value) {
    error.value = "请填写审核人、发布依据，并确认审核当前候选版本。";
    return;
  }
  busy.value = "publish";
  try {
    await api.publishImprovement(candidateId(selected.value), {
      reviewer: reviewer.value.trim(),
      reason: reason.value.trim(),
      approved: true,
      expected_active_version: registry.value.active_version,
    });
    await load();
    approved.value = false;
    notice.value = "新版本已发布，仅后续新建任务使用，已有任务保留原版本。";
  } catch (e) {
    error.value = errorMessage(e);
  } finally {
    busy.value = "";
  }
}
async function rollback() {
  error.value = "";
  notice.value = "";
  if (
    !targetVersion.value ||
    !reviewer.value.trim() ||
    !reason.value.trim() ||
    !rollbackApproved.value
  ) {
    error.value = "请选择目标版本，填写审核人与原因，并确认本次回滚。";
    return;
  }
  busy.value = "rollback";
  try {
    await api.rollbackImprovement({
      target_version: targetVersion.value,
      reviewer: reviewer.value.trim(),
      reason: reason.value.trim(),
      approved: true,
      expected_active_version: registry.value.active_version,
    });
    await load();
    rollbackApproved.value = false;
    rollbackOpen.value = false;
    notice.value = "已切换后续新任务使用的有效版本，已有任务保留原版本。";
  } catch (e) {
    error.value = errorMessage(e);
  } finally {
    busy.value = "";
  }
}
onMounted(() => {
  void load();
});
</script>

<template>
  <div class="improvement-panel">
    <div class="card improvement-overview">
      <span class="improvement-symbol"><GitBranch /></span>
      <div>
        <h2>从一次纠错，到可审核的改进</h2>
        <p>保存候选 → 固定样例评测 → 人工审核 → 新任务使用</p>
      </div>
      <span class="version-label"
        >当前有效版本 <code>{{ registry.active_version || "—" }}</code></span
      >
      <button class="ghost icon" aria-label="刷新反馈候选" @click="load">
        <RefreshCw :size="15" />
      </button>
      <button class="primary" @click="openCreate">
        <Plus :size="15" />创建映射候选
      </button>
    </div>
    <div v-if="error" class="notice error" role="alert">
      <CircleAlert :size="15" />{{ error }}
    </div>
    <div v-if="notice" class="notice" role="status">
      <Check :size="15" />{{ notice }}
    </div>
    <section v-if="createOpen" class="card">
      <div class="card-head">
        <h3>将当前任务反馈保存为候选</h3>
        <button
          class="ghost icon"
          aria-label="关闭候选表单"
          @click="createOpen = false"
        >
          <X :size="15" />
        </button>
      </div>
      <form class="candidate-form" @submit.prevent="propose">
        <div class="form-grid">
          <label
            >来源任务<select v-model="taskId" required>
              <option value="">请选择任务</option>
              <option v-for="task in tasks" :key="task.id" :value="task.id">
                {{ task.title || task.id }} · R{{ task.revision }}
              </option></select
            ><small v-if="sourceTask"
              >绑定 Revision
              {{ sourceTask.revision }}，提交时由服务端核对版本。</small
            ></label
          >
          <label
            >适用记账主体<input
              v-model="entity"
              required
              placeholder="与来源任务一致的完整公司名"
          /></label>
          <label
            >原始费用别名<input
              v-model="alias"
              required
              placeholder="例如 Document Charge"
          /></label>
          <label
            >候选标准费用名<input
              v-model="standardName"
              :required="!removeAlias"
              :disabled="removeAlias"
              placeholder="例如 Documentation Fee"
          /></label>
          <label class="check-line"
            ><input
              v-model="removeAlias"
              type="checkbox"
            />移除此别名的自定义映射（仍需评测与发布）</label
          >
          <label
            >提出人<input
              v-model="proposer"
              required
              placeholder="记录本次反馈的提出者"
          /></label>
        </div>
        <label class="check-line"
          ><input
            v-model="optedIn"
            type="checkbox"
            required
          />我明确选择将这次反馈沉淀为费用映射候选，供后续评测与审核。</label
        >
        <div class="form-footer">
          <p>当前任务的人工修改只作用于当前版本。候选发布后仅新任务使用。</p>
          <button class="primary" :disabled="!!busy || !sourceTask">
            <LoaderCircle
              v-if="busy === 'create'"
              class="loading-icon"
              :size="14"
            /><Plus v-else :size="14" />保存候选
          </button>
        </div>
      </form>
    </section>
    <EvaluationDatasets @select="datasetId = $event" />
    <div v-if="loading" class="card empty">
      <LoaderCircle class="loading-icon" />
      <h3>正在读取候选与版本</h3>
    </div>
    <div v-else-if="!candidates.length" class="card empty">
      <Sparkles />
      <h3>还没有共享改进候选</h3>
      <p>从已修订的任务提议费用映射，经评测与审核后再供新任务使用。</p>
      <button @click="openCreate"><Plus :size="14" />创建第一个候选</button>
    </div>
    <div v-else class="improvement-grid">
      <aside class="candidate-list card" aria-label="改进候选列表">
        <div class="card-head">
          <h3>候选记录</h3>
          <span class="small muted">{{ candidates.length }} 项</span>
        </div>
        <button
          v-for="item in candidates"
          :key="candidateId(item)"
          :class="{ selected: candidateId(item) === selectedId }"
          @click="selectedId = candidateId(item)"
        >
          <div class="flex between">
            <strong>{{
              Object.keys(item.after || {}).join("、") || item.kind
            }}</strong
            ><span class="badge">{{ statusLabel(item.status) }}</span>
          </div>
          <p>{{ item.scope?.accounting_entity || "未限定主体" }}</p>
          <small
            >{{ item.proposed_by || "未记录提出者" }} ·
            {{ formatDate(item.created_at) }}</small
          >
        </button>
      </aside>
      <section v-if="selected" class="candidate-detail card">
        <div class="card-head">
          <div>
            <span class="eyebrow">CHARGE MAPPING</span>
            <h3>费用映射候选</h3>
          </div>
          <span class="badge">{{ statusLabel(selected.status) }}</span>
        </div>
        <div class="candidate-content">
          <div class="candidate-meta">
            <span
              >适用主体<strong>{{
                selected.scope?.accounting_entity || "—"
              }}</strong></span
            ><span
              >来源 Revision<strong>{{
                selected.source?.revision || "—"
              }}</strong></span
            ><span
              >基线版本<strong class="mono">{{
                selected.base_version || "—"
              }}</strong></span
            >
          </div>
          <div
            class="mapping-diff"
            v-for="change in mappingChanges"
            :key="change.alias"
          >
            <span
              ><small>原始别名</small><strong>{{ change.alias }}</strong
              ><small v-if="change.before"
                >原映射：{{ change.before }}</small
              ></span
            ><ArrowRight :size="17" /><span
              ><small>候选标准名</small
              ><strong>{{ change.after || "移除此自定义映射" }}</strong></span
            >
          </div>
          <div class="evaluation-head">
            <h4><FlaskConical :size="16" />固定样例评测</h4>
            <button
              :disabled="
                !!busy ||
                selected.kind !== 'charge_mapping' ||
                selected.status === 'published'
              "
              @click="evaluate"
            >
              <LoaderCircle
                v-if="busy === 'evaluate'"
                class="loading-icon"
                :size="14"
              /><FlaskConical v-else :size="14" />运行评测
            </button>
          </div>
          <template v-if="selected.comparison">
            <div
              v-if="selected.comparison.total_cases != null"
              class="evaluation-scores"
            >
              <div>
                <span>基线通过</span
                ><strong
                  >{{ selected.comparison.baseline_passes
                  }}<small
                    >/ {{ selected.comparison.total_cases }}</small
                  ></strong
                >
              </div>
              <ArrowRight :size="17" />
              <div>
                <span>候选通过</span
                ><strong
                  >{{ selected.comparison.candidate_passes
                  }}<small
                    >/ {{ selected.comparison.total_cases }}</small
                  ></strong
                >
              </div>
              <span class="score-scope"
                >{{
                  selected.comparison.synthetic
                    ? "合成样例评测"
                    : "固定样例评测"
                }}<small>{{ selected.comparison.engine }}</small></span
              >
            </div>
            <div :class="['notice', selected.comparison.passed ? '' : 'error']">
              <Check v-if="selected.comparison.passed" :size="15" /><CircleAlert
                v-else
                :size="15"
              />{{
                selected.comparison.passed
                  ? "评测通过，请继续核对覆盖范围并人工审核。"
                  : "评测未通过或尚未形成通过结论，暂不能发布。"
              }}
            </div>
            <p v-if="selected.comparison.synthetic" class="evaluation-empty">
              本次范围为明确标注的合成回归与最终评测样例，不衡量真实 OCR
              或原题材料的提取准确率。
            </p>
            <p
              v-for="(issue, index) in selected.comparison.issues"
              :key="index"
              class="evaluation-issue"
            >
              {{ issueText(issue) }}
            </p>
            <details class="report">
              <summary>查看评测报告与失败问题</summary>
              <pre class="code-block">{{
                JSON.stringify(selected.comparison, null, 2)
              }}</pre>
            </details>
          </template>
          <p v-else class="evaluation-empty">
            候选尚未评测。固定样例为明确标注的合成回归样例；未覆盖的别名需要先补充样例，不能直接发布。
          </p>
          <form
            v-if="selected.status !== 'published'"
            class="release-form"
            @submit.prevent="publish"
          >
            <h4><ShieldCheck :size="16" />人工审核发布</h4>
            <div class="form-grid">
              <label
                >审核人<input
                  v-model="reviewer"
                  required
                  placeholder="审核人姓名" /></label
              ><label
                >审核依据<input
                  v-model="reason"
                  required
                  placeholder="说明映射依据与已核对的评测结果"
              /></label>
            </div>
            <label class="check-line"
              ><input
                v-model="approved"
                type="checkbox"
                required
              />我已审核当前候选与评测报告，同意发布为后续新任务的有效版本。</label
            >
            <button
              class="primary"
              :disabled="
                !!busy ||
                !selected.comparison?.passed ||
                selected.kind !== 'charge_mapping'
              "
            >
              <LoaderCircle
                v-if="busy === 'publish'"
                class="loading-icon"
                :size="14"
              /><ShieldCheck v-else :size="14" />审核并发布
            </button>
          </form>
          <div v-else class="notice">
            <ShieldCheck
              :size="15"
            />候选已有发布记录。新任务使用顶部的当前有效版本，已有任务保留启动时的版本。
          </div>
          <details class="report">
            <summary>候选原始记录</summary>
            <pre class="code-block">{{
              JSON.stringify(selected, null, 2)
            }}</pre>
          </details>
        </div>
      </section>
    </div>
    <section class="card version-history">
      <button class="ghost" @click="rollbackOpen = !rollbackOpen">
        <History :size="15" />{{
          rollbackOpen ? "收起版本回滚" : "版本记录与回滚"
        }}</button
      ><span class="small muted">有效版本切换只影响后续新任务</span>
      <form v-if="rollbackOpen" @submit.prevent="rollback">
        <div class="form-grid">
          <label
            >目标版本<select v-model="targetVersion" required>
              <option value="">请选择已发布版本</option>
              <option
                v-for="version in versions"
                :key="version"
                :value="version"
                :disabled="version === registry.active_version"
              >
                {{ version
                }}{{ version === registry.active_version ? "（当前）" : "" }}
              </option>
            </select></label
          ><label>审核人<input v-model="reviewer" required /></label
          ><label class="wide"
            >回滚原因<input v-model="reason" required
          /></label>
        </div>
        <label class="check-line"
          ><input
            v-model="rollbackApproved"
            type="checkbox"
            required
          />确认将后续新任务切换到选择的历史版本。</label
        >
        <button :disabled="!!busy || !targetVersion">
          <LoaderCircle
            v-if="busy === 'rollback'"
            class="loading-icon"
            :size="14"
          /><History v-else :size="14" />审核并回滚
        </button>
        <details class="report">
          <summary>版本与回滚记录</summary>
          <pre class="code-block">{{ JSON.stringify(registry, null, 2) }}</pre>
        </details>
      </form>
    </section>
  </div>
</template>

<style scoped>
.improvement-panel {
  display: grid;
  gap: 18px;
}
.improvement-overview {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 20px;
  flex-wrap: wrap;
}
.improvement-symbol {
  display: grid;
  place-items: center;
  width: 42px;
  height: 42px;
  border-radius: 12px;
  background: var(--primary-soft);
  color: var(--primary);
}
.improvement-overview h2 {
  font-size: 15px;
}
.improvement-overview p {
  font-size: 12px;
  color: var(--muted);
  margin-top: 5px;
}
.version-label {
  margin-left: auto;
  display: grid;
  gap: 3px;
  font-size: 11px;
  color: var(--muted);
}
.version-label code {
  color: var(--ink);
  font-size: 12px;
}
.improvement-grid {
  display: grid;
  grid-template-columns: 290px minmax(0, 1fr);
  gap: 18px;
  align-items: start;
}
.candidate-list {
  overflow: hidden;
}
.candidate-list > button {
  display: block;
  width: 100%;
  text-align: left;
  border: none;
  border-bottom: 1px solid var(--line);
  border-radius: 0;
  padding: 18px;
}
.candidate-list > button.selected {
  background: #f6f2ff;
  box-shadow: inset 3px 0 var(--primary);
}
.candidate-list strong {
  font-size: 12px;
  overflow-wrap: anywhere;
}
.candidate-list .badge {
  font-size: 10px;
  padding: 3px 5px;
}
.candidate-list p {
  color: var(--muted);
  font-size: 12px;
  margin-top: 8px;
}
.candidate-list small {
  color: var(--muted);
  font-size: 10px;
  display: block;
  margin-top: 4px;
}
.candidate-detail .card-head h3 {
  margin-top: 5px;
}
.candidate-content {
  padding: 22px;
}
.candidate-meta {
  display: flex;
  gap: 24px;
  flex-wrap: wrap;
}
.candidate-meta > span {
  display: grid;
  gap: 5px;
  font-size: 11px;
  color: var(--muted);
}
.candidate-meta strong {
  font-weight: 500;
  color: var(--ink);
  font-size: 12px;
  overflow-wrap: anywhere;
}
.mapping-diff {
  margin-top: 20px;
  display: grid;
  grid-template-columns: 1fr 20px 1fr;
  align-items: center;
  gap: 14px;
  padding: 18px;
  border: 1px solid var(--line);
  background: #fcfbff;
  border-radius: 8px;
}
.mapping-diff span {
  display: grid;
  gap: 6px;
}
.mapping-diff small {
  font-size: 11px;
  color: var(--muted);
}
.mapping-diff strong {
  font-size: 13px;
  font-weight: 500;
  overflow-wrap: anywhere;
}
.mapping-diff svg {
  color: var(--primary);
}
.evaluation-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  margin: 24px 0 12px;
}
h4 {
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 13px;
  font-weight: 600;
  margin: 0;
}
.evaluation-scores {
  display: flex;
  align-items: center;
  gap: 18px;
  padding: 17px;
  border: 1px solid var(--line);
  border-radius: 8px;
  margin-bottom: 14px;
}
.evaluation-scores > div {
  display: grid;
  gap: 6px;
}
.evaluation-scores span {
  font-size: 11px;
  color: var(--muted);
}
.evaluation-scores strong {
  font-size: 18px;
  font-weight: 600;
}
.evaluation-scores strong small {
  font-size: 12px;
  color: var(--muted);
  font-weight: 400;
}
.evaluation-scores > svg {
  color: var(--primary);
}
.evaluation-scores .score-scope {
  margin-left: auto;
  display: grid;
  gap: 6px;
}
.score-scope small {
  font-size: 10px;
}
.evaluation-issue {
  font-size: 12px;
  color: var(--red);
  padding: 7px 0;
  overflow-wrap: anywhere;
}
.evaluation-empty {
  color: var(--muted);
  font-size: 12px;
  padding: 14px 0;
}
.release-form {
  margin-top: 22px;
  border-top: 1px solid var(--line);
  padding-top: 20px;
  display: grid;
  gap: 15px;
}
.candidate-form {
  padding: 22px;
  display: grid;
  gap: 18px;
}
.form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}
label {
  display: grid;
  gap: 7px;
  font-size: 12px;
  color: var(--ink);
}
label small {
  color: var(--muted);
  font-size: 11px;
}
input,
select {
  font-size: 12px;
}
.check-line {
  display: flex;
  align-items: flex-start;
  gap: 9px;
  font-size: 12px;
  line-height: 1.8;
}
.check-line input {
  width: 15px;
  height: 15px;
  margin: 3px 0 0;
  flex-shrink: 0;
  accent-color: var(--primary);
}
.form-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
}
.form-footer p {
  font-size: 11px;
  color: var(--muted);
}
.report {
  margin-top: 16px;
}
.report summary {
  font-size: 12px;
  color: var(--muted);
  cursor: pointer;
}
.report pre {
  font-size: 11px;
  margin-top: 10px;
  max-height: 340px;
  overflow: auto;
}
.version-history {
  padding: 14px 20px;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
}
.version-history > span {
  margin-left: auto;
}
.version-history form {
  flex-basis: 100%;
  padding: 15px 0 5px;
  display: grid;
  gap: 16px;
}
.wide {
  grid-column: 1/-1;
}
.notice {
  font-size: 12px;
}
button {
  font-size: 12px;
}
@media (max-width: 1100px) {
  .improvement-grid {
    grid-template-columns: 240px minmax(0, 1fr);
  }
  .version-label {
    margin-left: 0;
  }
}
@media (max-width: 800px) {
  .improvement-grid {
    grid-template-columns: 1fr;
  }
  .form-grid {
    grid-template-columns: 1fr;
  }
  .candidate-content,
  .candidate-form {
    padding: 17px;
  }
  .form-footer {
    align-items: flex-start;
    flex-direction: column;
  }
  .version-history > span {
    margin-left: 0;
  }
}
</style>
