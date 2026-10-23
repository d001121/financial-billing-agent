<script setup lang="ts">
import { computed, defineAsyncComponent, onMounted, ref, watch } from "vue";
import {
  ArrowRight,
  BookOpen,
  Check,
  CircleAlert,
  FileText,
  History,
  LoaderCircle,
  Pause,
  Pencil,
  Search,
  Sparkles,
  X,
} from "@lucide/vue";
import { api, ApiError, errorMessage } from "../api/client";
import {
  formatDate,
  type ExperienceCard,
  type ExperienceReference,
  type ConfigDocument,
  type JsonObject,
  type Task,
} from "../types/contracts";

const MappingRules = defineAsyncComponent(
  () => import("./ImprovementPanel.vue"),
);
const props = defineProps<{ tasks: Task[]; initialTaskId?: string }>();
const tab = ref("experiences");
const cards = ref<ExperienceCard[]>([]);
const references = ref<ExperienceReference[]>([]);
const selectedId = ref("");
const taskId = ref(props.initialTaskId || "");
const source = ref<Task | null>(null);
const note = ref("");
const search = ref("");
const filter = ref("all");
const busy = ref("");
const loading = ref(true);
const sourceLoading = ref(false);
const error = ref("");
const notice = ref("");
const retryAvailable = ref(false);
const usageConfig = ref<ConfigDocument | null>(null);
const useExperiences = computed(
  () =>
    (usageConfig.value?.config as JsonObject | undefined)
      ?.use_reviewed_experiences !== false,
);
const editor = ref<ExperienceCard | null>(null);
const keywordText = ref("");
const confirmed = ref(false);
const selected = computed(() =>
  cards.value.find((card) => card.id === selectedId.value),
);
const selectedUses = computed(() =>
  references.value.filter((use) => use.experience_id === selectedId.value),
);
const filtered = computed(() =>
  cards.value.filter(
    (card) =>
      (filter.value === "all" || card.status === filter.value) &&
      `${card.title} ${card.problem} ${card.keywords.join(" ")} ${card.accounting_entity || ""}`
        .toLowerCase()
        .includes(search.value.toLowerCase().trim()),
  ),
);
const counts = computed(() => ({
  active: cards.value.filter((c) => c.status === "active").length,
  draft: cards.value.filter((c) => c.status === "draft").length,
  references: references.value.length,
}));
const statusLabel = (status: string) =>
  ({ draft: "待确认", active: "可参考", paused: "已停用" })[status] || status;

watch(
  () => props.initialTaskId,
  (id) => {
    if (id) taskId.value = id;
  },
);
watch(
  taskId,
  async (id) => {
    source.value = null;
    retryAvailable.value = false;
    if (!id) return;
    sourceLoading.value = true;
    try {
      const result = await api.task(id);
      if (taskId.value === id) source.value = result;
    } catch (e) {
      if (taskId.value === id) error.value = errorMessage(e);
    } finally {
      if (taskId.value === id) sourceLoading.value = false;
    }
  },
  { immediate: true },
);
watch([taskId, note], () => {
  retryAvailable.value = false;
});
watch(selectedId, () => {
  confirmed.value = false;
  editor.value = null;
});

