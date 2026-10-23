<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { ArrowUpRight, CircleAlert, Download, FileText, LoaderCircle, Pencil, RefreshCw, X } from "@lucide/vue";
import { api, errorMessage } from "../api/client";
import type { Charge, Evidence, PreviewBlock, PreviewTarget, SourcePreview, Task } from "../types/contracts";
import PdfEvidenceViewer from "./PdfEvidenceViewer.vue";
import { formatChargeAmount } from "../utils/amountPresentation";

const props = defineProps<{ task: Task; charge?: Charge; target: Evidence; editable: boolean }>();
const emit = defineEmits<{ close: []; edit: [field?: string] }>();
const preview = ref<SourcePreview | null>(null), loading = ref(false), error = ref(""), retry = ref(0),
  content = ref<HTMLElement | null>(null), closeButton = ref<HTMLButtonElement | null>(null),
  imageSize = ref({ width: 0, height: 0 });
const view = ref<"original" | "text">("original");
const renderUrl = computed(() => safeUrl(preview.value?.render?.content_url));
const renderedTarget = computed(() => {
  const data = preview.value;
  return { located: false, ...data?.target,
    page: data && data.target.render_version === data.render?.version ? data.target.render_page : undefined };
});
const previousFocus = window.document.activeElement as HTMLElement | null;
async function switchView(next: "original" | "text") {
  view.value = next;
  await nextTick();
  window.document.getElementById(next === 'original' ? 'source-original-tab' : 'source-text-tab')?.focus();
}
type Cell = { text: string; anchor?: string; column?: string | number };

