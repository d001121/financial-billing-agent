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
  ArrowRight,
  CircleAlert,
  ClipboardCheck,
  FolderOpen,
  LayoutDashboard,
  LoaderCircle,
  Menu,
  Monitor,
  Plus,
  RefreshCw,
  Settings2,
  UploadCloud,
  X,
} from "@lucide/vue";
import { api, errorMessage } from "./api/client";
import {
  formatDate,
  type Asset,
  type Health,
  type Task,
} from "./types/contracts";
import { taskCategory, type TaskFilter } from "./utils/taskPresentation";
import OverviewPage from "./pages/OverviewPage.vue";
import TaskCenterPage from "./pages/TaskCenterPage.vue";
import TaskComposer from "./components/TaskComposer.vue";
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
  <ControlScreenPage
    v-if="page === 'screen'"
    :tasks="tasks"
    :loading="loading"
    :stale="stale"
    :updated-at="updatedAt"
    @exit="navigate('/overview')"
    @open="openTask"
    @filter="showFilter"
    @create="navigate('/new')"
    @manage="navigate('/management')"
  />
  <div v-else :class="['app-shell', { 'admin-shell': isManagement }]">
    <a class="skip-link" href="#workspace-main" @click.prevent="focusMain"
      >跳到页面内容</a
    >
    <button
      v-if="mobileNav"
      class="nav-scrim"
      aria-label="关闭导航"
      @click="closeMobileNav"
    />
    <aside :class="['sidebar', { 'is-open': mobileNav }]">
      <a class="brand" href="#/overview" aria-label="航账工作总览"
        ><span class="brand-mark"><Anchor /></span
        ><span
          ><strong>航账 <em>Harbor</em></strong
          ><small>航运智能账单助手</small></span
        ></a
      >
      <button
        v-if="!isManagement"
        class="sidebar-create"
        @click="navigate('/new')"
      >
        <Plus :size="17" />提交新材料<ArrowRight :size="15" />
      </button>
      <p class="nav-label" :class="{ 'manage-label': isManagement }">
        {{ isManagement ? "管理员控制台" : "日常工作" }}
      </p>
      <nav v-if="!isManagement" aria-label="业务导航">
        <a
          href="#/overview"
          :class="{ active: page === 'overview' }"
          :aria-current="page === 'overview' ? 'page' : undefined"
          @click="mobileNav = false"
          ><LayoutDashboard />工作总览</a
        >
        <a
          href="#/tasks"
          :class="{ active: ['tasks', 'detail'].includes(page) }"
          :aria-current="page === 'tasks' ? 'page' : undefined"
          @click="mobileNav = false"
          ><FolderOpen />账单业务中心</a
        >
        <a
          href="#/review"
          :class="{ active: page === 'review' }"
          :aria-current="page === 'review' ? 'page' : undefined"
          @click="mobileNav = false"
          ><ClipboardCheck />待办复核<span
            v-if="reviewCount && !stale"
            class="nav-count"
            >{{ reviewCount }}</span
          ></a
        >
        <a href="#/screen" @click="mobileNav = false"
          ><Monitor />大屏总控<ArrowRight class="nav-arrow" :size="13"
        /></a>
      </nav>
      <nav v-else aria-label="管理导航">
        <a
          href="#/management"
          :class="{ active: page === 'management' }"
          :aria-current="page === 'management' ? 'page' : undefined"
          @click="mobileNav = false"
          ><Settings2 />控制台总览</a
        >
        <a
          href="#/management/capabilities"
          :class="{ active: page === 'capabilities' }"
          ><Settings2 />Skill 与工具管理</a
        >
        <a
          href="#/management/improvements"
          :class="{ active: page === 'improvements' }"
          ><ClipboardCheck />进化库</a
        >
        <a href="#/management/traces" :class="{ active: page === 'traces' }"
          ><Monitor />Trace 追踪</a
        >
        <a href="#/overview"><ArrowLeft />返回用户工作空间</a>
      </nav>
      <div class="sidebar-bottom">
        <div class="workspace-note">
          <span class="workspace-note-dot" /><strong>{{
            isManagement ? "管理与运行观测" : "您的账单工作空间"
          }}</strong>
          <p>
            {{
              isManagement
                ? "配置能力与规则，查看真实执行记录。"
                : "提交材料，查看结果。需要您判断的事项会集中提醒。"
            }}
          </p>
        </div>
        <div class="workspace-user">
          <span>财</span>
          <div>
            <strong>财务工作空间</strong><small>本地运行 · 版本可追溯</small>
          </div>
        </div>
      </div>
    </aside>
    <div class="main-shell">
      <header class="topbar">
        <div class="topbar-left">
          <button
            id="mobile-menu-button"
            class="icon ghost mobile-menu"
            :aria-expanded="mobileNav"
            aria-label="展开导航"
            @click="mobileNav = !mobileNav"
          >
            <X v-if="mobileNav" /><Menu v-else /></button
          ><span class="breadcrumb"
            >工作空间 <span>/</span> <strong>{{ pageLabel }}</strong></span
          >
        </div>
        <div class="topbar-actions">
          <button
            class="ghost console-entry"
            @click="navigate(isManagement ? '/overview' : '/management')"
          >
            <ArrowLeft v-if="isManagement" :size="15" /><Settings2
              v-else
              :size="15"
            />{{ isManagement ? "返回用户端" : "控制台" }}
          </button>
          <span
            :class="[
              'service-status',
              { offline: !loading && (!health || stale) },
            ]"
            ><i />{{
              loading
                ? "正在连接"
                : health && !stale
                  ? "服务已连接"
                  : "连接异常"
            }}</span
          ><span class="sync-label">{{
            updatedAt ? "同步于 " + formatDate(updatedAt) : "正在连接"
          }}</span
          ><button
            class="icon ghost"
            aria-label="刷新工作空间"
            title="刷新工作空间"
            :disabled="refreshing"
            @click="refresh()"
          >
            <RefreshCw :size="16" :class="{ 'loading-icon': refreshing }" />
          </button>
        </div>
      </header>
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
        <OverviewPage
          v-if="page === 'overview'"
          :tasks="tasks"
          :loading="loading"
          :stale="stale"
          :updated-at="updatedAt"
          @create="navigate('/new')"
          @open="openTask"
          @filter="showFilter"
          @screen="navigate('/screen')"
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
        <footer class="page-footer">
          <span><Anchor :size="13" />HARBOR · 航账</span
          ><span>每笔费用，都有依据。</span>
        </footer>
      </main>
    </div>
  </div>
