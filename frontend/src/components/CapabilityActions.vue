<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { Plus, Upload, X, Save, Play, FileText } from "@lucide/vue";
import { api, errorMessage } from "../api/client";
import type { ConfigDocument, JsonObject } from "../types/contracts";

const props = defineProps<{ kind: string; document: ConfigDocument }>();
const emit = defineEmits<{ saved: [value: ConfigDocument] }>();
const open = ref(false),
  busy = ref(false),
  error = ref(""),
  notice = ref(""),
  editing = ref(-1);
const identity = ref(""),
  description = ref(""),
  version = ref("1.0.0"),
  url = ref(""),
  transport = ref(""),
  bindings = ref("[]");
const prompt = ref(""),
  skills = ref(""),
  agentType = ref("agent"),
  hookSkill = ref(""),
  hookFunction = ref(""),
  priority = ref(100);
const catalog = ref<JsonObject[]>([]),
  selectedPackage = ref(""),
  file = ref<File | null>(null);
const resourceName = ref(""),
  resourcePath = ref("SKILL.md"),
  resourceText = ref(""),
  resourceFiles = ref<string[]>([]);
const probeServer = ref<JsonObject | null>(null),
  probeTools = ref<JsonObject[]>([]),
  probeTool = ref(""),
  args = ref("{}"),
  callResult = ref("");
