<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from "vue";
import { init, use, type EChartsCoreOption, type EChartsType } from "echarts/core";
import { BarChart, LineChart, HeatmapChart, ScatterChart } from "echarts/charts";
import { GridComponent, TooltipComponent, DataZoomComponent, MarkLineComponent, VisualMapComponent, AriaComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";

use([BarChart, LineChart, HeatmapChart, ScatterChart, GridComponent, TooltipComponent,
  DataZoomComponent, MarkLineComponent, VisualMapComponent, AriaComponent, CanvasRenderer]);
const props = defineProps<{ option: EChartsCoreOption; label: string }>();
const emit = defineEmits<{ select: [value: { name: string; value: unknown }]; zoom: [value: unknown] }>();
const root = ref<HTMLDivElement>();
let chart: EChartsType | undefined;
let resize: ResizeObserver | undefined;
watch(() => props.option, (value, previous) => {
  // Summary polling must not restart an unchanged chart or dismiss its tooltip.
  if (JSON.stringify(value) !== JSON.stringify(previous)) chart?.setOption(value, { notMerge: true });
});
onMounted(() => {
  chart = init(root.value!, undefined, { renderer: "canvas" });
  chart.setOption(props.option);
  chart.on("click", (event: unknown) => emit("select", event as { name: string; value: unknown }));
  chart.on("datazoom", (event: unknown) => emit("zoom", event));
  resize = new ResizeObserver(() => chart?.resize());
  resize.observe(root.value!);
});
onBeforeUnmount(() => { resize?.disconnect(); chart?.dispose(); });
</script>

<template><div ref="root" class="analytics-chart" role="img" :aria-label="label" /></template>

<style scoped>
.analytics-chart { width: 100%; min-width: 0; height: 100%; }
</style>
