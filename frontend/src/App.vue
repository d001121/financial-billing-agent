<script setup lang="ts">
import {
  computed,
  defineAsyncComponent,
  onBeforeUnmount,
  onMounted,
  ref,
  watch,
} from "vue";
import {
  Anchor,
  ArrowLeft,
  CircleAlert,
  ClipboardCheck,
  FolderOpen,
  LayoutDashboard,
  LoaderCircle,
  Menu,
  Monitor,
  RefreshCw,
  Settings2,
  UploadCloud,
  Waves,
  X,
} from "@lucide/vue";
import { api, errorMessage } from "./api/client";
import {
  type Asset,
  type Health,
  type Task,
} from "./types/contracts";
import { taskCategory, type TaskFilter } from "./utils/taskPresentation";
import TaskCenterPage from "./pages/TaskCenterPage.vue";
import TaskComposer from "./components/TaskComposer.vue";
import OceanBackdrop from "./components/OceanBackdrop.vue";
import { useOceanMotion } from "./composables/useOceanMotion";
const oceanMotion = useOceanMotion();
const TaskWorkspace = defineAsyncComponent(
  () => import("./components/TaskWorkspace.vue"),
);
const ControlScreenPage = defineAsyncComponent(
  () => import("./pages/ControlScreenPage.vue"),
);
const ManagementPage = defineAsyncComponent(
  () => import("./pages/ManagementPage.vue"),
);

type Page =
  | "overview"
  | "tasks"
  | "review"
  | "new"
  | "detail"
  | "management"
  | "capabilities"
  | "improvements"
  | "traces"
  | "screen";
function readRoute(): { page: Page; id: string; filter: TaskFilter } {
  const [path, query] = window.location.hash.slice(1).split("?");
  const filter = new URLSearchParams(query).get("status") || "all";
  const status: TaskFilter = [
    "all",
    "review",
    "active",
    "completed",
    "attention",
  ].includes(filter)
    ? (filter as TaskFilter)
    : "all";
  if (path?.startsWith("/tasks/")) {
    try {
      return {
        page: "detail",
        id: decodeURIComponent(path.slice(7)),
        filter: status,
      };
    } catch {
      return { page: "tasks", id: "", filter: "all" };
    }
  }
  const pages: Record<string, Page> = {
    "/overview": "overview",
    "/tasks": "tasks",
    "/review": "review",
    "/new": "new",
    "/management": "management",
    "/management/capabilities": "capabilities",
    "/management/improvements": "improvements",
    "/management/traces": "traces",
    "/screen": "screen",
  };
  return { page: pages[path || ""] || "overview", id: "", filter: status };
}
const route = ref(readRoute());
const tasks = ref<Task[]>([]),
  assets = ref<Asset[]>([]),
  health = ref<Health | null>(null);
const removedTaskIds = new Set<string>();
function removeTasks(ids: string[]) {
  ids.forEach((id) => removedTaskIds.add(id));
  tasks.value = tasks.value.filter((task) => !removedTaskIds.has(task.id));
  if (removedTaskIds.has(localStorage.getItem("harbor.task") || "")) {
    localStorage.removeItem("harbor.task");
    improvementTask.value = "";
  }
}
const loading = ref(true),
  refreshing = ref(false),
  stale = ref(false),
  error = ref(""),
  updatedAt = ref("");
const currentTask = ref<Task | null>(null),
  detailLoading = ref(false),
  detailError = ref("");
const mobileNav = ref(false),
  composerKey = ref(0),
  improvementTask = ref(localStorage.getItem("harbor.task") || "");