const key = computed(() => (props.kind === "mcp" ? "servers" : props.kind));
const pendingRemoval = ref<JsonObject | null>(null);
const config = computed(() => props.document.config as JsonObject);
const label = computed(
  () =>
    ({
      skills: "Skill",
      mcp: "MCP 服务",
      agents: "专家智能体",
      hooks: "校验 Hook",
    })[props.kind] || "配置",
);
const installed = computed(() => catalog.value.filter((s) => !s.registered));
async function loadCatalog() {
  try {
    catalog.value = (await api.skillCatalog()).skills;
  } catch (e) {
    error.value = errorMessage(e);
  }
}
watch(
  () => props.kind,
  () => {
    open.value = false;
    probeServer.value = null;
    resourceName.value = "";
    pendingRemoval.value = null;
    error.value = "";
    notice.value = "";
  },
);
onMounted(() => void loadCatalog());
watch(
  () => props.document,
  () => {
    if (props.kind === "mcp" && probeServer.value) {
      const servers = config.value.servers as JsonObject[];
      probeServer.value =
        servers.find((s) => s.id === probeServer.value?.id) || null;
    }
  },
);
function reset() {
  editing.value = -1;
  identity.value = "";
  description.value = "";
  version.value = "1.0.0";
  url.value = "";
  transport.value = "";
  bindings.value = "[]";
  prompt.value = "";
  skills.value = "";
  hookSkill.value = "";
  hookFunction.value = "";
  agentType.value = "agent";
  priority.value = 100;
  selectedPackage.value = "";
  error.value = "";
  open.value = true;
}
function edit(entry: JsonObject) {
  reset();
  editing.value = Number(String(entry._key).split("-").pop());
  identity.value = String(entry.name || entry.id || "");
  description.value = String(entry.description || "");
  version.value = String(entry.version || "1.0.0");
  url.value = String(entry.url || "");
  transport.value = entry.transport
    ? JSON.stringify(entry.transport, null, 2)
    : "";
  bindings.value = JSON.stringify(entry.tools || [], null, 2);
  prompt.value = String(entry.prompt || "");
  skills.value = ((entry.skills as string[]) || []).join(", ");
  agentType.value = String(entry.type || "agent");
  hookSkill.value = String(entry.skill || "");
  hookFunction.value = String(entry.function || "");
  priority.value = Number(entry.priority || 0);
}
async function persist(value: JsonObject) {
  emit(
    "saved",
    await api.saveConfig(props.kind, {
      expected_version: props.document.version,
      config: value,
    }),
  );
  notice.value = "已保存。新任务使用新版本；已禁用能力会在下一次派发时被拦截。";
  await loadCatalog();
}
async function save() {
  busy.value = true;
  error.value = "";
  try {
    const updated = JSON.parse(JSON.stringify(config.value));
    const list = updated[key.value] as JsonObject[];
    let item: JsonObject;
    if (props.kind === "mcp")
      item = {
        id: identity.value.trim(),
        description: description.value,
        enabled: true,
        ...(transport.value.trim()
          ? { transport: JSON.parse(transport.value) }
          : { url: url.value.trim() }),
      };
    else if (props.kind === "skills")
      item = {
        name: (editing.value < 0
          ? selectedPackage.value
          : identity.value
        ).trim(),
        enabled: true,
        version: version.value,
        tools: JSON.parse(bindings.value),
      };
    else if (props.kind === "agents")
      item = {
        name: identity.value.trim(),
        enabled: true,
        type: agentType.value,
        description: description.value,
        prompt: prompt.value,
        skills: skills.value
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean),
      };
    else
      item = {
        name: identity.value.trim(),
        enabled: true,
        required:
          editing.value >= 0 ? list[editing.value]?.required === true : false,
        priority: priority.value,
        skill: hookSkill.value,
        function: hookFunction.value,
      };
    if (editing.value >= 0)
      list[editing.value] = {
        ...list[editing.value],
        ...item,
        enabled: list[editing.value]?.enabled ?? true,
      };
    else list.push(item);
    await persist(updated);
    open.value = false;
  } catch (e) {
    error.value = errorMessage(e);
  } finally {
    busy.value = false;
  }
}
function remove(entry: JsonObject) {
  pendingRemoval.value = entry;
}
async function confirmRemoval() {
  if (!pendingRemoval.value) return;
  const entry = pendingRemoval.value;
  busy.value = true;
  error.value = "";
  try {
    const updated = JSON.parse(JSON.stringify(config.value));
    (updated[key.value] as JsonObject[]).splice(
      Number(String(entry._key).split("-").pop()),
      1,
    );
    await persist(updated);
    pendingRemoval.value = null;
  } catch (e) {
    error.value = errorMessage(e);
  } finally {
    busy.value = false;
  }
}
async function install() {
  if (!file.value) return;
  busy.value = true;
  error.value = "";
  try {
    const result = await api.importSkill(
      file.value,
      Number(props.document.version),
      bindings.value,
    );
    emit("saved", {
      kind: "skills",
      version: result.config.version as number,
      config: result.config,
    });
    notice.value = "Skill已导入并注册；官方Skill加载器会在新任务发现它。";
    file.value = null;
    await loadCatalog();
    open.value = false;
  } catch (e) {
    error.value = errorMessage(e);
  } finally {
    busy.value = false;
  }
}
function choosePackage() {
  const item = catalog.value.find((s) => s.name === selectedPackage.value);
  if (item) version.value = String(item.version);
}
function chooseFile(event: Event) {
  file.value = (event.target as HTMLInputElement).files?.[0] || null;
}
async function readResource() {
  try {
    resourceText.value = (
      await api.skillResource(resourceName.value, resourcePath.value)
    ).content;
  } catch (e) {
    error.value = errorMessage(e);
  }
}
async function inspect(entry: JsonObject) {
  resourceName.value = String(entry.name);
  resourceFiles.value = (catalog.value.find((s) => s.name === entry.name)
    ?.files as string[]) || ["SKILL.md"];
  resourcePath.value = "SKILL.md";
  await readResource();
}
async function probe(entry: JsonObject) {
  busy.value = true;
  error.value = "";
  probeServer.value = entry;
  probeTools.value = [];
  callResult.value = "";
  try {
    const server = { ...entry };
    delete server._key;
    const result = await api.testMcp(server);
    probeTools.value = result.tools;
    probeTool.value = String(result.tools[0]?.name || "");
    notice.value = `已真实连接并发现 ${result.tools.length} 个工具。`;
  } catch (e) {
    error.value = errorMessage(e);
  } finally {
    busy.value = false;
  }
}
async function call() {
  if (!probeServer.value) return;
  busy.value = true;
  error.value = "";
  try {
    const parsed = JSON.parse(args.value);
    callResult.value = JSON.stringify(
      await api.callMcp(String(probeServer.value.id), probeTool.value, parsed),
      null,
      2,
    );
  } catch (e) {
    error.value = errorMessage(e);
  } finally {
    busy.value = false;
  }
}
defineExpose({ edit, remove, inspect, probe });
</script>
<template>
  <section class="extension-actions">
    <section
      v-if="pendingRemoval"
      class="resource-view"
      role="region"
      aria-label="移除配置确认"
    >
      <h3>移除 {{ pendingRemoval.name || pendingRemoval.id }}？</h3>
      <p>从新任务配置中移除；历史快照与已安装的 Skill 包文件保留。</p>
      <div class="flex gap">
        <button :disabled="busy" @click="confirmRemoval">确认移除配置</button
        ><button class="ghost" :disabled="busy" @click="pendingRemoval = null">
          取消移除
        </button>
      </div>
    </section>
    <div class="action-bar" v-if="kind !== 'runtime'">
      <button @click="reset" :disabled="busy">
        <Plus :size="14" />新增{{ label }}</button
      ><span>更改使用版本校验保存，依赖冲突会直接提示。</span>
    </div>
    <p v-if="error" class="notice error" role="alert">{{ error }}</p>
    <p v-if="notice" class="notice" role="status">{{ notice }}</p>
    <form v-if="open" class="extension-form" @submit.prevent="save">
      <div class="flex between">
        <h3>{{ editing < 0 ? "新增" : "编辑" }}{{ label }}</h3>
        <button
          type="button"
          class="ghost"
          @click="open = false"
          aria-label="关闭能力编辑"
        >
          <X :size="16" />
        </button>
      </div>
      <template v-if="kind === 'skills' && editing < 0">
        <label
          >导入Skill ZIP<input type="file" accept=".zip" @change="chooseFile"
        /></label>
        <p class="small muted">
          包含SKILL.md和references/scripts资源。脚本工具绑定可选，加载与执行由官方框架完成。
        </p>
        <button v-if="file" type="button" :disabled="busy" @click="install">
          <Upload :size="14" />导入并注册
        </button>
        <label
          >或注册已安装的Skill<select
            v-model="selectedPackage"
            @change="choosePackage"
          >
            <option value="">选择未注册的包</option>
            <option
              v-for="s in installed"
              :key="String(s.name)"
              :value="String(s.name)"
            >
              {{ s.name }}
            </option>
          </select></label
        >
      </template>
      <label v-else
        >标识名称<input
          v-model="identity"
          required
          :readonly="editing >= 0"
          placeholder="例如 shipping-policy"
      /></label>
      <label v-if="kind === 'skills'"
        >版本<input v-model="version" required
      /></label>
      <label v-if="kind === 'skills'"
        >脚本工具绑定（JSON数组）<textarea
          v-model="bindings"
          rows="3"
          class="mono"
          placeholder='[{"function":"calculate","name":"calculate"}]'
        />
      </label>
      <template v-if="kind === 'mcp'"
        ><label>服务说明<input v-model="description" /></label
        ><label
          >HTTP / SSE 地址<input
            v-model="url"
            type="url"
            placeholder="https://example.com/mcp"
            :disabled="!!transport.trim()"
        /></label>
        <details>
          <summary>本地stdio / 请求头等原生传输配置</summary>
          <label
            >FastMCP transport JSON<textarea
              v-model="transport"
              class="mono"
              rows="5"
              placeholder='{"command":"python","args":["server.py"]}'
            />
          </label>
        </details>
        <p class="small muted">
          填写传输JSON时使用该配置；保存后可真实连接、查看工具和测试调用。
        </p></template
      >
      <template v-if="kind === 'agents'"
        ><label>职责说明<input v-model="description" required /></label
        ><label
          >Agent类型<select v-model="agentType">
            <option value="agent">LangChain Agent</option>
            <option value="deep-agent">Deep Agent</option>
          </select></label
        ><label
          >授权Skill（逗号分隔）<input
            v-model="skills"
            placeholder="document-extraction, evidence-linking" /></label
        ><label>职责提示词<textarea v-model="prompt" required rows="5" /></label
      ></template>
      <template v-if="kind === 'hooks'"
        ><label>所属Skill<input v-model="hookSkill" required /></label
        ><label>校验函数<input v-model="hookFunction" required /></label
        ><label
          >优先级<input
            v-model.number="priority"
            type="number"
            min="0"
            required /></label
      ></template>
      <button
        class="primary"
        :disabled="
          busy || (kind === 'skills' && editing < 0 && !selectedPackage)
        "
      >
        <Save :size="14" />{{ busy ? "保存中…" : "保存配置" }}
      </button>
    </form>
    <section v-if="resourceName" class="resource-view">
      <div class="flex between">
        <h3><FileText :size="15" />{{ resourceName }}</h3>
        <button
          class="ghost"
          @click="resourceName = ''"
          aria-label="关闭资源预览"
        >
          <X :size="16" />
        </button>
      </div>
      <label
        >包内资源<select v-model="resourcePath" @change="readResource">
          <option v-for="f in resourceFiles" :key="f">{{ f }}</option>
        </select></label
      >
      <pre>{{ resourceText }}</pre>
    </section>
    <section v-if="probeServer" class="resource-view">
      <div class="flex between">
        <h3>{{ probeServer.id }} · 实际工具</h3>
        <button
          class="ghost"
          @click="probeServer = null"
          aria-label="关闭MCP测试"
        >
          <X :size="16" />
        </button>
      </div>
      <template v-if="probeTools.length"
        ><label
          >工具<select v-model="probeTool">
            <option v-for="t in probeTools" :key="String(t.name)">
              {{ t.name }}
            </option>
          </select></label
        >
        <p>{{ probeTools.find((t) => t.name === probeTool)?.description }}</p>
        <details>
          <summary>参数Schema</summary>
          <pre>{{
            JSON.stringify(
              probeTools.find((t) => t.name === probeTool)?.schema,
              null,
              2,
            )
          }}</pre>
        </details>
        <label
          >调用参数（JSON对象）<textarea v-model="args" class="mono" rows="4" />
        </label>
        <p class="small muted">
          此操作会真实执行所选工具，请核对参数后调用。禁用服务无法执行。
        </p>
        <button :disabled="busy || probeServer.enabled === false" @click="call">
          <Play :size="14" />执行测试调用
        </button>
        <pre v-if="callResult">{{ callResult }}</pre>
      </template>
      <p v-else>尚未发现工具，请检查连接结果。</p>
    </section>
  </section>
