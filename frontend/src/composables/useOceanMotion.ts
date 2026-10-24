import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";

const preferenceKey = "harbor.ocean-motion";

export function useOceanMotion() {
  const enabled = ref(true);
  try {
    enabled.value = localStorage.getItem(preferenceKey) !== "off";
  } catch {
    // The visual preference still works when browser storage is unavailable.
  }
  const reduced = ref(window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  const active = computed(() => enabled.value && !reduced.value);
  let media: MediaQueryList | undefined;
  const update = (event: MediaQueryListEvent) => { reduced.value = event.matches; };
  onMounted(() => {
    media = window.matchMedia("(prefers-reduced-motion: reduce)");
    reduced.value = media.matches;
    media.addEventListener("change", update);
  });
  onBeforeUnmount(() => media?.removeEventListener("change", update));
  watch(enabled, value => {
    try { localStorage.setItem(preferenceKey, value ? "on" : "off"); } catch { /* Local preference only. */ }
  });
  return { enabled, reduced, active };
}
