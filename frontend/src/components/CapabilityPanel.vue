<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import {
  Blocks,
  BookOpen,
  CircleAlert,
  Code,
  FileCode,
  GitBranch,
  LoaderCircle,
  Plug,
  RefreshCw,
  Save,
  Settings2,
  ShieldCheck,
} from "@lucide/vue";
import { ApiError, api, errorMessage } from "../api/client";
import type { ConfigDocument, JsonObject } from "../types/contracts";
import CapabilityActions from "./CapabilityActions.vue";
const actions = ref<InstanceType<typeof CapabilityActions>>();
function savedDocument(value: ConfigDocument) {
  documents.value[active.value] = value;
  loadEditor();
}
const kinds = [
  {
    id: "agents",
    name: "智能体",
    en: "AGENTS",
    icon: GitBranch,
    description: "主控与专家分工、工具授权及模型设置。",
  },
  {
    id: "skills",
    name: "业务技能",
    en: "SKILLS",
    icon: BookOpen,
    description: "可移植的业务能力包，按任务固定技能版本。",
  },
  {
    id: "mcp",
    name: "MCP 服务",
    en: "CONNECTIONS",
    icon: Plug,
    description: "按配置接入外部工具，在调用边界检查可用状态。",
  },
  {
    id: "hooks",
    name: "校验 Hook",
    en: "VALIDATION",
    icon: ShieldCheck,
    description: "独立配置每项校验，统一装配与管理。",
  },
  {
    id: "runtime",
    name: "运行参数",
    en: "RUNTIME",
    icon: Settings2,
    description: "调整预算、并发与运行时策略。",
  },
];
const active = ref("skills"),
  documents = ref<Record<string, ConfigDocument>>({}),
  editor = ref(""),
  loading = ref(true),
  saving = ref(false),
  error = ref(""),
  success = ref(""),
  conflict = ref(false),
  view = ref("overview");
const current = computed(() => documents.value[active.value]),
  definition = computed(() => kinds.find((k) => k.id === active.value)!);