async function load() {
  try {
    const [result, runtime] = await Promise.all([
      api.experiences(),
      api.config("runtime"),
    ]);
    usageConfig.value = runtime;
    cards.value = result.experiences
      .slice()
      .sort((a, b) => (b.created_at || "").localeCompare(a.created_at || ""));
    references.value = result.references;
    if (!selected.value) selectedId.value = cards.value[0]?.id || "";
  } catch (e) {
    error.value = errorMessage(e);
  } finally {
    loading.value = false;
  }
}
async function toggleUsage() {
  if (!usageConfig.value || busy.value) return;
  const enabled = !useExperiences.value;
  busy.value = "usage";
  error.value = "";
  notice.value = "";
  try {
    usageConfig.value = await api.saveConfig("runtime", {
      ...(usageConfig.value.config as JsonObject),
      version: usageConfig.value.version,
      use_reviewed_experiences: enabled,
    });
    notice.value = enabled
      ? "已开启，后续新任务可按需检索已确认经验。"
      : "已关闭，后续检索不会返回经验。经验卡片已保留。";
  } catch (e) {
    error.value = errorMessage(e);
    if (e instanceof ApiError && e.status === 409) {
      try {
        usageConfig.value = await api.config("runtime");
      } catch {
        /* Keep the save error visible. */
      }
    }
  } finally {
    busy.value = "";
  }
}
function select(card: ExperienceCard) {
  selectedId.value = card.id;
  notice.value = "";
}
async function summarize(retry = false) {
  if (!source.value || busy.value) return;
  const task = source.value;
  busy.value = "summary";
  error.value = "";
  notice.value = "";
  try {
    const result = await api.summarizeExperience({
      task_id: task.id,
      expected_revision: task.revision,
      note: note.value,
      retry_failed: retry,
    });
    await load();
    selectedId.value = result.experience.id;
    filter.value = "all";
    search.value = "";
    retryAvailable.value = false;
    notice.value = result.reused
      ? "已打开同一次总结，没有再次调用 AI。"
      : "AI 已整理为草稿。核对内容和适用范围后，再确认入库。";
  } catch (e) {
    error.value = errorMessage(e);
    retryAvailable.value =
      e instanceof ApiError &&
      !!(e.details as { retry_available?: boolean })?.retry_available;
    if (e instanceof ApiError && e.status === 409) {
      try {
        source.value = await api.task(task.id);
      } catch {
        /* Keep the original actionable error. */
      }
    }
  } finally {
    busy.value = "";
  }
}
async function review(card: ExperienceCard, action: "activate" | "pause") {
  if (busy.value || (action === "activate" && !confirmed.value)) return;
  busy.value = card.id;
  error.value = "";
  notice.value = "";
  try {
    await api.reviewExperience(card, action);
    await load();
    confirmed.value = false;
    notice.value =
      action === "activate"
        ? "已确认入库，供后续同主体的新任务参考。"
        : "已停用，后续检索不再返回这条经验。";
  } catch (e) {
    error.value = errorMessage(e);
  } finally {
    busy.value = "";
  }
}
function edit(card: ExperienceCard) {
  editor.value = { ...card, keywords: [...card.keywords] };
  keywordText.value = card.keywords.join("、");
}
async function save() {
  if (!editor.value || busy.value) return;
  busy.value = "edit";
  error.value = "";
  try {
    const card = editor.value;
    await api.editExperience(card.id, {
      expected_revision: card.revision,
      title: card.title,
      problem: card.problem,
      applicability: card.applicability,
      recommendation: card.recommendation,
      exceptions: card.exceptions,
      keywords: keywordText.value
        .split(/[,，、\n]/)
        .map((word) => word.trim())
        .filter(Boolean),
    });
    editor.value = null;
    confirmed.value = false;
    await load();
    notice.value = "已保存为待确认草稿。";
  } catch (e) {
    error.value = errorMessage(e);
  } finally {
    busy.value = "";
  }
}
onMounted(load);
</script>

