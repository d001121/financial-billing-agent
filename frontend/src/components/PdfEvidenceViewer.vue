<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from "vue";
import { ChevronLeft, ChevronRight, LoaderCircle } from "@lucide/vue";
import type { PDFDocumentProxy, PDFDocumentLoadingTask, RenderTask, TextLayer } from "pdfjs-dist";
import workerUrl from "pdfjs-dist/build/pdf.worker.min.mjs?url";
import "pdfjs-dist/web/pdf_viewer.css";
import type { OriginalLocation, PreviewTarget } from "../types/contracts";

const props = defineProps<{ url: string; target: PreviewTarget; original?: OriginalLocation; amount?: number | null; derived?: boolean }>();
const canvas = ref<HTMLCanvasElement | null>(null), textContainer = ref<HTMLElement | null>(null),
  stage = ref<HTMLElement | null>(null), pageNumber = ref(1), pageCount = ref(0),
  loading = ref(false), error = ref(""), location = ref(""), highlights = ref<{left:number;top:number;width:number;height:number}[]>([]);
let documentTask: PDFDocumentLoadingTask | undefined, document: PDFDocumentProxy | undefined,
  renderTask: RenderTask | undefined, layer: TextLayer | undefined, epoch = 0;
const selectedMatch = ref(0);
const originalMarks = computed(() => props.original?.locations.flatMap((match, index) =>
  match.page === pageNumber.value ? match.boxes.map(box => ({...box, selected:index === selectedMatch.value})) : []) || []);
const initialPage = () => props.original?.locations[selectedMatch.value]?.page || props.target.page || 1;

function scrollToMark() {
  requestAnimationFrame(() => {
    const mark = stage.value?.querySelector<HTMLElement>('.pdf-evidence-mark.selected, .pdf-evidence-mark');
    const scroll = stage.value?.parentElement;
    if (mark && scroll) scroll.scrollTo({top:Math.max(0,mark.offsetTop-scroll.clientHeight/2), behavior:'smooth'});
  });
}

function locateText() {
  highlights.value = [];
  if (props.original) {
    location.value = props.original.locations.some(match => match.page === pageNumber.value)
      ? props.original.reason : props.original.locations.length ? '当前页无所选引用，可用“对应位置”返回标注处。' : props.original.reason;
    scrollToMark();
    return;
  }
  if (!layer || !textContainer.value || !stage.value) return;
  if (!props.target.located || !Number.isInteger(props.target.page) || (props.target.page || 0) < 1) {
    location.value = "缺少可核验的对应页映射，仅展示当前页，未自动标记。";
    return;
  }
  if (props.target.page !== pageNumber.value) {
    location.value = `引用对应第 ${props.target.page} 页；当前页未自动标记。`;
    return;
  }
  const pointers: ({node: Text; offset: number} | null)[] = [];
  let raw = "";
  for (const span of layer.textDivs) {
    const node = span.firstChild;
    if (!(node instanceof Text)) continue;
    for (let i = 0; i < node.length; i++) { raw += node.data[i]; pointers.push({ node, offset: i }); }
    raw += " "; pointers.push(null);
  }
  const quote = props.target.quote || "";
  const normalized: number[] = [];
  for (let i = 0; i < raw.length; i++) if (!/\s/.test(raw[i] || "")) normalized.push(i);
  const plain = normalized.map(i => raw[i]).join("");
  const needle = quote.replace(/\s/g, "");
  let rangeStart = 0, rangeEnd = raw.length, quoteMatched = false;
  if (needle) {
    const at = plain.indexOf(needle);
    if (at >= 0 && plain.indexOf(needle, at + 1) < 0) {
      rangeStart = normalized[at] ?? 0;
      rangeEnd = (normalized[at + needle.length - 1] ?? rangeStart) + 1;
      quoteMatched = true;
    }
  }
  if (!quoteMatched) {
    location.value = raw.trim() ? "仅展示对应页：未找到唯一原文上下文，未自动标记。" : "仅展示对应页：此页没有可搜索文本层。";
    return;
  }
  if (props.target.field?.split(".").at(-1) === "amount" && props.amount != null) {
    const found = [...raw.matchAll(/[-+]?\d[\d,]*(?:\.\d+)?/g)].filter(match => {
      const at = match.index ?? 0;
      return at >= rangeStart && at < rangeEnd && Number(match[0].replace(/,/g, "")) === props.amount;
    });
    if (found.length === 1) { rangeStart = found[0]!.index!; rangeEnd = rangeStart + found[0]![0].length; }
    else { location.value = found.length > 1 ? "本页存在多个相同金额，请结合上下文核对；未自动标记。" : "仅展示当前页：文本层中未找到对应金额。"; return; }
  }
  while (!pointers[rangeStart] && rangeStart < rangeEnd) rangeStart++;
  while (!pointers[rangeEnd - 1] && rangeEnd > rangeStart) rangeEnd--;
  const start = pointers[rangeStart], end = pointers[rangeEnd - 1];
  if (!start || !end) return;
  const range = window.document.createRange();
  range.setStart(start.node, start.offset); range.setEnd(end.node, end.offset + 1);
  const containerRect = stage.value.getBoundingClientRect();
  highlights.value = [...range.getClientRects()].filter(rect => rect.width && rect.height).map(rect => ({
    left: rect.left - containerRect.left, top: rect.top - containerRect.top, width: rect.width, height: rect.height,
  }));
  location.value = highlights.value.length ? "已在当前页文本层定位对应内容。" : "仅展示当前页：未取得可展示的位置。";
  requestAnimationFrame(() => stage.value?.querySelector(".pdf-evidence-mark")?.scrollIntoView({ block: "center", behavior: "smooth" }));
}