const returnPage = ref("/tasks");
const page = computed(() => route.value.page);
const reviewCount = computed(
  () => tasks.value.filter((t) => taskCategory(t) === "review").length,
);
const isManagement = computed(() =>
  ["management", "capabilities", "improvements", "traces"].includes(page.value),
);
const pageLabel = computed(
  () =>
    ({
      overview: "工作总览",
      tasks: "账单业务中心",
      review: "待办复核",
      new: "提交新材料",
      detail: "账单详情",
      management: "管理员控制台",
      capabilities: "能力与连接",
      improvements: "进化库",
      traces: "Trace 追踪",
      screen: "大屏总控",
    })[page.value],
);
function navigate(path: string) {
  mobileNav.value = false;
  window.location.hash = path;
}
function showFilter(filter: TaskFilter) {
  navigate("/tasks" + (filter === "all" ? "" : "?status=" + filter));
}
function focusMain() {
  document.getElementById("workspace-main")?.focus();
}
function closeMobileNav() {
  mobileNav.value = false;
  document.getElementById("mobile-menu-button")?.focus();
}
function keyDown(event: KeyboardEvent) {
  if (event.key === "Escape" && mobileNav.value) closeMobileNav();
}
function openTask(task: Task) {
  returnPage.value =
    page.value === "review"
      ? "/review"
      : "/tasks" +
        (route.value.filter === "all" ? "" : "?status=" + route.value.filter);
  localStorage.setItem("harbor.task", task.id);
  improvementTask.value = task.id;
  navigate("/tasks/" + encodeURIComponent(task.id));
}
function updateTask(task: Task) {
  if (removedTaskIds.has(task.id)) return;
  if (
    currentTask.value?.id === task.id &&
    task.revision >= currentTask.value.revision
  )
    currentTask.value = { ...currentTask.value, ...task };
  const index = tasks.value.findIndex((t) => t.id === task.id);
  const summary = {
    ...task,
    record_count: task.record_count ?? task.records?.length,
    issue_count: task.issue_count ?? task.issues?.length,
  };
  if (index === -1) tasks.value.unshift(summary);
  else if (task.revision >= tasks.value[index]!.revision)
    tasks.value[index] = { ...tasks.value[index], ...summary };
}
let detailSequence = 0;
async function loadTask(id: string, silent = false) {
  const sequence = ++detailSequence;
  if (!silent) detailLoading.value = true;
  detailError.value = "";
  try {
    const task = await api.task(id);
    if (
      sequence !== detailSequence ||
      route.value.id !== id ||
      page.value !== "detail"
    )
      return;
    if (!currentTask.value || task.revision >= currentTask.value.revision)
      currentTask.value = task;
    updateTask(task);
  } catch (failure) {
    if (sequence === detailSequence && route.value.id === id)
      detailError.value = errorMessage(failure);
  } finally {
    if (sequence === detailSequence) detailLoading.value = false;
  }
}
async function refresh(silent = false) {
  if (refreshing.value) return;
  refreshing.value = true;
  const results = await Promise.allSettled([api.bills(), api.health()]);
  if (results[0].status === "fulfilled") {
    // 摘要只更新列表；详情单独读取，避免用摘要覆盖费用和原文。
    tasks.value = results[0].value.filter((task) => !removedTaskIds.has(task.id));
    stale.value = false;
    error.value = "";
    updatedAt.value = new Date().toISOString();
  } else {
    stale.value = true;
    error.value = errorMessage(results[0].reason);
  }
  health.value = results[1].status === "fulfilled" ? results[1].value : null;
  loading.value = false;
  if (page.value === "detail" && route.value.id && !detailLoading.value)
    await loadTask(route.value.id, silent);
  refreshing.value = false;
}
function created(task: Task) {
  composerKey.value++;
  updateTask(task);
  openTask(task);
  void refresh(true);
}
function hashChanged() {
  route.value = readRoute();
  mobileNav.value = false;
}
watch(
  () => route.value.id,
  (id) => {
    detailSequence++;
    currentTask.value = null;
    detailError.value = "";
    detailLoading.value = false;
    if (id) {
      improvementTask.value = id;
      void loadTask(id);
      void api
        .listAssets()
        .then((value) => {
          assets.value = value;
        })
        .catch(() => {});
    }
  },
  { immediate: true },
);
watch(page, () => {
  window.scrollTo({ top: 0 });
  document.title = pageLabel.value + " · 航账 Harbor";
});
let timer: ReturnType<typeof setInterval>;
onMounted(() => {
  window.addEventListener("hashchange", hashChanged);
  window.addEventListener("keydown", keyDown);
  document.title = pageLabel.value + " · 航账 Harbor";
  void refresh(true);
  timer = setInterval(() => {
    if (!document.hidden) void refresh(true);
  }, 5000);
});
onBeforeUnmount(() => {
  clearInterval(timer);
  window.removeEventListener("hashchange", hashChanged);
  window.removeEventListener("keydown", keyDown);
  detailSequence++;
});
</script>

