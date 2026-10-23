<script setup lang="ts">
import MarkdownIt from 'markdown-it';
import { computed } from 'vue';
const props = defineProps<{ text: string }>();
// Raw HTML stays text; markdown-it's URL validation also rejects javascript:.
const markdown = new MarkdownIt({ html: false, breaks: true, linkify: false });
markdown.renderer.rules.image = (tokens, index) => markdown.utils.escapeHtml(tokens[index]?.content || '图片');
const rendered = computed(() => markdown.render(props.text));
</script>

<template><div class="agent-markdown" v-html="rendered" /></template>

<style scoped>
.agent-markdown { font-size:13px; line-height:1.85; overflow-wrap:anywhere; min-width:0; }
.agent-markdown :deep(> :first-child) { margin-top:0; }
.agent-markdown :deep(> :last-child) { margin-bottom:0; }
.agent-markdown :deep(p) { margin:0 0 10px; }
.agent-markdown :deep(h1),.agent-markdown :deep(h2),.agent-markdown :deep(h3) { font-size:14px; margin:16px 0 8px; }
.agent-markdown :deep(ul),.agent-markdown :deep(ol) { padding-left:20px; margin:8px 0; }
.agent-markdown :deep(table) { display:block; max-width:100%; overflow:auto; border-collapse:collapse; font-size:12px; margin:12px 0; }
.agent-markdown :deep(td),.agent-markdown :deep(th) { padding:8px 12px; border:1px solid var(--line); text-align:left; min-width:70px; }
.agent-markdown :deep(th) { background:var(--surface-alt, #f5f8f6); font-weight:600; }
.agent-markdown :deep(pre) { max-width:100%; overflow:auto; padding:12px; background:#f3f6f4; border-radius:8px; white-space:pre-wrap; }
.agent-markdown :deep(code) { font:12px/1.7 Consolas,monospace; }
.agent-markdown :deep(blockquote) { margin:12px 0; padding:0 12px; border-left:2px solid var(--line); color:var(--muted); }
.agent-markdown :deep(a) { color:var(--primary); text-decoration:underline; }
.agent-markdown :deep(img) { max-width:100%; }
</style>
