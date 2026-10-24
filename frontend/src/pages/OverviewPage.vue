<script setup lang="ts">
import ControlScreenPage from "./ControlScreenPage.vue";
import type { Task } from "../types/contracts";
import type { TaskFilter } from "../utils/taskPresentation";
defineProps<{ tasks: Task[]; loading: boolean; stale: boolean; updatedAt: string; motionActive?: boolean }>();
const emit = defineEmits<{ create: []; open: [task: Task]; filter: [filter: TaskFilter]; screen: [] }>();
</script>
<template><ControlScreenPage :tasks="tasks" :loading="loading" :stale="stale" :updated-at="updatedAt" :motion-active="motionActive" @create="emit('create')" @open="emit('open', $event)" @filter="emit('filter', $event)" /></template>