<template>
  <div class="experience-library">
    <div class="library-tabs" role="tablist" aria-label="进化库内容">
      <button
        id="experience-tab"
        role="tab"
        :aria-selected="tab === 'experiences'"
        :class="{ active: tab === 'experiences' }"
        @click="tab = 'experiences'"
      >
        <BookOpen :size="16" />参考经验
      </button>
      <button
        id="rules-tab"
        role="tab"
        :aria-selected="tab === 'rules'"
        :class="{ active: tab === 'rules' }"
        @click="tab = 'rules'"
      >
        <History :size="16" />执行规则
      </button>
    </div>
    <MappingRules
      v-if="tab === 'rules'"
      :tasks="tasks"
      :initial-task-id="initialTaskId"
    />
    <div v-else role="tabpanel" aria-labelledby="experience-tab">
      <section class="library-intro card">
        <div class="intro-copy">
          <span class="library-kicker">从一次纠错开始积累</span>
          <h2>让下一张账单，参考这一次的经验</h2>
          <p>
            选一张已核对的账单，让 AI
            整理。你看过并确认后，才供后续同主体的任务参考。
          </p>
          <div class="library-steps">
            <span><b>1</b>选择账单</span><ArrowRight :size="14" /><span
              ><b>2</b>AI 整理草稿</span
            ><ArrowRight :size="14" /><span><b>3</b>确认入库</span>
          </div>
        </div>
        <dl class="library-stats">
          <div>
            <dt>可参考经验</dt>
            <dd>{{ counts.active }}</dd>
          </div>
          <div>
            <dt>待确认</dt>
            <dd>{{ counts.draft }}</dd>
          </div>
          <div>
            <dt>任务检索记录</dt>
            <dd>{{ counts.references }}</dd>
          </div>
        </dl>
      </section>
      <section class="usage-control card" aria-labelledby="usage-title">
        <div>
          <h3 id="usage-title">使用已确认经验</h3>
          <p id="usage-description">
            {{
              !usageConfig
                ? "正在读取使用设置…"
                : useExperiences
                  ? "已开启：后续同主体的新任务可按需检索经验。"
                  : "已关闭：Agent 不再检索经验，仍可整理和保存草稿。"
            }}
          </p>
          <small
            >已进入模型上下文的经验无法撤回；重新开启只为新任务加入经验。</small
          >
        </div>
        <button
          class="usage-switch"
          role="switch"
          :aria-checked="useExperiences"
          aria-labelledby="usage-title"
          aria-describedby="usage-description"
          :disabled="!usageConfig || !!busy"
          @click="toggleUsage"
        >
          <span class="switch-track" aria-hidden="true"><span /></span>
          <span>{{
            !usageConfig ? "读取中…" : useExperiences ? "已开启" : "已关闭"
          }}</span>
        </button>
      </section>
      <div v-if="error" class="notice error" role="alert">
        <CircleAlert :size="16" />{{ error }}
      </div>
      <div v-if="notice" class="notice" role="status">
        <Check :size="16" />{{ notice }}
      </div>
      <section class="summary-card card" aria-labelledby="summary-title">
        <div class="section-heading">
          <span class="sparkle-icon"><Sparkles :size="20" /></span>
          <div>
            <h3 id="summary-title">AI 总结这次纠错</h3>
            <p>选择一张账单，让 AI 从修改记录和原文中总结经验。</p>
          </div>
        </div>
        <div class="summary-fields">
          <div class="summary-source">
            <label for="summary-task">来源账单</label>
            <select
              id="summary-task"
              v-model="taskId"
              :disabled="!!busy"
              aria-describedby="summary-source-status"
            >
              <option value="">选择已核对或已修改的账单</option>
              <option v-for="task in tasks" :key="task.id" :value="task.id">
                {{ task.title || task.id }} ·
                {{ task.accounting_entity || "未提供主体" }}
              </option>
            </select>
            <div
              id="summary-source-status"
              class="source-status"
              aria-live="polite"
            >
              <LoaderCircle
                v-if="sourceLoading"
                class="loading-icon"
                :size="14"
              />
              <FileText v-else :size="14" />
              <p v-if="sourceLoading">正在读取来源账单…</p>
              <p v-else-if="source">
                <span
                  >来源版本 R{{ source.revision }} ·
                  {{ source.accounting_entity || "未提供主体" }}</span
                >
                <small v-if="!source.accounting_entity"
                  >可生成草稿，补充主体后才能启用。</small
                >
              </p>
              <p v-else>自动带入修改记录、原文引用和适用主体。</p>
            </div>
          </div>
          <div class="summary-note">
            <div class="summary-label">
              <label for="summary-note">想让 AI 特别记住什么</label>
              <span class="optional">选填</span>
            </div>
            <textarea
              id="summary-note"
              v-model="note"
              :disabled="!!busy"
              maxlength="2000"
              rows="3"
              aria-describedby="summary-note-hint"
              placeholder="例如：条件性收费不能直接当作已发生费用。"
            />
            <div id="summary-note-hint" class="note-hint">
              <span>留空也可以，AI 会从修改记录中总结。</span>
              <span class="note-count">{{ note.length }} / 2000</span>
            </div>
          </div>
        </div>
        <div class="summary-footer">
          <p><BookOpen :size="14" />生成后可编辑，确认后才会加入可参考经验。</p>
          <button
            v-if="retryAvailable"
            class="ghost"
            :disabled="!!busy || !source"
            @click="summarize(true)"
          >
            重试 AI 总结</button
          ><button
            v-else
            class="primary"
            :disabled="!!busy || !source || sourceLoading"
            @click="summarize()"
          >
            <LoaderCircle
              v-if="busy === 'summary'"
              class="loading-icon"
              :size="15"
            /><Sparkles v-else :size="15" />{{
              busy === "summary" ? "正在总结…" : "生成经验草稿"
            }}
          </button>
        </div>
      </section>

      <section class="library-content" aria-label="经验库">
        <div class="library-list card">
          <div class="list-heading">
            <h3>
              我的经验库 <small>{{ cards.length }}</small>
            </h3>
            <button
              class="ghost"
              :disabled="!!busy"
              @click="
                error = '';
                load();
              "
            >
              刷新
            </button>
          </div>
          <label class="library-search"
            ><Search :size="15" /><input
              v-model="search"
              placeholder="搜索问题、关键词或公司"
              aria-label="搜索经验"
          /></label>
          <div class="status-filters" aria-label="经验状态">
            <button
              v-for="item in [
                { value: 'all', label: '全部' },
                { value: 'draft', label: '待确认' },
                { value: 'active', label: '可参考' },
                { value: 'paused', label: '已停用' },
              ]"
              :key="item.value"
              :class="{ active: filter === item.value }"
              :aria-pressed="filter === item.value"
              @click="filter = item.value"
            >
              {{ item.label }}
            </button>
          </div>
          <p v-if="loading" class="library-empty">正在读取经验库…</p>
          <div v-else-if="!filtered.length" class="library-empty">
            <BookOpen :size="28" /><strong>{{
              cards.length ? "没有匹配的经验" : "把第一次纠错留给下一次"
            }}</strong>
            <p>
              {{
                cards.length
                  ? "换一个关键词或状态试试。"
                  : "从上方选择账单并生成草稿，确认后就会出现在这里。"
              }}
            </p>
          </div>
          <button
            v-for="card in filtered"
            :key="card.id"
            class="experience-row"
            :class="{ selected: selectedId === card.id }"
            :aria-pressed="selectedId === card.id"
            @click="select(card)"
          >
            <div>
              <span :class="['experience-status', card.status]">{{
                statusLabel(card.status)
              }}</span
              ><small>{{ formatDate(card.created_at) }}</small>
            </div>
            <strong>{{ card.title }}</strong>
            <p>{{ card.problem }}</p>
            <span class="row-entity">{{
              card.accounting_entity || "未提供主体"
            }}</span>
          </button>
        </div>

        <article v-if="selected" class="experience-detail card">
          <header>
            <div>
              <span :class="['experience-status', selected.status]">{{
                statusLabel(selected.status)
              }}</span
              ><span class="card-version"
                >经验版本 {{ selected.revision }}</span
              >
            </div>
            <button
              v-if="selected.status !== 'active' && !editor"
              class="ghost"
              :disabled="!!busy"
              @click="edit(selected)"
            >
              <Pencil :size="14" />修改内容
            </button>
          </header>
          <form v-if="editor" class="experience-editor" @submit.prevent="save">
            <label
              >学到了什么<input
                v-model="editor.title"
                required
                maxlength="80" /></label
            ><label
              >这次发现的问题<textarea
                v-model="editor.problem"
                required
                maxlength="400"
                rows="2"
              /></label
            ><label
              >什么时候参考<textarea
                v-model="editor.applicability"
                required
                maxlength="400"
                rows="2"
              /></label
            ><label
              >建议怎么处理<textarea
                v-model="editor.recommendation"
                required
                maxlength="700"
                rows="3"
              /></label
            ><label
              >不适用情况<textarea
                v-model="editor.exceptions"
                required
                maxlength="400"
                rows="2"
              /></label
            ><label
              >检索关键词<input
                v-model="keywordText"
                required
                placeholder="用顿号分隔"
            /></label>
            <div class="detail-actions">
              <button
                type="button"
                class="ghost"
                :disabled="!!busy"
                @click="editor = null"
              >
                <X :size="14" />取消</button
              ><button type="submit" class="primary" :disabled="!!busy">
                保存草稿
              </button>
            </div>
          </form>
          <template v-else
            ><h2>{{ selected.title }}</h2>
            <dl class="experience-sections">
              <div>
                <dt>这次发现的问题</dt>
                <dd>{{ selected.problem }}</dd>
              </div>
              <div>
                <dt>什么时候参考</dt>
                <dd>{{ selected.applicability }}</dd>
              </div>
              <div class="recommendation">
                <dt>建议怎么处理</dt>
                <dd>{{ selected.recommendation }}</dd>
              </div>
              <div>
                <dt>不适用情况</dt>
                <dd>{{ selected.exceptions }}</dd>
              </div>
            </dl>
            <div class="keyword-tags">
              <span v-for="word in selected.keywords" :key="word">{{
                word
              }}</span>
            </div>
            <div class="source-binding">
              <FileText :size="16" />
              <div>
                <strong
                  >适用主体：{{
                    selected.accounting_entity || "未提供"
                  }}</strong
                >
                <p>
                  来源
                  <a
                    :href="`#/tasks/${encodeURIComponent(selected.source.task_id)}`"
                    >{{ selected.source.title || "原账单" }}</a
                  >
                  · R{{ selected.source.revision }}
                </p>
              </div>
            </div>
            <details v-if="selected.source_refs.length" class="source-quotes">
              <summary>
                查看总结时的原文引用（{{ selected.source_refs.length }}）
              </summary>
              <blockquote
                v-for="(ref, index) in selected.source_refs"
                :key="index"
              >
                <small>{{ ref.source_id }} {{ ref.anchor || "" }}</small>
                <p>{{ ref.quote }}</p>
              </blockquote>
            </details>
            <div class="review-box" v-if="selected.status !== 'active'">
              <p>
                这条经验只提供核对建议。当前单据没有的金额、币种和单号，仍然留空。
              </p>
              <label
                ><input
                  v-model="confirmed"
                  type="checkbox"
                  :disabled="!!busy"
                />我已核对内容，确认适用于上述记账主体</label
              ><button
                class="primary"
                :disabled="!!busy || !confirmed || !selected.accounting_entity"
                @click="review(selected, 'activate')"
              >
                <Check :size="15" />确认入库，供新任务参考</button
              ><small v-if="!selected.accounting_entity"
                >来源账单缺少主体，请先补充，再重新生成经验。</small
              >
            </div>
            <div v-else class="active-experience">
              <span><Check :size="16" />后续同主体的新任务可按需检索</span
              ><button
                class="ghost"
                :disabled="!!busy"
                @click="review(selected, 'pause')"
              >
                <Pause :size="14" />停用经验
              </button>
            </div>
          </template>
          <section class="reference-history">
            <h3><History :size="16" />被哪些任务参考过</h3>
            <p class="reference-note">
              记录检索工具实际返回的经验；不代表已采纳或正确率。
            </p>
            <p v-if="!selectedUses.length" class="no-references">
              还没有任务检索记录。
            </p>
            <a
              v-for="use in selectedUses"
              :key="use.id"
              :href="`#/tasks/${encodeURIComponent(use.task_id)}`"
              ><span
                >{{ use.task_title || "查看账单" }} · R{{ use.task_revision
                }}<small>检索：{{ use.query }}</small></span
              ><small>{{ formatDate(use.at) }}</small></a
            >
          </section>
        </article>
        <div v-else class="detail-placeholder card">
          <Sparkles :size="30" />
          <h3>先让 AI 整理，再决定记住什么</h3>
          <p>
            草稿会说明问题、适用情况、处理方法和边界。你确认后，模型才能在新任务中参考。
          </p>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.experience-library {
  display: grid;
  gap: 20px;
}
.library-tabs {
  display: flex;
  gap: 6px;
  border-bottom: 1px solid var(--line);
  padding-bottom: 12px;
}
.library-tabs button {
  background: transparent;
  border-color: transparent;
  color: var(--muted);
}
.library-tabs button.active {
  color: var(--primary, #2563eb);
  background: #eff6ff;
  border-color: #dbeafe;
}
.library-intro {
  padding: 26px;
  display: flex;
  justify-content: space-between;
  gap: 28px;
  align-items: center;
  margin-bottom: 18px;
}
.library-kicker {
  font-size: 12px;
  color: #527269;
  font-weight: 650;
}
.intro-copy h2 {
  font-size: 22px;
  line-height: 1.4;
  margin: 7px 0;
}
.intro-copy p,
.section-heading p {
  color: var(--muted);
  font-size: 13px;
  line-height: 1.7;
  margin: 0;
}
.library-steps {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
  margin-top: 18px;
  font-size: 12px;
  color: #5c6c7d;
}
.library-steps span {
  display: flex;
  gap: 7px;
  align-items: center;
}
.library-steps b {
  display: grid;
  place-items: center;
  border-radius: 50%;
  background: #edf2f7;
  width: 22px;
  height: 22px;
  font-size: 11px;
}
.library-stats {
  display: flex;
  gap: 24px;
  flex-shrink: 0;
  margin: 0;
}
.library-stats dt {
  font-size: 11px;
  color: var(--muted);
}
.library-stats dd {
  font-size: 27px;
  font-weight: 650;
  margin: 7px 0 0;
}
.summary-card {
  padding: 22px;
  margin-bottom: 22px;
}
.usage-control {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  padding: 18px 22px;
  margin-bottom: 18px;
}
.usage-control h3 {
  margin: 0 0 7px;
  font-size: 14px;
}
.usage-control p {
  margin: 0;
  font-size: 12px;
  line-height: 1.7;
}
.usage-control small {
  color: var(--muted);
  font-size: 11px;
  line-height: 1.8;
}
.usage-switch {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
  padding: 10px;
  background: transparent;
  border: 0;
  box-shadow: none;
  font-size: 12px;
}
.switch-track {
  width: 38px;
  padding: 3px;
  border-radius: 20px;
  background: #94a3b8;
}
.switch-track > span {
  display: block;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: white;
  transition: transform 0.15s;
}
.usage-switch[aria-checked="true"] .switch-track {
  background: #306d54;
}
.usage-switch[aria-checked="true"] .switch-track > span {
  transform: translateX(22px);
}
.usage-switch:focus-visible {
  outline: 2px solid #4778a9;
  outline-offset: 2px;
}
.section-heading {
  display: flex;
  gap: 12px;
  align-items: center;
  margin-bottom: 18px;
}
.section-heading h3 {
  margin: 0 0 4px;
  font-size: 15px;
}
.sparkle-icon {
  display: grid;
  place-items: center;
  width: 40px;
  height: 40px;
  border-radius: 12px;
  flex-shrink: 0;
  background: var(--primary-soft);
  color: var(--primary);
}
.summary-fields {
  display: grid;
  grid-template-columns: minmax(200px, 0.8fr) minmax(240px, 1.4fr);
  gap: 24px;
  align-items: start;
}
.summary-source,
.summary-note {
  display: grid;
  gap: 10px;
  min-width: 0;
}
.summary-label {
  display: flex;
  align-items: center;
  gap: 8px;
}
.summary-fields label {
  font-size: 12px;
  line-height: 20px;
  font-weight: 600;
}
.experience-editor label {
  display: grid;
  gap: 8px;
  font-size: 12px;
  font-weight: 600;
}
.summary-fields select,
.summary-fields textarea,
.experience-editor input,
.experience-editor textarea {
  width: 100%;
  box-sizing: border-box;
  font: inherit;
  font-weight: 400;
}
.optional {
  font-size: 11px;
  color: var(--muted);
  font-weight: 400;
  line-height: 20px;
}
.summary-fields select {
  height: 44px;
  min-width: 0;
  padding-right: 28px;
  text-overflow: ellipsis;
}
.summary-fields textarea {
  min-height: 104px;
  line-height: 1.7;
}
.summary-fields textarea::placeholder {
  color: var(--muted);
}
.source-status {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 10px 12px;
  border-radius: 8px;
  background: #f5f8f6;
  color: #63786f;
  font-size: 12px;
  line-height: 1.7;
  overflow-wrap: anywhere;
}
.source-status > svg {
  margin-top: 3px;
}
.source-status p {
  margin: 0;
}
.source-status small {
  display: block;
  font-size: 11px;
  color: var(--muted);
}
.note-hint {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  color: var(--muted);
  font-size: 11px;
  line-height: 1.7;
}
.note-count {
  flex-shrink: 0;
  font-variant-numeric: tabular-nums;
}
.summary-footer {
  display: flex;
  gap: 12px;
  align-items: center;
  justify-content: space-between;
  margin-top: 20px;
  border-top: 1px solid var(--line);
  padding-top: 16px;
}
.summary-footer p {
  display: flex;
  gap: 6px;
  align-items: center;
  color: var(--muted);
  font-size: 12px;
  margin: 0;
}
.summary-footer button {
  min-height: 42px;
  flex-shrink: 0;
}
.library-content {
  display: grid;
  grid-template-columns: minmax(250px, 340px) minmax(0, 1fr);
  gap: 20px;
  align-items: start;
}
.library-list {
  overflow: hidden;
  padding: 18px 0;
}
.list-heading {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 18px 12px;
}
.list-heading h3 {
  margin: 0;
  font-size: 15px;
}
.list-heading h3 small {
  margin-left: 7px;
  color: var(--muted);
  font-size: 12px;
}
.library-search {
  display: flex;
  align-items: center;
  gap: 8px;
  border: 1px solid var(--line);
  border-radius: 8px;
  margin: 0 18px;
  padding: 0 10px;
  color: var(--muted);
}
.library-search input {
  min-width: 0;
  width: 100%;
  border: 0;
  background: transparent;
  box-shadow: none;
  padding: 10px 0;
  font-size: 12px;
}
.status-filters {
  display: flex;
  gap: 5px;
  padding: 12px 18px;
}
.status-filters button {
  padding: 5px 8px;
  font-size: 11px;
  border: 0;
  box-shadow: none;
  background: transparent;
  color: var(--muted);
}
.status-filters button.active {
  color: #285e83;
  background: #edf4fb;
}
.experience-row {
  width: 100%;
  display: block;
  text-align: left;
  border: 0;
  border-radius: 0;
  box-shadow: none;
  background: transparent;
  padding: 17px 20px;
  border-left: 3px solid transparent;
  border-top: 1px solid #f0f2f5;
  white-space: normal;
}
.experience-row.selected {
  background: #f3f7fc;
  border-left-color: #4778a9;
}
.experience-row > div {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}
.experience-row strong {
  display: block;
  font-size: 14px;
  line-height: 1.55;
  margin-top: 10px;
}
.experience-row p {
  font-size: 12px;
  line-height: 1.7;
  color: var(--muted);
  margin: 5px 0 8px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.experience-row small,
.row-entity {
  font-size: 10px;
  color: var(--muted);
}
.experience-status {
  display: inline-flex;
  font-size: 10px;
  padding: 3px 7px;
  border-radius: 5px;
  font-weight: 600;
  background: #fff5df;
  color: #8b6420;
}
.experience-status.active {
  color: #306d54;
  background: #eaf5ee;
}
.experience-status.paused {
  color: #64748b;
  background: #eef1f5;
}
.experience-detail {
  padding: 24px;
  min-width: 0;
}
.experience-detail > header {
  display: flex;
  gap: 12px;
  justify-content: space-between;
  align-items: center;
}
.card-version {
  font-size: 11px;
  color: var(--muted);
  margin-left: 10px;
}
.experience-detail h2 {
  font-size: 21px;
  line-height: 1.5;
  margin: 20px 0;
}
.experience-sections {
  display: grid;
  gap: 20px;
  margin: 0;
}
.experience-sections dt {
  font-size: 11px;
  color: var(--muted);
  margin-bottom: 7px;
}
.experience-sections dd {
  font-size: 13px;
  line-height: 1.9;
  margin: 0;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
.experience-sections .recommendation {
  padding: 16px;
  background: #f1f6fb;
  border-radius: 9px;
}
.recommendation dt {
  color: #42688c;
}
.keyword-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
  margin: 20px 0;
}
.keyword-tags span {
  font-size: 10px;
  padding: 4px 8px;
  background: #f3f5f7;
  color: #607083;
  border-radius: 4px;
}
.source-binding {
  display: flex;
  gap: 10px;
  align-items: start;
  background: #fafbfc;
  padding: 14px;
  border: 1px solid var(--line);
  border-radius: 8px;
  font-size: 12px;
}
.source-binding strong {
  font-size: 11px;
  font-weight: 500;
}
.source-binding p {
  font-size: 11px;
  color: var(--muted);
  margin: 6px 0 0;
}
.source-quotes {
  font-size: 11px;
  color: var(--muted);
  margin: 16px 0;
}
.source-quotes summary {
  cursor: pointer;
}
.source-quotes blockquote {
  border-left: 2px solid #dbe4ef;
  padding-left: 12px;
  margin: 14px 0;
}
.source-quotes p {
  line-height: 1.8;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
.review-box {
  background: #f7f9fc;
  padding: 16px;
  border-radius: 9px;
  display: grid;
  gap: 13px;
  margin-top: 20px;
}
.review-box p {
  font-size: 12px;
  line-height: 1.8;
  color: var(--muted);
  margin: 0;
}
.review-box label {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  font-size: 12px;
  line-height: 1.6;
}
.review-box input {
  width: auto;
  flex-shrink: 0;
}
.review-box button {
  justify-self: start;
}
.review-box small {
  font-size: 11px;
  color: #926527;
}
.active-experience {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin: 20px 0;
  font-size: 12px;
  color: #306d54;
}
.active-experience span {
  display: flex;
  gap: 7px;
  align-items: center;
}
.reference-history {
  border-top: 1px solid var(--line);
  margin-top: 24px;
  padding-top: 20px;
}
.reference-history h3 {
  font-size: 13px;
  display: flex;
  gap: 7px;
  align-items: center;
  margin: 0;
}
.reference-note,
.no-references {
  font-size: 11px;
  line-height: 1.8;
  color: var(--muted);
}
.reference-history > a {
  display: flex;
  gap: 12px;
  align-items: center;
  justify-content: space-between;
  padding: 12px 0;
  border-top: 1px solid #f0f2f5;
  font-size: 12px;
  text-decoration: none;
  color: inherit;
}
.reference-history > a small {
  display: block;
  color: var(--muted);
  font-size: 10px;
  line-height: 1.8;
}
.experience-editor {
  display: grid;
  gap: 14px;
  margin-top: 18px;
}
.detail-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}
.library-empty,
.detail-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  gap: 12px;
  padding: 38px 24px;
  color: var(--muted);
  font-size: 12px;
  line-height: 1.8;
}
.library-empty strong {
  color: inherit;
}
.library-empty p,
.detail-placeholder p {
  margin: 0;
}
.detail-placeholder {
  padding: 60px 38px;
}
.detail-placeholder h3 {
  font-size: 15px;
  margin: 0;
  color: var(--ink);
}
.experience-library .notice {
  margin-bottom: 18px;
}
button:disabled {
  cursor: default;
}
.experience-row:focus-visible {
  outline: 2px solid #4778a9;
  outline-offset: -3px;
}
@media (max-width: 1100px) {
  .library-intro {
    align-items: flex-start;
    flex-direction: column;
  }
  .library-stats {
    gap: 36px;
  }
  .library-content {
    grid-template-columns: 280px minmax(0, 1fr);
  }
}
@media (max-width: 760px) {
  .library-intro,
  .summary-card,
  .experience-detail {
    padding: 18px;
  }
  .intro-copy h2 {
    font-size: 19px;
  }
  .summary-fields,
  .library-content {
    grid-template-columns: 1fr;
  }
  .library-stats {
    gap: 25px;
  }
  .library-steps {
    gap: 8px;
  }
  .summary-footer,
  .usage-control,
  .active-experience {
    align-items: flex-start;
    flex-direction: column;
  }
  .summary-footer button {
    width: 100%;
  }
  .detail-placeholder {
    padding: 35px 22px;
  }
  .experience-row {
    padding: 14px 18px;
  }
}
</style>
