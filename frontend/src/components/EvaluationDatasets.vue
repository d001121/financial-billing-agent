<script setup lang="ts">
import { onMounted, ref } from "vue";
import { Upload, Download, FlaskConical } from "@lucide/vue";
import { api, downloadJson, errorMessage } from "../api/client";
import type { JsonObject } from "../types/contracts";
const emit = defineEmits<{ select: [id: string] }>();
const datasets = ref<JsonObject[]>([]),
  selected = ref("builtin"),
  open = ref(false),
  name = ref(""),
  labeledBy = ref(""),
  file = ref<File | null>(null),
  busy = ref(false),
  error = ref(""),
  notice = ref("");
async function load() {
  try {
    datasets.value = (await api.evaluationDatasets()).datasets;
    if (
      !datasets.value.some(
        (d) => d.id === selected.value && d.enabled !== false,
      )
    ) {
      selected.value = "builtin";
      emit("select", "builtin");
    }
  } catch (e) {
    error.value = errorMessage(e);
  }
}
async function importFile() {
  if (!file.value) return;
  busy.value = true;
  error.value = "";
  try {
    const result = await api.importEvaluationDataset({
      name: name.value,
      labeled_by: labeledBy.value,
      dataset: JSON.parse(await file.value.text()),
    });
    selected.value = String(result.id);
    emit("select", selected.value);
    await load();
    open.value = false;
    notice.value = "标注数据集已保存，可选择它运行真实对照评测。";
  } catch (e) {
    error.value = errorMessage(e);
  } finally {
    busy.value = false;
  }
}
async function toggle(d: JsonObject) {
  busy.value = true;
  error.value = "";
  try {
    await api.toggleEvaluationDataset(String(d.id), {
      expected_revision: d.revision,
      enabled: d.enabled === false,
    });
    await load();
  } catch (e) {
    error.value = errorMessage(e);
  } finally {
    busy.value = false;
  }
}
async function download(id: string) {
  try {
    downloadJson(
      await api.evaluationDataset(id),
      id === "builtin" ? "费用映射标注示例.json" : `${id}.json`,
    );
  } catch (e) {
    error.value = errorMessage(e);
  }
}
function chooseFile(event: Event) {
  file.value = (event.target as HTMLInputElement).files?.[0] || null;
}
onMounted(() => void load());
</script>
<template>
  <section class="card dataset-panel">
    <div class="flex between">
      <h3><FlaskConical :size="16" />评测数据集</h3>
      <button @click="open = !open"><Upload :size="14" />导入人工标注</button>
    </div>
    <p>
      先用回归样例检查，再使用独立最终样例。此处评测费用映射与财务规则，不能代表OCR识别准确率。
    </p>
    <p v-if="error" class="notice error" role="alert">{{ error }}</p>
    <p v-if="notice" class="notice" role="status">{{ notice }}</p>
    <label
      >本次候选使用的数据集<select
        v-model="selected"
        @change="emit('select', selected)"
      >
        <option
          v-for="d in datasets.filter((d) => d.enabled !== false)"
          :key="String(d.id)"
          :value="String(d.id)"
        >
          {{ d.name }} · {{ d.synthetic ? "合成" : "真实标注" }} ·
          {{ d.case_count }}例
        </option>
      </select></label
    >
    <div class="dataset-list">
      <div v-for="d in datasets" :key="String(d.id)" class="flex between">
        <span
          >{{ d.name }}
          <small>{{ d.enabled === false ? "已禁用" : "可选择" }}</small></span
        >
        <div class="flex">
          <button class="ghost" @click="download(String(d.id))">
            <Download :size="13" />{{
              d.id === "builtin" ? "下载格式示例" : "下载"
            }}</button
          ><button
            v-if="d.id !== 'builtin'"
            class="ghost"
            :disabled="busy"
            @click="toggle(d)"
          >
            {{ d.enabled === false ? "启用" : "禁用" }}
          </button>
        </div>
      </div>
    </div>
    <form v-if="open" @submit.prevent="importFile">
      <label>名称<input v-model="name" required /></label
      ><label>人工标注人<input v-model="labeledBy" required /></label
      ><label
        >标注JSON<input
          type="file"
          accept=".json"
          required
          @change="chooseFile"
      /></label>
      <p>
        按格式示例填写真实输入、期望结果、样例家族及regression/final用途。禁止用候选输出自动充当正确答案。已暴露的最终样例不能通过改名再次充当独立样例。
      </p>
      <button class="primary" :disabled="busy || !file">保存数据集</button>
    </form>
  </section>
</template>
<style scoped>
.dataset-panel {
  padding: 20px 24px;
  margin-bottom: 20px;
  display: grid;
  gap: 13px;
}
.dataset-panel h3 {
  display: flex;
  gap: 8px;
  align-items: center;
  font-size: 14px;
}
.dataset-panel p {
  font-size: 12px;
  color: var(--muted);
  line-height: 1.8;
}
label {
  display: grid;
  gap: 7px;
  font-size: 12px;
}
select,
input {
  padding: 9px;
  border: 1px solid var(--line);
  border-radius: 6px;
  background: white;
  min-width: 0;
  width: 100%;
}
.dataset-list {
  display: grid;
  gap: 8px;
  font-size: 12px;
}
.dataset-list small {
  color: var(--muted);
  margin-left: 8px;
}
form {
  border-top: 1px solid var(--line);
  padding-top: 16px;
  display: grid;
  gap: 12px;
}
.flex {
  gap: 8px;
  flex-wrap: wrap;
}
</style>