async function renderPage() {
  if (!document) return;
  const token = ++epoch;
  renderTask?.cancel(); layer?.cancel(); highlights.value = []; loading.value = true; error.value = "";
  try {
    const page = await document.getPage(pageNumber.value);
    if (token !== epoch) return;
    await nextTick();
    if (!canvas.value || !textContainer.value || !stage.value) return;
    const width = Math.max(280, stage.value.parentElement?.clientWidth || 760);
    const scale = Math.min(1.8, width / page.getViewport({ scale: 1 }).width);
    const viewport = page.getViewport({ scale });
    const ratio = Math.min(window.devicePixelRatio || 1, 2);
    canvas.value.width = Math.floor(viewport.width * ratio); canvas.value.height = Math.floor(viewport.height * ratio);
    canvas.value.style.width = `${viewport.width}px`; canvas.value.style.height = `${viewport.height}px`;
    stage.value.style.width = `${viewport.width}px`; stage.value.style.height = `${viewport.height}px`;
    stage.value.style.setProperty("--total-scale-factor", String(scale));
    renderTask = page.render({ canvas: canvas.value, viewport, transform: ratio === 1 ? undefined : [ratio, 0, 0, ratio, 0, 0] });
    await renderTask.promise;
    if (token !== epoch) return;
    textContainer.value.replaceChildren();
    const { TextLayer: Layer } = await import("pdfjs-dist");
    layer = new Layer({ textContentSource: await page.getTextContent(), container: textContainer.value, viewport });
    await layer.render();
    if (token === epoch) { loading.value = false; await nextTick(); locateText(); }
  } catch (e) {
    if (token !== epoch || (e instanceof Error && e.name === "RenderingCancelledException")) return;
    error.value = e instanceof Error ? e.message : "PDF预览未完成，可下载原件核对。";
  } finally { if (token === epoch) loading.value = false; }
}