</template>
<style scoped>
.extension-actions {
  display: grid;
  gap: 12px;
  margin-bottom: 18px;
}
.action-bar {
  display: flex;
  gap: 14px;
  align-items: center;
  flex-wrap: wrap;
}
.action-bar span {
  font-size: 12px;
  color: var(--muted);
}
.extension-form,
.resource-view {
  border: 1px solid var(--line);
  background: var(--surface, #fafcfb);
  border-radius: 10px;
  padding: 18px;
  display: grid;
  gap: 13px;
}
.extension-form h3,
.resource-view h3 {
  font-size: 14px;
  display: flex;
  gap: 8px;
  align-items: center;
}
label {
  display: grid;
  gap: 7px;
  font-size: 12px;
}
input,
select,
textarea {
  width: 100%;
  min-width: 0;
  padding: 10px;
  border: 1px solid var(--line);
  border-radius: 6px;
  background: white;
  font: inherit;
  color: var(--ink);
}
textarea {
  resize: vertical;
}
button {
  width: fit-content;
}
pre {
  max-height: 360px;
  overflow: auto;
  background: #f0f4f2;
  padding: 14px;
  border-radius: 7px;
  font-size: 12px;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
details {
  font-size: 12px;
}
details label {
  margin-top: 12px;
}
</style>
