<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from "vue";
import ocean from "../assets/ocean-panorama.webp";
const props = defineProps<{ animated: boolean }>();
const canvas = ref<HTMLCanvasElement>();
const ready = ref(false);
let frame = 0;
let render: ((time: number) => void) | undefined;
let cleanup: (() => void) | undefined;
function resume() {
  cancelAnimationFrame(frame);
  if (props.animated && !document.hidden && ready.value) frame = requestAnimationFrame(tick);
}
function tick(time: number) {
  render?.(time);
  if (props.animated && !document.hidden) frame = requestAnimationFrame(tick);
}
watch(() => props.animated, resume);
onMounted(() => {
  const element = canvas.value!;
  const gl = element.getContext("webgl", { alpha: false, antialias: false, powerPreference: "low-power" });
  if (!gl) return;
  const compile = (type: number, source: string) => {
    const shader = gl.createShader(type)!;
    gl.shaderSource(shader, source); gl.compileShader(shader);
    if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) { gl.deleteShader(shader); return null; }
    return shader;
  };
  const vertex = compile(gl.VERTEX_SHADER, "attribute vec2 a; varying vec2 uv; void main(){uv=a*.5+.5;gl_Position=vec4(a,0.,1.);}");
  const fragment = compile(gl.FRAGMENT_SHADER, `precision mediump float; uniform sampler2D photo; uniform float time; varying vec2 uv;
    void main(){vec2 p=uv; float wave=sin(p.x*35.+time*.85)+sin(p.x*67.-time*1.2)*.4;
    p.y=.56+(p.y-.5)*.30+wave*.027; p.x+=sin(p.y*34.+time*.65)*.003;
    gl_FragColor=vec4(texture2D(photo,p).rgb*.83,1.);}`);
  if (!vertex || !fragment) return;
  const program = gl.createProgram()!;
  gl.attachShader(program, vertex); gl.attachShader(program, fragment); gl.linkProgram(program);
  if (!gl.getProgramParameter(program, gl.LINK_STATUS)) return;
  gl.useProgram(program);
  const buffer = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1,-1,1,-1,-1,1,-1,1,1,-1,1,1]), gl.STATIC_DRAW);
  const position = gl.getAttribLocation(program, "a"); gl.enableVertexAttribArray(position); gl.vertexAttribPointer(position, 2, gl.FLOAT, false, 0, 0);
  const texture = gl.createTexture(); gl.bindTexture(gl.TEXTURE_2D, texture);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
  const timeUniform = gl.getUniformLocation(program, "time");
  render = time => {
    const width = Math.round(element.clientWidth * Math.min(devicePixelRatio, 1.5));
    const height = Math.round(element.clientHeight * Math.min(devicePixelRatio, 1.5));
    if (element.width !== width || element.height !== height) { element.width = width; element.height = height; gl.viewport(0, 0, width, height); }
    gl.uniform1f(timeUniform, time / 1000); gl.drawArrays(gl.TRIANGLES, 0, 6);
  };
  const image = new Image();
  let disposed = false;
  image.onload = () => {
    if (disposed) return;
    gl.bindTexture(gl.TEXTURE_2D, texture); gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, true);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGB, gl.RGB, gl.UNSIGNED_BYTE, image);
    ready.value = true; render?.(0); resume();
  };
  image.src = ocean;
  document.addEventListener("visibilitychange", resume);
  cleanup = () => { disposed = true; image.onload = null; document.removeEventListener("visibilitychange", resume); gl.deleteBuffer(buffer); gl.deleteTexture(texture); gl.deleteProgram(program); gl.deleteShader(vertex); gl.deleteShader(fragment); };
});
onBeforeUnmount(() => { cancelAnimationFrame(frame); cleanup?.(); });
</script>

<template><div class="ocean-backdrop" aria-hidden="true"><img :src="ocean" alt="" width="1600" height="240" fetchpriority="high"/><canvas ref="canvas" :class="{ ready }"/></div></template>
<style scoped>
.ocean-backdrop { position: absolute; inset: 0; overflow: hidden; pointer-events: none; background: #21394b; }
.ocean-backdrop img,.ocean-backdrop canvas { width: 100%; height: 100%; position: absolute; inset: 0; display: block; }
.ocean-backdrop img { object-fit: cover; object-position: center 56%; filter: brightness(.83); }
.ocean-backdrop canvas { opacity: 0; }.ocean-backdrop canvas.ready { opacity: 1; }
</style>