<template>
  <div class="harbor-app" :data-motion="oceanMotion.active.value ? 'on' : 'off'">
    <a class="skip-link" href="#workspace-main" @click.prevent="focusMain">跳到页面内容</a>
    <header class="topbar">
      <div class="topbar-row">
        <a class="brand" href="#/overview" aria-label="航账工作总览"><span class="brand-mark"><Anchor :size="17" /></span><strong>航账 <em>Harbor</em></strong></a>
        <button id="mobile-menu-button" class="icon ghost mobile-menu" :aria-expanded="mobileNav" aria-label="展开导航" @click="mobileNav = !mobileNav"><X v-if="mobileNav"/><Menu v-else/></button>
        <nav :class="['top-navigation', { 'is-open': mobileNav }]" :aria-label="isManagement ? '管理导航' : '业务导航'">
          <template v-if="!isManagement">
            <a href="#/overview" :class="{active: page === 'overview'}" :aria-current="page === 'overview' ? 'page' : undefined" @click="mobileNav = false"><LayoutDashboard/>工作总览</a>
            <a href="#/tasks" :class="{active: ['tasks','detail'].includes(page)}" :aria-current="page === 'tasks' ? 'page' : undefined" @click="mobileNav = false"><FolderOpen/>账单业务中心</a>
            <a href="#/review" :class="{active: page === 'review'}" :aria-current="page === 'review' ? 'page' : undefined" @click="mobileNav = false"><ClipboardCheck/>待办复核<span v-if="reviewCount && !stale" class="nav-count">{{ reviewCount }}</span></a>
            <a href="#/screen" :class="{active: page === 'screen'}" :aria-current="page === 'screen' ? 'page' : undefined" @click="mobileNav = false"><Monitor/>大屏总控</a>
          </template>
          <template v-else>
            <a href="#/management" :class="{active: page === 'management'}" @click="mobileNav = false"><LayoutDashboard/>控制台总览</a>
            <a href="#/management/capabilities" :class="{active: page === 'capabilities'}" @click="mobileNav = false"><Settings2/>Skill 与工具</a>
            <a href="#/management/improvements" :class="{active: page === 'improvements'}" @click="mobileNav = false"><ClipboardCheck/>进化库</a>
            <a href="#/management/traces" :class="{active: page === 'traces'}" @click="mobileNav = false"><Monitor/>Trace 追踪</a>
          </template>
        </nav>
        <div class="topbar-actions"><button class="primary new-material" @click="navigate('/new')"><UploadCloud :size="14"/><span>提交新材料</span></button><button class="console-entry" @click="navigate(isManagement ? '/overview' : '/management')"><ArrowLeft v-if="isManagement" :size="14"/><Settings2 v-else :size="14"/><span>{{ isManagement ? '返回工作空间' : '管理控制台' }}</span></button><button class="motion-toggle" role="switch" aria-label="波光动效" :aria-checked="oceanMotion.active.value" :disabled="oceanMotion.reduced.value" :title="oceanMotion.reduced.value ? '跟随系统减少动态效果设置' : '开启或关闭海面动效与图表过渡'" @click="oceanMotion.enabled.value = !oceanMotion.enabled.value"><Waves :size="14"/><span>动效</span><i :class="{enabled: oceanMotion.active.value}"/></button><button class="icon ghost refresh-button" aria-label="刷新工作空间" title="刷新工作空间" :disabled="refreshing" @click="refresh()"><RefreshCw :size="14" :class="{'loading-icon': refreshing}"/></button><span :class="['service-indicator', {offline: !loading && (!health || stale)}]" :title="loading ? '正在连接' : health && !stale ? '服务已连接' : '连接异常'"><i/></span></div>
      </div>
      <div class="ocean-ribbon"><OceanBackdrop :animated="oceanMotion.active.value"/></div>
    </header>
    <button v-if="mobileNav" class="nav-scrim" aria-label="关闭导航" @click="closeMobileNav"/>
    <div :class="['app-shell', {'admin-shell': isManagement}]">
      <main
        id="workspace-main"
        tabindex="-1"
        :class="{ 'detail-page': page === 'detail' }"
      >
        <div v-if="error" class="notice error connection-notice" role="alert">
          <CircleAlert /><span
            >{{ error
            }}{{ tasks.length ? " 当前保留上次同步的任务。" : "" }}</span
          ><button class="ghost" @click="refresh()">重试连接</button>
        </div>
        <ControlScreenPage
          v-if="page === 'overview' || page === 'screen'"
          :tasks="tasks" :loading="loading" :stale="stale" :updated-at="updatedAt"
          :motion-active="oceanMotion.active.value"
          @create="navigate('/new')" @open="openTask" @filter="showFilter"
        />
        <KeepAlive :max="2"
          ><TaskCenterPage
            v-if="page === 'tasks' || page === 'review'"
            :key="page"
            :tasks="tasks"
            :loading="loading"
            :stale="stale"
            :filter="page === 'review' ? 'review' : route.filter"
            :review-only="page === 'review'"
            @open="openTask"
            @create="navigate('/new')"
            @filter="showFilter"
            @deleted="removeTasks"
        /></KeepAlive>
        <section v-if="page === 'new'" class="new-page">
          <div class="page-heading">
            <div>
              <div class="eyebrow">A CLEAR START</div>
              <h1>从一份材料开始</h1>
              <p>上传账单或邮件，助手先整理费用，再引导您确认记账公司。</p>
            </div>
            <button class="ghost" @click="navigate('/tasks')">
              <ArrowLeft :size="15" />返回业务中心
            </button>
          </div>
          <div class="submission-layout">
            <TaskComposer
              :key="composerKey"
              embedded
              @created="created"
              @close="navigate('/tasks')"
            />
            <aside class="submission-guide">
              <span class="guide-kicker">接下来会发生什么</span>
              <ol>
                <li>
                  <b>01</b>
                  <div>
                    <strong>添加参考材料</strong>
                    <p>一次可上传多份文件，邮件中的附件也会一并处理。</p>
                  </div>
                </li>
                <li>
                  <b>02</b>
                  <div>
                    <strong>自动提取并核对</strong>
                    <p>处理在后台进行，您可以离开页面，稍后回来查看。</p>
                  </div>
                </li>
                <li>
                  <b>03</b>
                  <div>
                    <strong>确认主体，查看结果</strong>
                    <p>查看置信度，按需定位原件。发现问题时可直接修订。</p>
                  </div>
                </li>
              </ol>
              <div class="guide-formats">
                <UploadCloud /><strong>让材料保持原样</strong>
                <p>
                  支持邮件、PDF、图片、Excel 和 Word，无需先整理为固定模板。
                </p>
              </div>
            </aside>
          </div>
        </section>
        <section v-else-if="page === 'detail'" class="detail-wrapper">
          <div class="detail-nav">
            <button class="ghost" @click="navigate(returnPage)">
              <ArrowLeft :size="15" />{{
                returnPage === "/review" ? "返回待办复核" : "返回业务中心"
              }}</button
            ><span>费用结果与原文复核</span>
          </div>
          <div v-if="detailError" class="notice error" role="alert">
            <CircleAlert /><span>{{ detailError }}</span
            ><button class="ghost" @click="loadTask(route.id)">重新加载</button>
          </div>
          <div v-if="detailLoading && !currentTask" class="card empty">
            <LoaderCircle class="loading-icon" />
            <h2>正在读取账单与原件</h2>
          </div>
          <TaskWorkspace
            v-else-if="currentTask"
            :key="currentTask.id"
            :task="currentTask"
            :assets="assets"
            @updated="updateTask"
            @refresh="refresh(true)"
            @improve="navigate('/management/improvements')"
          />
          <div v-else-if="!detailError" class="card empty">
            <FolderOpen />
            <h2>未找到这份账单</h2>
            <button @click="navigate('/tasks')">查看全部任务</button>
          </div>
        </section>
        <ManagementPage
          v-else-if="isManagement"
          :section="page"
          :tasks="tasks"
          :health="health"
          :initial-task-id="improvementTask"
          @navigate="navigate"
        />
        <footer v-if="!['overview', 'screen'].includes(page)" class="page-footer">
          <span><Anchor :size="13" />HARBOR · 航账</span
          ><span>每笔费用，都有依据。</span>
        </footer>
      </main>
    </div>
  </div>
