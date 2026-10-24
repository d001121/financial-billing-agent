<script setup lang="ts">
import ocean from "../assets/ocean-panorama.webp";
defineProps<{ animated: boolean }>();
</script>

<template>
  <div class="ocean-backdrop" :class="{ 'ocean-animated': animated }" aria-hidden="true">
    <img :src="ocean" alt="" width="1600" height="240" fetchpriority="high" />
    <img class="ocean-reflection" :src="ocean" alt="" width="1600" height="240" />
  </div>
</template>

<style scoped>
.ocean-backdrop { position: absolute; inset: 0; overflow: hidden; pointer-events: none; background: #d5e6e5; }
.ocean-backdrop img { width: 100%; height: 100%; object-fit: cover; object-position: center 20%; display: block; }
.ocean-backdrop > img:first-child { opacity: .68; }
.ocean-reflection { position: absolute; inset: 0; opacity: 0; mix-blend-mode: screen; }
.ocean-animated > img:first-child { animation: sea-drift 28s ease-in-out infinite alternate; }
.ocean-animated .ocean-reflection { animation: sea-light 18s ease-in-out infinite alternate; }
@keyframes sea-drift { from { transform: scale(1.035) translate3d(-.5%, 0, 0); } to { transform: scale(1.06) translate3d(.5%, -.5%, 0); } }
@keyframes sea-light { from { opacity: .025; transform: scale(1.08) translate3d(-.7%, .4%, 0); } to { opacity: .1; transform: scale(1.06) translate3d(.7%, -.4%, 0); } }
@media (prefers-reduced-motion: reduce) { .ocean-backdrop img { animation: none !important; } }
</style>
