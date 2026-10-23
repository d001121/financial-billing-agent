<script setup lang="ts">
import { onMounted, ref } from "vue";
import {
  Check,
  File,
  FolderOpen,
  Link,
  LoaderCircle,
  Plus,
  Sparkles,
  UploadCloud,
  X,
} from "@lucide/vue";
import { api, errorMessage } from "../api/client";
import { formatSize, type Asset, type Task } from "../types/contracts";
const props = defineProps<{ embedded?: boolean }>();
const emit = defineEmits<{ close: []; created: [task: Task] }>();
const title = ref(""),
  instructions = ref(""),
  url = ref(""),
  assets = ref<Asset[]>([]),
  samples = ref<Asset[]>([]);
const busy = ref(false),
  uploading = ref(false),
  error = ref(""),
  sampleError = ref(""),
  mode = ref("upload"),
  fileInput = ref<HTMLInputElement>();
onMounted(async () => {
  try {
    samples.value = await api.samples();
  } catch (e) {
    sampleError.value = errorMessage(e);
  }
});
async function upload(files: File[]) {
  if (!files.length) return;
  uploading.value = true;
  error.value = "";
  const failed: string[] = [];
  for (const file of files) {
    try {
      assets.value.push(...(await api.assets([file])));
    } catch (e) {
      failed.push(file.name + "：" + errorMessage(e));
    }
  }
  error.value = failed.join("；");
  uploading.value = false;
}
function chosen(event: Event) {
  void upload(Array.from((event.target as HTMLInputElement).files || []));
}
function drop(event: DragEvent) {
  void upload(Array.from(event.dataTransfer?.files || []));
}
async function importUrl() {
  if (!url.value.trim()) return;
  uploading.value = true;
  error.value = "";
  try {
    assets.value.push(...(await api.importAsset({ url: url.value.trim() })));
    url.value = "";
  } catch (e) {
    error.value = errorMessage(e);
  } finally {
    uploading.value = false;
  }
}
async function importSample(sample: Asset) {
  uploading.value = true;
  error.value = "";
  try {
    const result = await api.importAsset({
      sample_path: sample.sample_path || sample.path || sample.name,
    });
    assets.value.push(
      ...result.filter((x) => !assets.value.some((a) => a.id === x.id)),
    );
  } catch (e) {
    error.value = errorMessage(e);
  } finally {
    uploading.value = false;
  }
}
async function submit() {
  error.value = "";
  if (!assets.value.length) {
    error.value = "请先添加至少一份材料。";
    return;
  }
  busy.value = true;
  try {
    const task = await api.createTask({
      title: title.value.trim() || assets.value[0]?.name || "账单处理账单",
      accounting_entity: null,
      asset_ids: assets.value.map((x) => x.id),
      history_mode: "automatic",
      instructions: instructions.value.trim(),
    });
    emit("created", task);
  } catch (e) {
    error.value = errorMessage(e);
  } finally {
    busy.value = false;
  }
}
</script>
<template>
  <div
    :class="props.embedded ? 'embedded-composer' : 'modal-overlay'"
    @click.self="!props.embedded && !busy && emit('close')"
    @keydown.esc="!props.embedded && !busy && emit('close')"
  >
    <form
      :class="['modal', { 'embedded-form': props.embedded }]"
      :role="props.embedded ? undefined : 'dialog'"
      :aria-modal="props.embedded ? undefined : true"
      aria-labelledby="compose-title"
      @submit.prevent="submit"
    >
      <div class="modal-head">
        <div>
          <span class="eyebrow">{{
            props.embedded ? "MATERIAL INTAKE" : "NEW WORKSPACE TASK"
          }}</span>
          <h2 id="compose-title">
            {{ props.embedded ? "本次处理材料" : "开始一次账单处理" }}
          </h2>
        </div>
        <button
          v-if="!props.embedded"
          type="button"
          class="icon ghost"
          :disabled="busy"
          aria-label="关闭"
          @click="emit('close')"
        >
          <X />
        </button>
      </div>
      <div class="modal-body">
        <div class="form-grid">
          <div class="field">
            <label for="task-title">账单名称</label
            ><input
              id="task-title"
              v-model="title"
              placeholder="例如：10 月宁波港费用核对"
            />
          </div>
        </div>
        <div class="field">
          <label>添加这份账单的参考材料</label>
          <p class="small muted">
            一次提交对应一份账单。正文与全部附件共同核对；提取后，助手会在会话中请您选择记账公司。
          </p>
          <div class="material-tabs">
            <button
              type="button"
              :class="{ active: mode === 'upload' }"
              @click="mode = 'upload'"
            >
              <UploadCloud />上传文件</button
            ><button
              type="button"
              :class="{ active: mode === 'samples' }"
              @click="mode = 'samples'"
            >
              <FolderOpen />题目样本</button
            ><button
              type="button"
              :class="{ active: mode === 'url' }"
              @click="mode = 'url'"
            >
              <Link />文件链接
            </button>
          </div>
          <div
            v-if="mode === 'upload'"
            class="upload-zone"
            role="button"
            tabindex="0"
            @click="fileInput?.click()"
            @keydown.enter.prevent="fileInput?.click()"
            @keydown.space.prevent="fileInput?.click()"
            @dragover.prevent
            @drop.prevent="drop"
          >
            <UploadCloud /><strong>{{
              uploading ? "正在上传材料…" : "点击上传，或将文件拖到这里"
            }}</strong>
            <p>EML · PDF · 图片 · Excel · Word</p>
            <input
              ref="fileInput"
              type="file"
              multiple
              hidden
              @change="chosen"
            />
          </div>
          <div v-else-if="mode === 'samples'" class="samples">
            <p v-if="sampleError" class="notice error">{{ sampleError }}</p>
            <p v-else-if="!samples.length" class="muted small">
              当前没有可用样本。
            </p>
            <button
              v-for="sample in samples"
              :key="sample.id || sample.name"
              type="button"
              :disabled="uploading"
              @click="importSample(sample)"
            >
              <File /><span
                >{{ sample.name
                }}<small>{{ formatSize(sample.size) }}</small></span
              ><Plus :size="15" />
            </button>
          </div>
          <div v-else class="flex">
            <input
              v-model="url"
              type="url"
              placeholder="https://… 可直接下载的材料链接"
              aria-label="文件链接"
            /><button
              type="button"
              :disabled="uploading || !url"
              @click="importUrl"
            >
              添加
            </button>
          </div>
        </div>
        <div v-if="assets.length" class="uploaded-list">
          <div v-for="asset in assets" :key="asset.id">
            <span class="file-icon"><File :size="16" /></span
            ><span
              >{{ asset.name }}<small>{{ formatSize(asset.size) }}</small></span
            ><Check class="uploaded-check" /><button
              type="button"
              class="icon ghost"
              :disabled="busy || uploading"
              :aria-label="'移除' + asset.name"
              @click="assets = assets.filter((a) => a.id !== asset.id)"
            >
              <X :size="14" />
            </button>
          </div>
        </div>
        <div class="field">
          <label for="instructions"
            >处理要求 <span class="muted">（可选）</span></label
          ><textarea
            id="instructions"
            v-model="instructions"
            rows="2"
            placeholder="说明更新范围、待核对事项或其他业务背景。"
          />
        </div>
        <div v-if="error" class="notice error" role="alert">{{ error }}</div>
        <div class="notice">
          <Sparkles :size="16" /><span
            >提交后自动解析材料，确定记账公司后自动比对已核验的历史账单。需要补充信息时，账单助手会直接在会话中询问您。</span
          >
        </div>
      </div>
      <div class="modal-foot">
        <button type="button" :disabled="busy" @click="emit('close')">
          {{ props.embedded ? "返回业务中心" : "取消" }}</button
        ><button type="submit" class="primary" :disabled="busy || uploading">
          <LoaderCircle v-if="busy" class="loading-icon" /><Sparkles v-else />{{
            busy ? "正在创建账单…" : "提交并开始处理"
          }}
        </button>
      </div>
    </form>
  </div>