</template>

<style scoped>
.app-shell { min-height: 100vh; padding-top: var(--ocean-height); }
.topbar { position: fixed; top: 0; left: 0; right: 0; z-index: 60; background: #fff; box-shadow: 0 1px 4px #26364c0a; }
.topbar-row { height: 48px; padding: 0 25px; display: flex; align-items: center; gap: 30px; border-bottom: 1px solid #e9ecf1; }
.brand { display: flex; align-items: center; gap: 9px; color: #26374d; flex-shrink: 0; text-decoration: none; }
.brand:hover { text-decoration: none; }.brand-mark { width: 26px; height: 26px; display: grid; place-items: center; background: #2f445f; color: #fff; border-radius: 50%; }.brand strong { font-size: 14px; font-weight: 600; letter-spacing: .3px; }.brand em { font: italic 12px Georgia,serif; font-weight: 400; color: #48586d; margin-left: 4px; }
.top-navigation { display: flex; height: 100%; gap: 8px; align-items: stretch; flex: 1; }
.top-navigation a { display: flex; align-items: center; gap: 7px; color: #717985; font-size: 12px; white-space: nowrap; padding: 0 12px; position: relative; text-decoration: none; transition: color 150ms,background 150ms; }
.top-navigation a svg { width: 14px; height: 14px; }.top-navigation a:hover { color: #365d99; background: #f8f9fc; }.top-navigation a.active { color: #293e5b; font-weight: 600; }.top-navigation a.active::after { content:''; height: 2px; background: #365d99; position: absolute; bottom: 0; left: 12px; right: 12px; }
.nav-count { color: #9e7a29; font-size: 9px; border-radius: 4px; padding: 0 4px; background: #f8f1e3; }
.topbar-actions { display: flex; align-items: center; gap: 8px; margin-left: auto; flex-shrink: 0; }
.topbar-actions button { height: 29px; font-size: 11px; padding: 0 10px; gap: 6px; border-radius: 5px; white-space: nowrap; }.topbar-actions button svg { width: 14px; height: 14px; }.topbar-actions .primary { box-shadow: 0 2px 5px #365d991c; }
.motion-toggle { color: #7c8797; border-color: #e7eaf0; }.motion-toggle i { display: block; width: 22px; height: 12px; background: #d2d8e0; border-radius: 8px; position: relative; transition: background 150ms; }.motion-toggle i::after { content:''; width: 8px; height: 8px; border-radius: 50%; background: #fff; position: absolute; top: 2px; left: 2px; transition: transform 150ms; }.motion-toggle i.enabled { background: #578579; }.motion-toggle i.enabled::after { transform: translateX(10px); }
.topbar-actions .refresh-button { padding: 0 4px; width: 23px; }.service-indicator { display: flex; width: 5px; }.service-indicator i { display:block; width: 5px; height: 5px; border-radius: 50%; background: #709a8c; }.service-indicator.offline i { background: #c69062; }
.ocean-ribbon { height: 14px; position: relative; overflow: hidden; background: #21394b; }
main { padding: 18px 18px 14px; max-width: 1920px; margin: 0 auto; min-width: 0; outline: none; }
.page-footer { display: flex; justify-content: space-between; margin-top: 22px; padding: 10px 0 0; border-top: 1px solid #e5e8ed; color: #949ca7; font-size: 10px; }.page-footer > span { display:flex; gap: 6px; align-items:center; }
.mobile-menu { display: none; }.nav-scrim { position: fixed; inset: var(--ocean-height) 0 0; z-index: 48; border: 0; border-radius: 0; background: #1f304c33; }
.skip-link { position: fixed; top: -60px; left: 12px; z-index: 120; padding: 8px 12px; border-radius: 4px; background: white; color: #365d99; }.skip-link:focus { top: 8px; }
.connection-notice { margin-bottom: 16px; }.detail-nav { display: flex; align-items: center; justify-content: space-between; margin: -5px 0 12px; color: #929aa7; font-size: 10px; }.detail-nav button { padding: 5px 0; font-size: 11px; }
.page-heading { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; gap: 16px; }.page-heading h1 { font-size: 20px; margin: 4px 0; }.page-heading p { font-size: 12px; color: var(--muted); }.page-heading button { font-size: 11px; }
.submission-layout { display: grid; grid-template-columns: minmax(0,1fr) 270px; gap: 22px; align-items: start; }.submission-guide { padding: 18px 0 0 15px; color: #7f8897; }.guide-kicker { font-size: 11px; color: #8490a2; }.submission-guide ol { padding: 0; list-style: none; display: grid; gap: 24px; margin: 24px 0; }.submission-guide li { display:flex; gap: 13px; }.submission-guide b { font: italic 14px Georgia,serif; color: #a3afbf; }.submission-guide strong { font-size: 12px; color: #4d5f76; font-weight: 500; }.submission-guide p { font-size: 11px; line-height: 1.9; margin-top: 5px; }.guide-formats { border-top: 1px solid #e2e7ef; padding-top: 20px; }.guide-formats svg { vertical-align: middle; margin-right: 8px; color: #879bb7; }
/* Apply the selected compact type scale to existing business surfaces. */
main :deep(h1) { font-size: 20px; letter-spacing: -.4px; } main :deep(h2) { font-size: 15px; } main :deep(h3) { font-size: 13px; }
main :deep(.page-heading p),main :deep(.workspace-summary) { font-size: 12px; }
main :deep(.card-head) { padding: 13px 16px; } main :deep(.card-body) { padding: 16px; }
main :deep(.card),main :deep(.panel) { border-radius: 7px; box-shadow: 0 2px 7px #26364b03; }
@media (max-width: 1180px) { .topbar-row { gap: 18px; padding: 0 20px; }.top-navigation { gap: 1px; }.top-navigation a { padding: 0 8px; font-size: 11px; }.topbar-actions .console-entry svg,.topbar-actions .new-material svg { display: none; }.topbar-actions { gap: 5px; }.topbar-actions button { padding: 0 8px; }.brand em { display: none; } }
@media (max-width: 900px) { .top-navigation a svg { display: none; }.topbar-actions .motion-toggle > span { display: none; }.topbar-row { gap: 12px; }.top-navigation a { padding: 0 7px; } main { padding: 18px 18px 14px; } }
@media (max-width: 760px) { .topbar-row { height: 50px; padding: 0 14px; gap: 10px; }.brand strong { font-size: 13px; }.brand-mark { width: 23px; height: 23px; }.mobile-menu { display: inline-flex; padding: 5px; border-radius: 4px; }.mobile-menu svg { width: 16px; height: 16px; }.top-navigation { display: none; position: fixed; top: var(--ocean-height); left: 0; width: 225px; height: auto; background: white; padding: 12px; z-index: 70; border-right: 1px solid #e1e6ed; border-bottom: 1px solid #e1e6ed; box-shadow: 5px 10px 20px #24344b12; }.top-navigation.is-open { display: grid; }.top-navigation a { height: 41px; padding: 0 10px; }.top-navigation a svg { display: block; }.top-navigation a.active { background: #f1f4f9; }.top-navigation a.active::after { left: 0; top: 10px; bottom: 10px; width: 2px; height: auto; }.ocean-ribbon { height: 12px; }.topbar-actions .console-entry { display: none; }main { padding: 16px 12px 12px; }.submission-layout { grid-template-columns: minmax(0,1fr); }.submission-guide { padding: 0 8px; }.page-heading { align-items: flex-start; flex-direction: column; }.page-heading h1 { font-size: 18px; }.detail-nav > span { display: none; } }
@media (max-width: 380px) { .topbar-actions button { padding: 0 6px; }.topbar-actions .new-material { font-size: 10px; }.brand strong { font-size: 12px; }.topbar-row { gap: 6px; padding: 0 10px; }.topbar-actions .refresh-button { display: none; } }
</style>
