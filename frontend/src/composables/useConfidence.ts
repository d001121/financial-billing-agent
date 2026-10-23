import { computed, ref, watch } from "vue";
import { api, errorMessage } from "../api/client";
import type { ConfidenceReport, Task } from "../types/contracts";

export function useConfidence(task: () => Task) {
  const report = ref<ConfidenceReport | null>(null);
  const loading = ref(false), error = ref(""), retry = ref(0);
  // Agent artifacts can change within one revision. Ignore unchanged poll objects.
  const signature = computed(() => {
    const value = task();
    const limits = value.capability?.config?.runtime;
    const activeSeconds = Number(value.usage?.active_seconds || 0);
    const timeLimit = Number(limits?.active_seconds);
    // Match the budget validation's strict > check, without rescoring each tick.
    const timeExceeded = Number.isFinite(timeLimit) && activeSeconds > timeLimit;
    return JSON.stringify([value.id, value.revision, value.accounting_entity,
      value.records, value.charges, value.totals, value.coverage, value.validation,
      value.issues, value.sources, value.capability?.version, limits,
      value.usage?.model_calls ?? 0, value.usage?.tool_calls ?? 0, timeExceeded]);
  });
  // Only the newest request may publish.  Requiring the whole signature to be
  // unchanged discarded every response while records changed mid-revision,
  // which made the panel's score appear and vanish in bursts.
  let sequence = 0;
  watch(() => JSON.stringify([signature.value, retry.value]), (_, __, cleanup) => {
    const controller = new AbortController();
    const value = task();
    const request = ++sequence;
    loading.value = true; error.value = "";
    const timer = window.setTimeout(async () => {
      try {
        const result = await api.confidence(value.id, controller.signal);
        if (request === sequence && !controller.signal.aborted &&
            result.revision === task().revision) report.value = result;
      } catch (failure) {
        if (request === sequence && !controller.signal.aborted) error.value = errorMessage(failure);
      } finally {
        if (request === sequence && !controller.signal.aborted) loading.value = false;
      }
    }, 350);
    cleanup(() => { window.clearTimeout(timer); controller.abort(); });
  }, { immediate: true });
  const byCharge = computed(() => new Map(report.value?.records.map(row => [row.charge_id, row]) || []));
  const candidates = computed(() => report.value?.records.filter(row => row.origin === "charges" && row.record).map(row => row.record!) || []);
  const unavailableReason = computed(() => report.value?.method === "unavailable" && typeof report.value.summary === "string" ? report.value.summary : "");
  const quickConfirm = computed(() => {
    const value = task(), rows = value.records || [];
    return !!report.value && report.value.revision === value.revision && rows.length > 0 &&
      !report.value.blockers.length && rows.every(row => {
        const result = byCharge.value.get(row.charge_id);
        return result?.origin !== "charges" && result?.eligible_for_quick_confirm === true;
      });
  });
  return { report, loading, error, byCharge, candidates, quickConfirm, unavailableReason, reload: () => retry.value++ };
}