const entries = computed<JsonObject[]>(() => {
  let config = current.value?.config;
  try {
    config = JSON.parse(editor.value);
  } catch {
    /* Keep the last valid overview while editing JSON. */
  }
  if (!config || typeof config !== "object") return [];
  return Object.entries(config as JsonObject).flatMap(([key, value]) =>
    Array.isArray(value)
      ? value
          .filter((v) => v && typeof v === "object")
          .map((v, i) => ({ ...(v as JsonObject), _key: key + "-" + i }))
      : [],
  );
});
const changed = computed(
  () => editor.value !== JSON.stringify(current.value?.config, null, 2),
);
function loadEditor() {
  editor.value = JSON.stringify(current.value?.config || {}, null, 2);
  error.value = "";
  success.value = "";
  conflict.value = false;
}
async function load() {
  loading.value = true;
  error.value = "";
  const results = await Promise.allSettled(kinds.map((k) => api.config(k.id)));
  const errors: string[] = [];
  results.forEach((r, i) => {
    if (r.status === "fulfilled") documents.value[kinds[i]!.id] = r.value;
    else errors.push(kinds[i]!.name + "：" + errorMessage(r.reason));
  });
  loadEditor();
  error.value = errors.join("；");
  loading.value = false;
}
function select(kind: string) {
  active.value = kind;
  loadEditor();
}
async function save() {
  error.value = "";
  success.value = "";
  let config: unknown;
  try {
    config = JSON.parse(editor.value);
    if (!config || typeof config !== "object" || Array.isArray(config))
      throw Error();
  } catch {
    error.value = "配置需要是有效的 JSON 对象。";
    return;
  }
  saving.value = true;
  try {
    documents.value[active.value] = await api.saveConfig(active.value, {
      expected_version: current.value?.version,
      config,
    });
    loadEditor();
    success.value =
      "配置已保存，新任务会使用新版本。在途任务仍使用其固定快照。";
  } catch (e) {
    conflict.value = e instanceof ApiError && e.status === 409;
    error.value = conflict.value
      ? "配置版本已更新。当前编辑已保留，请复制您的改动并重新载入后合并。"
      : errorMessage(e);
  } finally {
    saving.value = false;
  }
}
async function toggle(entry: JsonObject) {
  if (!current.value) return;
  let config: JsonObject;
  try {
    config = JSON.parse(editor.value);
    if (!config || typeof config !== "object" || Array.isArray(config))
      throw Error();
  } catch {
    error.value = "配置 JSON 当前无效，请先修正后再调整启停。";
    view.value = "json";
    return;
  }
  const key = String(entry._key);
  const idx = key.lastIndexOf("-");
  const list = config[key.slice(0, idx)] as JsonObject[];
  if (!Array.isArray(list)) return;
  const item = list[Number(key.slice(idx + 1))];
  if (!item) return;
  item.enabled = item.enabled === false;
  editor.value = JSON.stringify(config, null, 2);
  await save();
}
onMounted(() => void load());
</script>
<template>
  <div class="capability-page">
    <div class="notice">
      <Blocks :size="16" /><span
        >能力配置由服务端统一管理。运行中任务固定能力快照；工具禁用在实际派发时仍会被检查。</span
      >
    </div>
    <div class="capability-layout">
      <aside class="capability-nav card">
        <button
          v-for="kind in kinds"
          :key="kind.id"
          :class="{ active: active === kind.id }"
          @click="select(kind.id)"
        >
          <component :is="kind.icon" /><span
            >{{ kind.name }}<small>{{ kind.en }}</small></span
          ><span class="version" v-if="documents[kind.id]"
            >v{{ documents[kind.id]?.version }}</span
          >
        </button>
      </aside>
      <section class="capability-content card">
        <div class="card-head">
          <div class="flex">
            <span class="capability-symbol"
              ><component :is="definition.icon"
            /></span>
            <div>
              <h2>{{ definition.name }}</h2>
              <p>{{ definition.description }}</p>
            </div>
          </div>
          <button class="ghost" :disabled="loading" @click="load">
            <RefreshCw
              :size="14"
              :class="{ 'loading-icon': loading }"
            />重新载入
          </button>
        </div>
        <div class="tabs">
          <button
            :class="{ active: view === 'overview' }"
            @click="view = 'overview'"
          >
            能力概览</button
          ><button :class="{ active: view === 'json' }" @click="view = 'json'">
            配置 JSON<span v-if="changed"> · 未保存</span>
          </button>
        </div>
        <div class="card-body">
          <div v-if="error" class="notice error" role="alert">{{ error }}</div>
          <div v-if="success" class="notice">{{ success }}</div>
          <div v-if="loading" class="empty">
            <LoaderCircle class="loading-icon" />
            <h3>读取当前能力配置</h3>
          </div>
          <template v-else-if="current"
            ><CapabilityActions
              v-if="view === 'overview'"
              ref="actions"
              :kind="active"
              :document="current"
              @saved="savedDocument"
            />
            <div v-if="view === 'overview'" class="capability-cards">
              <template v-if="entries.length"
                ><article
                  v-for="entry in entries"
                  :key="String(entry._key)"
                  class="capability-item"
                >
                  <div class="flex between">
                    <span class="capability-item-icon"
                      ><component :is="definition.icon" :size="17" /></span
                    ><button
                      v-if="'enabled' in entry"
                      :class="['toggle', { enabled: entry.enabled !== false }]"
                      :aria-label="
                        (entry.enabled !== false ? '停用' : '启用') +
                        String(entry.name || entry.id || entry._key)
                      "
                      :aria-pressed="entry.enabled !== false"
                      :disabled="saving"
                      @click="toggle(entry)"
                    >
                      <span /></button
                    ><span v-else class="small muted">配置项</span>
                  </div>
                  <h3>{{ entry.name || entry.id || entry._key }}</h3>
                  <p>
                    {{
                      entry.description ||
                      entry.type ||
                      entry.handler ||
                      entry.path ||
                      "由服务端配置提供能力"
                    }}
                  </p>
                  <div
                    class="flex"
                    style="gap: 8px; flex-wrap: wrap; margin: 12px 0"
                  >
                    <button
                      v-if="!entry.native"
                      class="ghost"
                      @click="actions?.edit(entry)"
                    >
                      编辑
                    </button>
                    <button
                      v-if="active === 'skills'"
                      class="ghost"
                      @click="actions?.inspect(entry)"
                    >
                      查看资源
                    </button>
                    <button
                      v-if="active === 'mcp'"
                      class="ghost"
                      @click="actions?.probe(entry)"
                    >
                      连接与工具
                    </button>
                    <button
                      v-if="!entry.required && !entry.native"
                      class="ghost"
                      @click="actions?.remove(entry)"
                    >
                      移除
                    </button>
                  </div>
                  <div class="capability-item-foot">
                    <code>{{
                      entry.version ? "v" + entry.version : definition.en
                    }}</code
                    ><span
                      :class="[
                        'badge',
                        entry.enabled === false ? 'paused' : 'completed',
                      ]"
                      >{{
                        changed
                          ? entry.enabled === false
                            ? "未保存 · 停用"
                            : "未保存 · 启用"
                          : entry.enabled === false
                            ? "已停用"
                            : "已配置"
                      }}</span
                    >
                  </div>
                </article></template
              >
              <div v-else-if="active !== 'runtime'" class="config-overview">
                <Blocks />
                <h3>尚未注册{{ definition.name }}</h3>
                <p>使用上方新增入口接入能力，保存后供新任务使用。</p>
              </div>
              <div v-else class="config-overview">
                <FileCode />
                <h3>运行配置 v{{ current.version }}</h3>
                <p>此配置以结构化参数提供，打开 JSON 编辑区查看和修改。</p>
                <button @click="view = 'json'">
                  <Code :size="14" />查看配置
                </button>
              </div>
            </div>
            <div v-else class="json-editor">
              <div class="editor-label">
                <span>{{ active }}.json</span
                ><span>Version {{ current.version }}</span>
              </div>
              <textarea
                v-model="editor"
                spellcheck="false"
                class="mono"
                aria-label="能力配置JSON"
              />
              <div class="editor-foot">
                <span>服务端会检查配置结构与必需校验项。</span
                ><button
                  class="primary"
                  :disabled="saving || !changed || conflict"
                  @click="save"
                >
                  <LoaderCircle v-if="saving" class="loading-icon" /><Save
                    v-else
                    :size="14"
                  />{{ saving ? "保存中…" : "保存配置" }}
                </button>
              </div>
            </div></template
          >
          <div v-else class="empty">
            <CircleAlert />
            <h3>配置暂不可用</h3>
            <p>连接后端后重新载入当前配置。</p>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>
