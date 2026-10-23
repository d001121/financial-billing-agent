<script setup lang="ts">
import { ref } from "vue";
import { CircleAlert, LoaderCircle, ShieldCheck, X } from "@lucide/vue";
import { ApiError, api, errorMessage } from "../api/client";
import type { Task } from "../types/contracts";
const props = defineProps<{ task: Task }>();
const emit = defineEmits<{ close: []; saved: [task: Task] }>();
const revision = props.task.revision,
  reason = ref(""),
  decision = ref<"approve" | "reject">("approve"),
  busy = ref(false),
  error = ref(""),
  conflict = ref(false);
async function save() {
  error.value = "";
  if (!reason.value.trim()) {
    error.value = "请填写本次审核依据。";
    return;
  }
  busy.value = true;
  try {
    emit(
      "saved",
      await api.approve(props.task.id, {
        expected_revision: revision,
        decision: decision.value,
        reason: reason.value.trim(),
      }),
    );
  } catch (e) {
    conflict.value = e instanceof ApiError && e.status === 409;
    error.value = conflict.value
      ? "此结果已更新，请关闭后查看最新 Revision 再审核。当前输入已保留。"
      : errorMessage(e);
  } finally {
    busy.value = false;
  }
}
</script>
<template>
  <div
    class="modal-overlay"
    @click.self="!busy && emit('close')"
    @keydown.esc="!busy && emit('close')"
  >
    <form
      class="modal approval-modal"
      role="dialog"
      aria-modal="true"
      aria-labelledby="approval-title"
      @submit.prevent="save"
    >
      <div class="modal-head">
        <div>
          <span class="eyebrow">REVIEW · REVISION {{ revision }}</span>
          <h2 id="approval-title">审核当前费用结果</h2>
        </div>
        <button
          type="button"
          class="icon ghost"
          aria-label="关闭"
          :disabled="busy"
          @click="emit('close')"
        >
          <X />
        </button>
      </div>
      <div class="modal-body">
        <div class="notice">
          <ShieldCheck /><span
            >审核仅对当前 Revision
            生效。正式导出须同时通过服务端必需校验；修改后需要重新审核。</span
          >
        </div>
        <div class="field">
          <label for="approval-decision">审核结论</label
          ><select id="approval-decision" v-model="decision">
            <option value="approve">批准当前结果</option>
            <option value="reject">驳回，需进一步核对</option>
          </select>
        </div>
        <div class="field">
          <label for="approval-reason">审核依据</label
          ><textarea
            id="approval-reason"
            v-model="reason"
            placeholder="说明已核对的材料和结论。"
            rows="3"
          />
        </div>
        <div v-if="error" class="notice error" role="alert">
          <CircleAlert /><span>{{ error }}</span>
        </div>
      </div>
      <div class="modal-foot">
        <button type="button" :disabled="busy" @click="emit('close')">
          取消</button
        ><button class="primary" type="submit" :disabled="busy || conflict">
          <LoaderCircle v-if="busy" class="loading-icon" /><ShieldCheck
            v-else
          />提交审核
        </button>
      </div>
    </form>
  </div>
</template>
<style scoped>
.approval-modal {
  width: 530px;
}
.modal-head .eyebrow {
  font-size: 11px;
}
.modal-head h2 {
  margin-top: 5px;
}
</style>