function cellRows(block: PreviewBlock): Cell[][] {
  const cells = block.cells;
  if (!Array.isArray(cells) || !cells.length) return [];
  const rows = Array.isArray(cells[0]) ? cells as unknown[][] : [cells];
  return rows.map(row => row.map(value => {
    if (value && typeof value === "object" && !Array.isArray(value)) {
      const cell = value as Record<string, unknown>;
      return { text: String(cell.text ?? cell.value ?? ""), anchor: typeof cell.anchor === "string" ? cell.anchor : typeof cell.coordinate === "string" ? cell.coordinate : undefined,
        column: typeof cell.column === "string" || typeof cell.column === "number" ? cell.column : undefined };
    }
    return { text: value == null ? "" : String(value) };
  }));
}
const selectedIndex = computed(() => {
  const data = preview.value;
  if (!data?.target.located) return -1;
  const target = data.target;
  let at = data.blocks.findIndex(block => target.anchor && block.anchor === target.anchor);
  if (at < 0 && target.cell_anchor) at = data.blocks.findIndex(block => cellRows(block).some(row => row.some(cell => cell.anchor === target.cell_anchor)));
  if (at < 0 && target.row != null) at = data.blocks.findIndex(block => block.row === target.row && (!target.sheet || block.sheet === target.sheet));
  if (at < 0 && target.quote) {
    const matches = data.blocks.map((block, index) => ({ block, index })).filter(({ block }) => block.text?.includes(target.quote || ""));
    if (matches.length === 1) at = matches[0]!.index;
  }
  return at;
});
const locationLabel = computed(() => {
  const target = preview.value?.target;
  if (!target) return "";
  return [target.page != null ? `原页 ${target.page}` : "", target.sheet, target.row != null ? `第 ${target.row} 行` : "", target.column != null ? `${target.column} 列` : "", target.anchor].filter(Boolean).join(" · ");
});
function columnNumber(value: string | number | undefined): string {
  if (typeof value === "number") return String(value);
  if (!value) return "";
  const letters = value.toUpperCase().match(/^([A-Z]+)(?:\d+)?$/)?.[1];
  return letters ? String([...letters].reduce((sum, char) => sum * 26 + char.charCodeAt(0) - 64, 0)) : value;
}
function selectedCell(cell: Cell, column: number) {
  const target = preview.value?.target;
  if (target?.cell_anchor) return cell.anchor === target.cell_anchor;
  if (target?.column != null) return columnNumber(cell.column ?? column + 1) === columnNumber(target.column);
  return false;
}
async function scrollToSelection() {
  await nextTick();
  content.value?.querySelector('[data-preview-selected="true"]')?.scrollIntoView({ block: "center", behavior: "smooth" });
}
function textParts(text: string, selected: boolean) {
  if (!selected) return [{ text, highlight: false }];
  const target = preview.value?.target;
  let start = -1, end = -1;
  if (target?.field?.split(".").at(-1) === "amount" && props.charge?.charge_details.amount != null) {
    const matches = [...text.matchAll(/[-+]?\d[\d,]*(?:\.\d+)?/g)].filter(match => Number(match[0].replace(/,/g, "")) === props.charge!.charge_details.amount);
    if (matches.length === 1) { start = matches[0]!.index!; end = start + matches[0]![0].length; }
  } else if (target?.quote && text.includes(target.quote) && text.indexOf(target.quote) === text.lastIndexOf(target.quote)) {
    start = text.indexOf(target.quote); end = start + target.quote.length;
  } else if (selected) return [{ text, highlight: true }];
  return start >= 0 ? [{ text: text.slice(0, start), highlight: false }, { text: text.slice(start, end), highlight: true }, { text: text.slice(end), highlight: false }] : [{ text, highlight: false }];
}
const imageBox = computed(() => {
  const box: PreviewTarget['bbox'] = preview.value?.original?.locations[0]?.boxes[0] || preview.value?.target.bbox;
  if (!box) return undefined;
  const width = box.unit === "normalized" ? 1 : box.unit === "pixel" ? box.image_width || imageSize.value.width : 0;
  const height = box.unit === "normalized" ? 1 : box.unit === "pixel" ? box.image_height || imageSize.value.height : 0;
  if (!width || !height || ![box.x, box.y, box.width, box.height].every(Number.isFinite) || box.width <= 0 || box.height <= 0) return undefined;
  if (box.x < 0 || box.y < 0 || box.x + box.width > width || box.y + box.height > height) return undefined;
  return { left: `${100 * box.x / width}%`, top: `${100 * box.y / height}%`, width: `${100 * box.width / width}%`, height: `${100 * box.height / height}%` };
});
function imageLoaded(event: Event) {
  const image = event.target as HTMLImageElement;
  imageSize.value = { width: image.naturalWidth, height: image.naturalHeight };
}
function safeUrl(url?: string) {
  return url && (/^\/(?!\/)/.test(url) || /^https?:\/\//i.test(url)) ? url : undefined;
}
const sourceSignature = computed(() => JSON.stringify(props.task.sources?.find(source =>
  source.source_id === (props.target.source_id || props.target.asset_id))));
const chargeSignature = computed(() => JSON.stringify(
  props.task.records?.find(record => record.charge_id === props.target.charge_id) ||
  props.task.charges?.find(record => record.charge_id === props.target.charge_id) || props.charge));
watch(() => JSON.stringify([props.task.id, props.task.revision, props.target.source_id, props.target.asset_id, props.target.anchor, props.target.quote, props.target.field, props.target.value, props.target.charge_id, sourceSignature.value, chargeSignature.value, retry.value]), async (_, __, cleanup) => {
  const controller = new AbortController(); cleanup(() => controller.abort());
  loading.value = true; error.value = ""; preview.value = null; imageSize.value = { width: 0, height: 0 };
  const sourceId = props.target.source_id || props.target.asset_id;
  if (!sourceId) { error.value = "当前字段尚未关联来源材料，请先补充证据。"; loading.value = false; return; }
  try {
    const data = await api.sourcePreview(props.task.id, sourceId, props.target, controller.signal);
    if (controller.signal.aborted) return;
    if (data.revision !== props.task.revision) throw Error("任务版本已变化，请刷新当前费用后重新查看证据。");
    preview.value = data;
    view.value = "original";
  } catch (e) { if (!controller.signal.aborted) error.value = errorMessage(e); }
  finally { if (!controller.signal.aborted) { loading.value = false; await scrollToSelection(); } }
}, { immediate: true });
watch(view, scrollToSelection);
onMounted(() => closeButton.value?.focus());
onBeforeUnmount(() => previousFocus?.isConnected && previousFocus.focus());
function trapFocus(event: KeyboardEvent) {
  if (event.key !== "Tab") return;
  const elements = (event.currentTarget as HTMLElement).querySelectorAll<HTMLElement>('button:not(:disabled), a[href], input, select, textarea, [tabindex="0"]');
  const first = elements[0], last = elements[elements.length - 1];
  if (event.shiftKey && window.document.activeElement === first) { event.preventDefault(); last?.focus(); }
  else if (!event.shiftKey && window.document.activeElement === last) { event.preventDefault(); first?.focus(); }
}
</script>
<template>
  <Teleport to="body">
    <div class="preview-overlay" @click.self="emit('close')">
      <section class="material-preview" role="dialog" aria-modal="true" aria-labelledby="material-preview-title" @keydown.esc.stop="emit('close')" @keydown="trapFocus">
        <header class="preview-header">
          <div><span class="eyebrow">SOURCE · REVISION {{ task.revision }}</span><h2 id="material-preview-title">{{ preview?.name || '材料与字段定位' }}</h2></div>
          <button ref="closeButton" class="icon ghost" aria-label="关闭材料预览" @click="emit('close')"><X /></button>
        </header>
        <div class="preview-context">
          <div><b>{{ charge?.charge_details?.charge_item || '来源材料' }}</b><span v-if="charge">{{ formatChargeAmount(charge) }} {{ charge.charge_details.currency }}</span></div>
          <button v-if="charge" :disabled="!editable" @click="emit('edit', String(target.field || ''))"><Pencil :size="14" />修订当前费用</button>
        </div>
        <div class="representation-tabs" role="tablist" aria-label="证据查看方式">
          <button id="source-original-tab" role="tab" :aria-selected="view === 'original'" aria-controls="source-evidence-page" :tabindex="view === 'original' ? 0 : -1" :class="{ active: view === 'original' }" @click="view = 'original'" @keydown.right.prevent="switchView('text')">原件定位</button>
          <button id="source-text-tab" role="tab" :aria-selected="view === 'text'" aria-controls="source-evidence-page" :tabindex="view === 'text' ? 0 : -1" :class="{ active: view === 'text' }" @click="view = 'text'" @keydown.left.prevent="switchView('original')">提取原文</button>
        </div>
        <div id="source-evidence-page" ref="content" class="preview-content" role="tabpanel" :aria-labelledby="view === 'original' ? 'source-original-tab' : 'source-text-tab'" tabindex="0">
          <div v-if="loading" class="preview-empty" role="status"><LoaderCircle class="loading-icon" /><h3>正在打开来源材料</h3><p>保留原文位置与本次字段上下文。</p></div>
          <div v-else-if="error" class="preview-empty"><CircleAlert /><h3>暂时无法展示材料</h3><p role="alert">{{ error }}</p><button @click="retry++"><RefreshCw :size="14" />重试</button></div>
          <template v-else-if="preview">
            <div v-if="view === 'text'" class="preview-location" :class="{ warning: !preview.target.located }" role="status">
              <FileText :size="15" /><div><strong>{{ preview.target.located ? (preview.target.cell_anchor || preview.target.column != null ? '已定位原文单元格' : '已定位原文锚点') : '仅定位文件 / 原页' }}</strong><p>{{ locationLabel }}</p><p v-if="preview.target.reason">{{ preview.target.reason }}</p></div>
            </div>
            <template v-if="view === 'original' && renderUrl">
              <p class="preview-note">原文件转换的只读 PDF，黄色区域为对应原文。可切换“提取原文”对照识别内容。</p>
              <PdfEvidenceViewer :url="renderUrl" :target="renderedTarget" :original="preview.original" :amount="charge?.charge_details.amount" derived />
            </template>
            <PdfEvidenceViewer v-else-if="view === 'original' && preview.kind === 'pdf' && safeUrl(preview.content_url)" :url="preview.content_url" :target="preview.target" :original="preview.original" :amount="charge?.charge_details.amount" />
            <template v-else-if="view === 'original' && preview.kind === 'image' && safeUrl(preview.content_url)">
              <p class="preview-note">{{ preview.original?.reason || '原图对应位置' }}</p>
              <div class="image-preview"><img :src="preview.content_url" :alt="preview.name" @load="imageLoaded" /><span v-if="imageBox" class="image-evidence-box" :style="imageBox" /></div>
            </template>
            <div v-else-if="view === 'original' && preview.kind === 'office'" class="preview-empty"><FileText /><h3>暂时无法打开原件版式</h3><p>{{ preview.original?.reason || '可先切换提取原文核对，或下载原件。' }}</p></div>
            <template v-else-if="preview.blocks.length">
              <div class="structure-caption"><b>{{ view === 'text' ? '提取后的原文' : '原文件文字内容' }}</b><span>{{ view === 'text' ? '解析 / OCR 结果，保留原页、段落与单元格锚点。' : '邮件或文本材料，黄色标注对应引用。' }}</span></div>
              <article v-for="(block, index) in preview.blocks" :key="block.anchor || index" class="preview-block" :class="{ selected: selectedIndex === index }" :data-preview-selected="selectedIndex === index">
                <div class="block-location"><span>{{ [block.sheet, block.row != null ? `第 ${block.row} 行` : '', block.page != null ? `原页 ${block.page}` : '', block.anchor].filter(Boolean).join(' · ') || `内容块 ${index + 1}` }}</span><b v-if="selectedIndex === index">定位范围</b></div>
                <div v-if="cellRows(block).length" class="preview-table-scroll"><table class="preview-table"><tbody><tr v-for="(row, rowIndex) in cellRows(block)" :key="rowIndex"><td v-for="(cell, columnIndex) in row" :key="columnIndex" :class="{ target: selectedIndex === index && selectedCell(cell, columnIndex) }"><template v-for="(part, partIndex) in textParts(cell.text, selectedIndex === index && selectedCell(cell, columnIndex))" :key="partIndex"><mark v-if="part.highlight">{{ part.text }}</mark><template v-else>{{ part.text }}</template></template></td></tr></tbody></table></div>
                <p v-else class="block-text"><template v-for="(part, partIndex) in textParts(block.text || '', selectedIndex === index)" :key="partIndex"><mark v-if="part.highlight">{{ part.text }}</mark><template v-else>{{ part.text }}</template></template></p>
              </article>
              <p v-if="selectedIndex < 0" class="preview-note">当前内容未取得唯一锚点匹配，未自动高亮。可结合原件与引用片段核对。</p>
            </template>
            <div v-else class="preview-empty"><FileText /><h3>暂无可展示的结构化原文</h3><p>材料已保留，可打开原件核对并补充证据。</p></div>
          </template>
        </div>
        <footer class="preview-footer">
          <p>修订保存为新版本，原件独立保留。</p>
          <a v-if="safeUrl(preview?.content_url)" :href="safeUrl(preview?.content_url)" target="_blank" rel="noopener"><Download :size="14" />打开 / 下载原件<ArrowUpRight :size="12" /></a>
        </footer>
      </section>
    </div>
  </Teleport>
</template>
<style scoped>
.preview-overlay { position: fixed; inset: 0; z-index: 60; background: #16132766; display: flex; justify-content: flex-end; backdrop-filter: blur(2px); }
.material-preview { width: min(1040px, 83vw); height: 100dvh; background: var(--surface); box-shadow: -15px 0 70px #21174420; display: flex; flex-direction: column; min-width: 0; }
.preview-header { padding: 19px 24px; border-bottom: 1px solid var(--line); display: flex; align-items: center; justify-content: space-between; gap: 18px; }.preview-header > div { min-width: 0; }.preview-header h2 { margin-top: 4px; font-size: 16px; overflow-wrap: anywhere; }
.preview-context { background: #faf9fd; padding: 13px 24px; display: flex; align-items: center; justify-content: space-between; gap: 12px; border-bottom: 1px solid var(--line); font-size: 12px; }.preview-context > div { display: flex; flex-wrap: wrap; align-items: center; gap: 12px; }.preview-context span { color: var(--muted); }.preview-context button { flex-shrink: 0; font-size: 12px; }
.preview-content { padding: 20px 24px 30px; overflow: auto; flex: 1; min-height: 0; }.preview-empty { display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 280px; gap: 12px; text-align: center; color: var(--muted); }.preview-empty p { max-width: 430px; font-size: 12px; line-height: 1.8; }
.preview-location { display: flex; align-items: flex-start; gap: 9px; padding: 12px 14px; margin-bottom: 16px; border: 1px solid #dfd7fb; border-radius: 9px; background: var(--primary-soft); font-size: 12px; color: var(--primary); }.preview-location p { font-size: 11px; margin-top: 3px; overflow-wrap: anywhere; }.preview-location.warning { border-color: #f1e1bd; background: var(--amber-soft); color: var(--amber); }
.structure-caption { margin: 18px 0 10px; display: grid; gap: 4px; font-size: 12px; }.structure-caption span, .preview-note { color: var(--muted); font-size: 11px; line-height: 1.7; }.preview-note { padding: 8px 0 14px; }
.representation-tabs { display: flex; gap: 8px; padding: 12px 24px 0; border-bottom:1px solid var(--line); background:var(--surface); }.representation-tabs button { font-size: 13px; padding: 11px 16px; border:0; border-bottom:2px solid transparent; border-radius:6px 6px 0 0; box-shadow:none; }.representation-tabs button.active { background: var(--primary-soft); color: var(--primary); border-bottom-color:var(--primary); }
.preview-block { border: 1px solid var(--line); border-radius: 8px; margin: 10px 0; overflow: hidden; scroll-margin: 18px; }.preview-block.selected { border-color: #c6b4f7; box-shadow: 0 0 0 3px #6d4be80c; }.block-location { background: #f9f9fc; padding: 8px 12px; font-size: 10px; color: var(--muted); display: flex; align-items: center; justify-content: space-between; gap: 12px; overflow-wrap: anywhere; }.block-location b { color: var(--primary); white-space: nowrap; font-weight: 500; }
.block-text { padding: 13px; white-space: pre-wrap; font-size: 13px; overflow-wrap: anywhere; line-height: 1.9; }.preview-table-scroll { overflow: auto; }.preview-table { width: 100%; border-collapse: collapse; font-size: 12px; }.preview-table td { padding: 11px 13px; border: 1px solid var(--line); white-space: pre-wrap; min-width: 80px; max-width: 340px; overflow-wrap: anywhere; }.preview-table td.target { background: #fff7dc; outline: 1px solid #d4a33e; outline-offset: -1px; }mark { background: #ffe29b; color: inherit; border-radius: 2px; padding: 1px 0; }
.image-preview { position: relative; width: 100%; }.image-preview img { display: block; width: 100%; height: auto; border: 1px solid var(--line); }.image-evidence-box { position: absolute; border: 2px solid #d89a0f; background: #ffdc6b33; pointer-events: none; }
.preview-footer { padding: 14px 24px; border-top: 1px solid var(--line); display: flex; justify-content: space-between; align-items: center; gap: 14px; font-size: 11px; color: var(--muted); }.preview-footer a { display: inline-flex; align-items: center; gap: 7px; flex-shrink: 0; }
@media(max-width: 760px) { .material-preview { width: 100vw; }.preview-header, .preview-context, .preview-footer { padding-left: 16px; padding-right: 16px; }.preview-content { padding: 14px 16px; }.preview-footer { flex-wrap: wrap; } }
</style>