</template>
<style scoped>
.form-grid {
  grid-template-columns: 1fr;
}
.embedded-composer {
  min-width: 0;
}
.embedded-form {
  width: 100%;
  max-width: none;
  max-height: none;
  box-shadow: var(--shadow);
  border: 1px solid var(--line);
  border-radius: 14px;
}
.embedded-form .modal-head {
  padding: 25px 28px 22px;
}
.embedded-form .modal-head h2 {
  font-size: 18px;
}
.embedded-form .modal-body {
  padding: 26px 28px;
  overflow: visible;
  gap: 24px;
}
.embedded-form .field label {
  font-size: 13px;
}
.embedded-form .form-grid {
  align-items: start;
}
.embedded-form .field-hint {
  font-size: 11px;
  line-height: 1.8;
}
.embedded-form .upload-zone {
  background: #f5f9f6;
  border-color: #b8d2c4;
  padding: 36px 18px;
}
.embedded-form .upload-zone > svg {
  color: var(--primary);
  width: 32px;
  height: 32px;
  margin-bottom: 5px;
}
.embedded-form .upload-zone strong {
  color: var(--ink);
  font-size: 14px;
}
.embedded-form .upload-zone p {
  color: var(--muted);
}
.embedded-form .modal-foot {
  padding: 20px 28px;
  background: #fafbf9;
}
.embedded-form .material-tabs button {
  font-size: 13px;
  color: var(--muted);
}
.embedded-form .material-tabs button.active {
  color: var(--primary);
}
.embedded-form .file-icon {
  color: var(--primary);
  background: var(--primary-soft);
}
@media (max-width: 600px) {
  .embedded-form .modal-body,
  .embedded-form .modal-head,
  .embedded-form .modal-foot {
    padding: 20px;
  }
  .embedded-form .form-grid {
    grid-template-columns: 1fr;
  }
  .embedded-form .modal-foot {
    flex-wrap: wrap;
  }
  .embedded-form .material-tabs {
    gap: 2px;
  }
  .embedded-form .material-tabs button {
    padding-inline: 8px;
    font-size: 12px;
  }
}
.modal-head h2 {
  margin-top: 4px;
}
.modal-head .eyebrow {
  font-size: 11px;
}
.material-tabs {
  display: flex;
  gap: 8px;
  margin: 2px 0 8px;
}
.material-tabs button {
  font-size: 12px;
  padding: 7px 10px;
  border-color: transparent;
  color: var(--muted);
}
.material-tabs button svg {
  width: 14px;
  height: 14px;
}
.material-tabs button.active {
  color: var(--primary);
  background: var(--primary-soft);
}
.upload-zone {
  border: 1px dashed #c3d7ca;
  border-radius: 11px;
  background: #f7faf7;
  padding: 27px;
  text-align: center;
  cursor: pointer;
  display: grid;
  justify-items: center;
  gap: 8px;
}
.upload-zone > svg {
  width: 27px;
  height: 27px;
  color: var(--muted);
}
.upload-zone strong {
  font-size: 13px;
  font-weight: 500;
  color: var(--primary);
}
.upload-zone p {
  font-size: 12px;
  color: var(--muted);
}
.upload-zone input {
  display: none;
}
.samples {
  max-height: 210px;
  overflow: auto;
  display: grid;
  gap: 7px;
}
.samples > button {
  justify-content: flex-start;
  padding: 10px 12px;
  font-size: 12px;
}
.samples > button > svg:first-child {
  color: var(--muted);
}
.samples > button > svg:last-child {
  margin-left: auto;
  color: var(--primary);
}
.samples span {
  text-align: left;
}
.samples small,
.uploaded-list small {
  display: block;
  font-size: 11px;
  color: var(--muted);
  margin-top: 2px;
}
.uploaded-list {
  display: grid;
  gap: 8px;
}
.uploaded-list > div {
  display: flex;
  align-items: center;
  gap: 9px;
  border: 1px solid var(--line);
  padding: 8px 10px;
  border-radius: 8px;
  font-size: 12px;
}
.uploaded-list > div > span:nth-child(2) {
  overflow-wrap: anywhere;
}
.file-icon {
  width: 31px;
  height: 34px;
  display: grid;
  place-items: center;
  background: var(--primary-soft);
  color: var(--primary);
  border-radius: 6px;
}
.uploaded-check {
  color: var(--green);
  margin-left: auto;
  width: 14px;
}
.uploaded-list button {
  padding: 4px;
}
.field label .muted {
  font-weight: 400;
}
</style>