</template>

<style scoped>
.app-shell {
  min-height: 100vh;
}
.console-entry {
  font-size: 12px;
  white-space: nowrap;
}
.admin-shell .sidebar {
  background: #172a37;
}
.sidebar {
  width: var(--sidebar-width);
  position: fixed;
  inset: 0 auto 0 0;
  z-index: 40;
  background: var(--navy);
  color: #d6e1e5;
  padding: 30px 18px 0;
  display: flex;
  flex-direction: column;
}
.brand {
  display: flex;
  align-items: center;
  gap: 11px;
  color: #fff;
  padding: 0 10px;
  text-decoration: none;
}
.brand-mark {
  display: grid;
  place-items: center;
  width: 39px;
  height: 42px;
  color: #8de1c6;
  border: 1px solid #80cdb333;
  border-radius: 12px;
  background: #70c4ac12;
}
.brand-mark svg {
  width: 24px;
  height: 24px;
}
.brand strong {
  font-size: 24px;
  font-weight: 600;
  letter-spacing: 1px;
}
.brand em {
  font-family: Georgia, serif;
  font-style: normal;
  font-size: 16px;
  letter-spacing: -0.5px;
  color: #a2b9bf;
  margin-left: 3px;
}
.brand small {
  display: block;
  font-size: 10px;
  color: #93a9b2;
  margin-top: 3px;
  letter-spacing: 1.4px;
}
.sidebar-create {
  background: #ddf5eb;
  color: #153d36;
  border-color: transparent;
  margin: 32px 6px 29px;
  padding: 12px;
  border-radius: 9px;
  justify-content: flex-start;
  font-weight: 600;
}
.sidebar-create > svg:last-child {
  margin-left: auto;
}
.sidebar-create:hover {
  background: #bfe9d8;
  border-color: transparent;
}
.nav-label {
  color: #839aa4;
  font-size: 10px;
  letter-spacing: 1.8px;
  padding: 0 17px;
  margin-bottom: 12px;
}
.manage-label {
  margin-top: 32px;
}
nav {
  display: grid;
  gap: 5px;
}
nav a {
  display: flex;
  align-items: center;
  gap: 13px;
  color: #b9cbd2;
  border-radius: 8px;
  min-height: 46px;
  padding: 11px 16px;
  font-size: 13px;
  text-decoration: none;
}
nav a svg {
  width: 18px;
  height: 18px;
  color: #8ca8b4;
}
nav a:hover {
  background: #ffffff08;
  color: #fff;
}
nav a.active {
  background: #d1f3e712;
  color: #c5f1e1;
  box-shadow: inset 3px 0 #8edec1;
}
nav a.active svg {
  color: #92dcbf;
}
.nav-count {
  background: #92dec127;
  color: #b8edd9;
  border-radius: 5px;
  min-width: 22px;
  text-align: center;
  font-size: 10px;
  padding: 1px 5px;
  margin-left: auto;
}
.nav-arrow {
  margin-left: auto;
}
.sidebar-bottom {
  margin-top: auto;
  padding-top: 35px;
}
.workspace-note {
  padding: 16px 14px 22px;
  font-size: 11px;
}
.workspace-note-dot {
  width: 6px;
  height: 6px;
  display: inline-block;
  border-radius: 50%;
  background: #87d7b9;
  margin-right: 7px;
}
.workspace-note strong {
  font-size: 11px;
  color: #c1d8d7;
  font-weight: 500;
}
.workspace-note p {
  color: #819aa6;
  font-size: 11px;
  margin-top: 9px;
  line-height: 1.9;
}
.workspace-user {
  border-top: 1px solid #ffffff0f;
  display: flex;
  gap: 10px;
  padding: 20px 10px 24px;
  align-items: center;
}
.workspace-user > span {
  width: 32px;
  height: 32px;
  border-radius: 9px;
  background: #ffffff10;
  display: grid;
  place-items: center;
  font-size: 12px;
  color: #cbe8df;
}
.workspace-user strong {
  display: block;
  font-size: 11px;
  font-weight: 500;
}
.workspace-user small {
  display: block;
  font-size: 10px;
  margin-top: 3px;
  color: #849ca6;
}
.main-shell {
  margin-left: var(--sidebar-width);
  min-width: 0;
}
.topbar {
  position: sticky;
  top: 0;
  z-index: 30;
  min-height: 70px;
  border-bottom: 1px solid var(--line);
  background: #ffffffed;
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 34px;
  gap: 12px;
}
.topbar-left,
.topbar-actions {
  display: flex;
  align-items: center;
  gap: 16px;
}
.breadcrumb {
  font-size: 11px;
  color: var(--muted);
}
.breadcrumb > span {
  margin: 0 12px;
  color: #c1cbce;
}
.breadcrumb strong {
  color: #354a52;
  font-weight: 500;
}
.service-status {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 10px;
  color: var(--green);
  white-space: nowrap;
}
.service-status i {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: currentColor;
}
.service-status.offline {
  color: var(--amber);
}
.sync-label {
  font-size: 10px;
  color: var(--muted);
}
.mobile-menu {
  display: none;
}
main {
  max-width: 1680px;
  margin: 0 auto;
  padding: 32px 34px 0;
  min-height: calc(100vh - 70px);
  outline: none;
}
.connection-notice {
  margin-bottom: 22px;
  align-items: center;
}
.connection-notice > span {
  flex: 1;
}
.page-footer {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  color: #8c9a9e;
  font-size: 10px;
  padding: 32px 0 22px;
  letter-spacing: 0.6px;
}
.page-footer > span:first-child {
  display: flex;
  gap: 7px;
  align-items: center;
}
.page-heading {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: 16px;
  margin-bottom: 26px;
}
.page-heading h1 {
  margin-top: 9px;
  font-size: 29px;
  font-weight: 600;
}
.page-heading p {
  margin-top: 9px;
  color: var(--muted);
  font-size: 12px;
}
.page-heading > button {
  font-size: 12px;
  white-space: nowrap;
}
.submission-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 265px;
  gap: 30px;
  align-items: start;
}
.submission-guide {
  padding: 24px 0;
}
.guide-kicker {
  font-size: 11px;
  color: var(--muted);
  letter-spacing: 1px;
}
.submission-guide ol {
  padding: 0;
  margin: 26px 0 32px;
  list-style: none;
  display: grid;
  gap: 30px;
}
.submission-guide li {
  display: flex;
  gap: 14px;
}
.submission-guide li > b {
  font-family: Georgia, serif;
  font-size: 21px;
  font-weight: 400;
  color: #6b9a8d;
  line-height: 1.2;
}
.submission-guide strong {
  font-size: 12px;
  font-weight: 600;
}
.submission-guide p {
  font-size: 11px;
  color: var(--muted);
  line-height: 1.9;
  margin-top: 6px;
}
.guide-formats {
  padding: 22px;
  border: 1px dashed #cbdad4;
  border-radius: 10px;
}
.guide-formats > svg {
  color: var(--primary);
  display: block;
  margin-bottom: 12px;
}
.detail-nav {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: -7px 0 18px;
}
.detail-nav button {
  font-size: 12px;
  padding-left: 0;
}
.detail-nav > span {
  font-size: 11px;
  color: var(--muted);
}
.detail-wrapper > .notice {
  margin-bottom: 18px;
}
.skip-link {
  position: fixed;
  top: -80px;
  left: 260px;
  z-index: 100;
  padding: 10px 16px;
  background: white;
  color: var(--primary);
  border-radius: 8px;
}
.skip-link:focus {
  top: 10px;
}
.nav-scrim {
  display: none;
}
@media (min-width: 1700px) {
  main {
    padding-top: 42px;
  }
}
@media (max-width: 1150px) {
  .sidebar {
    padding-inline: 12px;
  }
  .topbar {
    padding-inline: 24px;
  }
  main {
    padding-inline: 24px;
  }
  .submission-layout {
    grid-template-columns: minmax(0, 1fr) 215px;
    gap: 20px;
  }
  .sync-label {
    display: none;
  }
}
@media (max-width: 800px) {
  .sidebar {
    transform: translateX(-100%);
    width: 242px;
    transition: transform 0.2s ease;
  }
  .sidebar.is-open {
    transform: translateX(0);
  }
  .main-shell {
    margin-left: 0;
  }
  .mobile-menu {
    display: inline-flex;
  }
  .nav-scrim {
    display: block;
    position: fixed;
    inset: 0;
    z-index: 35;
    border: 0;
    border-radius: 0;
    background: #0c202a77;
  }
  .topbar {
    min-height: 62px;
    padding: 0 18px;
  }
  .topbar-left,
  .topbar-actions {
    gap: 9px;
  }
  main {
    padding: 24px 18px 0;
  }
  .submission-layout {
    grid-template-columns: minmax(0, 1fr);
  }
  .submission-guide {
    padding: 8px 4px;
  }
  .submission-guide ol {
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 16px;
  }
  .submission-guide li {
    display: block;
  }
  .submission-guide li > b {
    display: block;
    margin-bottom: 12px;
  }
  .guide-formats {
    display: none;
  }
  .skip-link {
    left: 16px;
  }
}
@media (max-width: 500px) {
  .topbar-left {
    min-width: 0;
  }
  .breadcrumb {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .topbar-actions {
    flex-shrink: 0;
  }
  .topbar-actions .service-status {
    display: none;
  }
  .topbar {
    padding: 0 12px;
  }
  .breadcrumb {
    font-size: 10px;
  }
  .breadcrumb > span {
    margin: 0 6px;
  }
  .service-status {
    font-size: 9px;
  }
  main {
    padding: 20px 14px 0;
  }
  .page-heading {
    align-items: flex-start;
    flex-direction: column;
  }
  .page-heading h1 {
    font-size: 26px;
  }
  .page-footer {
    font-size: 9px;
  }
  .detail-nav > span {
    display: none;
  }
  .submission-guide ol {
    grid-template-columns: 1fr;
    gap: 18px;
  }
  .submission-guide li {
    display: flex;
  }
}
@media (max-width: 800px) {
  .sidebar {
    visibility: hidden;
  }
  .sidebar.is-open {
    visibility: visible;
  }
}
</style>