<style scoped>
.capability-page {
  display: grid;
  gap: 21px;
}
.capability-layout {
  display: grid;
  grid-template-columns: 205px minmax(0, 1fr);
  gap: 20px;
  align-items: start;
}
.capability-nav {
  padding: 10px;
}
.capability-nav button {
  display: flex;
  width: 100%;
  justify-content: flex-start;
  border: 0;
  background: none;
  text-align: left;
  padding: 13px 10px;
  color: #786d86;
  gap: 10px;
  font-size: 12px;
}
.capability-nav button.active {
  background: #f5effc;
  color: #9771b8;
}
.capability-nav small {
  display: block;
  font-size: 9px;
  letter-spacing: 1px;
  margin-top: 3px;
  opacity: 0.65;
}
.capability-nav .version {
  font-size: 10px;
  margin-left: auto;
  color: #786d86;
}
.capability-nav svg {
  width: 16px;
}
.capability-content {
  overflow: hidden;
}
.capability-content .card-head {
  padding: 22px;
}
.capability-content .card-head h2 {
  font-size: 14px;
}
.capability-content .card-head p {
  font-size: 12px;
  color: #786d86;
  margin-top: 5px;
}
.capability-content .card-head > button {
  font-size: 11px;
  padding: 7px;
}
.capability-symbol {
  width: 35px;
  height: 37px;
  border-radius: 9px;
  background: #f4ecfc;
  color: #786d86;
  display: grid;
  place-items: center;
}
.capability-symbol svg {
  width: 19px;
}
.tabs button {
  font-size: 12px;
}
.card-body {
  display: grid;
  gap: 15px;
}
.capability-cards {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}
.capability-item {
  border: 1px solid #ede4f6;
  padding: 18px;
  border-radius: 11px;
  background: linear-gradient(140deg, white, #fdfbff);
}
.capability-item-icon {
  display: grid;
  place-items: center;
  width: 31px;
  height: 31px;
  border-radius: 8px;
  background: #f7f1fc;
  color: #786d86;
}
.capability-item h3 {
  margin-top: 14px;
  font-size: 13px;
  font-weight: 500;
  color: #916baf;
  overflow-wrap: anywhere;
}
.capability-item p {
  font-size: 12px;
  color: #786d86;
  margin-top: 7px;
  line-height: 1.8;
  overflow-wrap: anywhere;
}
.capability-item-foot {
  margin-top: 18px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.capability-item-foot code {
  font-size: 10px;
  color: #786d86;
}
.capability-item-foot .badge {
  font-size: 10px;
  padding: 3px 6px;
}
.toggle {
  width: 27px;
  height: 16px;
  border: 0;
  background: #ded5e6;
  border-radius: 20px;
  padding: 2px;
  justify-content: flex-start;
}
.toggle span {
  width: 12px;
  height: 12px;
  background: white;
  border-radius: 50%;
  box-shadow: 0 1px 3px #0001;
}
.toggle.enabled {
  background: #b191ce;
  justify-content: flex-end;
}
.toggle.enabled:hover {
  background: #a482c3;
}
.config-overview {
  grid-column: 1/-1;
  display: grid;
  justify-items: center;
  text-align: center;
  padding: 50px 20px;
  color: #786d86;
  gap: 12px;
}
.config-overview > svg {
  width: 34px;
  height: 34px;
}
.config-overview h3 {
  font-weight: 500;
  font-size: 13px;
  color: #9d7db5;
}
.config-overview p {
  font-size: 12px;
  max-width: 330px;
}
.config-overview button {
  font-size: 12px;
  color: #786d86;
  margin-top: 5px;
}
.json-editor {
  border: 1px solid #eadff3;
  border-radius: 9px;
  overflow: hidden;
}
.editor-label {
  background: #faf6fd;
  padding: 10px 14px;
  display: flex;
  justify-content: space-between;
  color: #786d86;
  font-size: 11px;
}
.json-editor textarea {
  border: 0;
  border-radius: 0;
  min-height: 490px;
  font-size: 12px;
  line-height: 1.9;
  padding: 16px;
  color: #946fad;
  background: #fefcff;
  resize: vertical;
}
.json-editor textarea:focus {
  box-shadow: none;
}
.editor-foot {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px;
  border-top: 1px solid #f0e5f9;
  gap: 12px;
}
.editor-foot > span {
  font-size: 11px;
  color: #786d86;
}
.editor-foot button {
  font-size: 12px;
  padding: 8px 12px;
}
@media (min-width: 1600px) {
  .capability-cards {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}
@media (max-width: 1100px) {
  .capability-layout {
    grid-template-columns: 165px minmax(0, 1fr);
    gap: 14px;
  }
  .capability-nav {
    padding: 7px;
  }
  .capability-nav button {
    padding: 12px 7px;
    gap: 7px;
  }
  .capability-content .card-head > button {
    font-size: 0;
    gap: 0;
  }
}
@media (max-width: 700px) {
  .capability-layout {
    grid-template-columns: 1fr;
  }
  .capability-nav {
    display: flex;
    overflow: auto;
    padding: 6px;
  }
  .capability-nav button {
    width: auto;
    white-space: nowrap;
    padding: 10px 12px;
    gap: 6px;
  }
  .capability-nav small,
  .capability-nav .version {
    display: none;
  }
  .capability-cards {
    grid-template-columns: 1fr;
  }
  .capability-content .card-head {
    padding: 18px;
  }
  .card-body {
    padding: 17px;
  }
  .editor-foot > span {
    font-size: 10px;
  }
  .editor-foot button {
    white-space: nowrap;
  }
}
</style>