watch(() => props.url, async url => {
  const token = ++epoch;
  renderTask?.cancel(); layer?.cancel(); await documentTask?.destroy(); document = undefined;
  loading.value = true; error.value = ""; location.value = ""; highlights.value = [];
  try {
    const pdfjs = await import("pdfjs-dist"); pdfjs.GlobalWorkerOptions.workerSrc = workerUrl;
    if (token !== epoch) return;
    const loadingTask = pdfjs.getDocument({ url, useSystemFonts: true });
    documentTask = loadingTask;
    const loaded = await loadingTask.promise;
    if (token !== epoch) { await loadingTask.destroy(); return; }
    document = loaded;
    pageCount.value = document.numPages;
    selectedMatch.value = 0;
    pageNumber.value = Math.max(1, Math.min(initialPage(), document.numPages));
    await renderPage();
  } catch (e) { if (token === epoch) { loading.value = false; error.value = e instanceof Error ? e.message : "无法打开PDF。"; } }
}, { immediate: true });
watch(() => [props.target.anchor, props.target.quote, props.target.field, props.target.page, props.amount, props.original], async () => {
  if (!document) return;
  selectedMatch.value = 0;
  const page = Math.max(1, Math.min(initialPage(), pageCount.value));
  if (page !== pageNumber.value) { pageNumber.value = page; await renderPage(); }
  else if (!loading.value) locateText();
});
function changePage(delta: number) { pageNumber.value += delta; void renderPage(); }
async function chooseMatch(index: number) {
  selectedMatch.value = index;
  const page = initialPage();
  if (page !== pageNumber.value) { pageNumber.value = page; await renderPage(); }
  else scrollToMark();
}
onBeforeUnmount(() => { ++epoch; renderTask?.cancel(); layer?.cancel(); void documentTask?.destroy(); });
</script>
<template>
  <section class="pdf-evidence-viewer" aria-label="PDF原页预览">
    <div class="pdf-controls">
      <button class="icon ghost" aria-label="上一页" :disabled="pageNumber <= 1 || loading" @click="changePage(-1)"><ChevronLeft /></button>
      <span>{{ derived ? '渲染' : '' }}第 {{ pageNumber }} / {{ pageCount || '…' }} 页</span>
      <button class="icon ghost" aria-label="下一页" :disabled="pageNumber >= pageCount || loading" @click="changePage(1)"><ChevronRight /></button>
      <button v-if="original?.locations.length" class="ghost return-location" @click="chooseMatch(selectedMatch)">返回对应位置</button>
    </div>
    <div v-if="(original?.locations.length || 0) > 1" class="pdf-matches" aria-label="原件匹配位置"><button v-for="(match,index) in original?.locations" :key="index" :class="{active:selectedMatch === index}" @click="chooseMatch(index)">位置 {{index+1}} · 第 {{match.page}} 页</button></div>
    <p v-if="loading" class="pdf-status" role="status"><LoaderCircle class="loading-icon" />正在渲染原页…</p>
    <p v-if="error" class="notice error" role="alert">{{ error }}</p>
    <p v-else-if="location" class="pdf-location" role="status">{{ location }}</p>
    <div class="pdf-scroll">
      <div ref="stage" class="pdf-stage">
        <canvas ref="canvas" />
        <div ref="textContainer" class="textLayer" />
        <span v-for="(rect,index) in originalMarks" :key="'original-'+index" class="pdf-evidence-mark" :class="{selected:rect.selected}" :style="{left:rect.x*100+'%',top:rect.y*100+'%',width:rect.width*100+'%',height:rect.height*100+'%'}" />
        <span v-for="(rect, index) in highlights" :key="index" class="pdf-evidence-mark" :style="{ left: rect.left+'px', top: rect.top+'px', width: rect.width+'px', height: rect.height+'px' }" />
      </div>
    </div>
  </section>
</template>
<style scoped>
.pdf-evidence-viewer { min-width: 0; }.pdf-controls { display: flex; align-items: center; gap: 8px; padding: 6px 0; font-size: 12px; }.pdf-controls small { color: var(--muted); margin-left: auto; font-size: 11px; }
.pdf-status, .pdf-location { padding: 8px 0; color: var(--muted); font-size: 12px; display: flex; align-items: center; gap: 7px; }
.pdf-controls { flex-wrap:wrap; }.return-location { margin-left:auto; font-size:11px; }.pdf-matches {display:flex;flex-wrap:wrap;gap:6px;margin:8px 0;}.pdf-matches button {font-size:11px;}.pdf-matches button.active {background:var(--primary-soft);color:var(--primary);}
.pdf-scroll { background: #e9e8ef; overflow: auto; border: 1px solid var(--line); border-radius: 8px; padding: 8px; max-height: 68vh; }
.pdf-stage { position: relative; margin: 0 auto; background: white; }.pdf-stage canvas { display: block; }.pdf-evidence-mark { position: absolute; background: #ffcb436b; border: 1px solid #d79b1b; border-radius: 2px; pointer-events: none; z-index: 2; scroll-margin: 60px; }
</style>
