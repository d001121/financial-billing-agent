<script setup lang="ts">
import { defineAsyncComponent } from "vue";
import {
  ArrowLeft,
  ArrowUpRight,
  BookOpen,
  Cable,
  Check,
  Settings2,
  ShieldCheck,
  Activity,
} from "@lucide/vue";
import type { Health, Task } from "../types/contracts";
const CapabilityPanel = defineAsyncComponent(
  () => import("../components/CapabilityPanel.vue"),
);
const ImprovementPanel = defineAsyncComponent(
  () => import("../components/ExperienceLibrary.vue"),
);
const TracePage = defineAsyncComponent(() => import("./TracePage.vue"));
defineProps<{
  section: string;
  tasks: Task[];
  health: Health | null;
  initialTaskId: string;
}>();
const emit = defineEmits<{ navigate: [path: string] }>();
</script>
<template>
  <section class="management-page">
    <div class="management-heading">
      <div>
        <span class="eyebrow">WORKSPACE SETTINGS</span>
        <h1>
          {{
            section === "capabilities"
              ? "能力与连接"
              : section === "improvements"
                ? "进化库"
                : section === "traces"
                  ? "Trace 追踪"
                  : "管理员控制台"
          }}
        </h1>
        <p>
          {{
            section === "capabilities"
              ? "管理智能体、业务技能、外部工具与校验设置。"
              : section === "improvements"
                ? "让 AI 整理纠错经验，确认入库后供后续账单参考。"
                : section === "traces"
                  ? "查看真实耗时、Agent 调用路径、工具拦截与人工介入。"
                  : "在这里维护工作空间，让账单处理适应您的业务。"
          }}
        </p>
      </div>
      <button
        v-if="section !== 'management'"
        class="ghost"
        @click="emit('navigate', '/management')"
      >
        <ArrowLeft :size="14" />返回管理中心
      </button>
    </div>
    <nav
      v-if="section !== 'management'"
      class="management-tabs"
      aria-label="管理功能"
    >
      <a
        href="#/management/capabilities"
        :class="{ active: section === 'capabilities' }"
        :aria-current="section === 'capabilities' ? 'page' : undefined"
        ><Cable :size="16" />能力与连接</a
      ><a
        href="#/management/improvements"
        :class="{ active: section === 'improvements' }"
        :aria-current="section === 'improvements' ? 'page' : undefined"
        ><BookOpen :size="16" />进化库</a
      >
      <a
        href="#/management/traces"
        :class="{ active: section === 'traces' }"
        :aria-current="section === 'traces' ? 'page' : undefined"
        ><Activity :size="16" />Trace 追踪</a
      >
    </nav>
    <CapabilityPanel v-if="section === 'capabilities'" />
    <TracePage v-else-if="section === 'traces'" />
    <ImprovementPanel
      v-else-if="section === 'improvements'"
      :tasks="tasks"
      :initial-task-id="initialTaskId"
    />
    <template v-else>
      <div class="management-options">
        <a class="management-card" href="#/management/capabilities"
          ><span class="setting-icon"><Settings2 /></span
          ><span class="option-kicker">CAPABILITIES</span>
          <h2>能力与连接</h2>
          <p>按业务配置处理能力、接入外部工具，管理独立的校验项与运行参数。</p>
          <div class="option-tags">
            <span>智能体</span><span>业务技能</span><span>MCP</span
            ><span>校验</span>
          </div>
          <span class="option-open"
            >进入配置<ArrowUpRight :size="16" /></span></a
        ><a class="management-card" href="#/management/improvements"
          ><span class="setting-icon experience"><BookOpen /></span
          ><span class="option-kicker">KNOWLEDGE</span>
          <h2>进化库</h2>
          <p>
            从账单纠错一键生成经验，确认后供 AI 参考；查看来源与任务检索记录。
          </p>
          <div class="option-tags">
            <span>AI 总结</span><span>经验卡片</span><span>按需参考</span>
          </div>
          <span class="option-open">查看改进<ArrowUpRight :size="16" /></span
        ></a>
        <a class="management-card" href="#/management/traces"
          ><span class="setting-icon"><Activity /></span
          ><span class="option-kicker">OBSERVABILITY</span>
          <h2>Trace 追踪</h2>
          <p>
            查看任务耗时、Agent
            路径、工具调用和拦截，区分人工修订与常规确认，核对质量评测口径。
          </p>
          <div class="option-tags">
            <span>调用路径</span><span>耗时</span><span>人工介入</span
            ><span>识别质量</span>
          </div>
          <span class="option-open"
            >查看运行记录<ArrowUpRight :size="16" /></span
        ></a>
      </div>
      <div class="management-notes">
        <ShieldCheck />
        <div>
          <h3>配置发布与日常核账分开</h3>
          <p>
            日常材料提交、费用修订和结果确认在业务中心完成。共享能力与规则经过明确保存或发布后，才供后续任务使用。
          </p>
        </div>
      </div>
      <section class="service-card card">
        <div class="service-heading">
          <Cable />
          <h2>工作空间连接</h2>
          <span :class="['connection', { offline: !health }]"
            ><Check v-if="health" :size="13" />{{
              health ? "业务 API 已连接" : "业务 API 未连接"
            }}</span
          >
        </div>
        <p>
          此处显示业务 API 的连接情况。外部工具和 MCP
          的具体状态，请在“能力与连接”中查看。
        </p>
      </section>
    </template>
  </section>
</template>
<style scoped>
.management-heading {
  display: flex;
  justify-content: space-between;
  gap: 20px;
  align-items: flex-end;
  margin-bottom: 16px;
}
.management-heading h1 {
  font-size: 20px;
  font-weight: 600;
  margin-top: 9px;
}
.management-heading p {
  font-size: 13px;
  color: var(--muted);
  margin-top: 10px;
}
.management-heading button {
  font-size: 13px;
  white-space: nowrap;
}
.management-options {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}
.management-card {
  display: block;
  background: white;
  border: 1px solid var(--line);
  border-radius: 7px;
  padding: 20px;
  color: var(--ink);
  text-decoration: none;
  position: relative;
  transition:
    box-shadow 0.2s,
    border-color 0.2s;
}
.management-card:hover {
  border-color: #b2c2da;
  box-shadow: 0 10px 35px #17352b07;
}
.setting-icon {
  width: 32px;
  height: 32px;
  display: grid;
  place-items: center;
  color: var(--primary);
  background: var(--primary-soft);
  border-radius: 7px;
  margin-bottom: 16px;
}
.setting-icon.experience {
  background: #edf1f7;
  color: #527091;
}
.option-kicker {
  font-size: 11px;
  color: var(--muted);
  letter-spacing: 1.5px;
}
.management-card h2 {
  font-size: 16px;
  margin: 8px 0 12px;
  letter-spacing: -0.5px;
}
.management-card p {
  font-size: 13px;
  line-height: 1.9;
  color: var(--muted);
  max-width: 365px;
}
.option-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
  margin: 18px 0 20px;
}
.option-tags span {
  font-size: 11px;
  background: #f4f6f5;
  padding: 4px 9px;
  border-radius: 5px;
  color: #6b7c94;
}
.option-open {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 13px;
  color: var(--primary);
  border-top: 1px solid var(--line);
  padding-top: 20px;
}
.management-notes {
  display: flex;
  align-items: flex-start;
  gap: 13px;
  background: #f0f3f8;
  padding: 22px 26px;
  border-radius: 7px;
  margin-top: 24px;
}
.management-notes > svg {
  margin-top: 2px;
  color: #5b8578;
}
.management-notes h3 {
  font-size: 13px;
  font-weight: 600;
}
.management-notes p {
  font-size: 12px;
  color: var(--muted);
  line-height: 1.9;
  margin-top: 7px;
  max-width: 740px;
}
.service-card {
  margin-top: 24px;
  padding: 24px 26px;
}
.service-heading {
  display: flex;
  gap: 10px;
  align-items: center;
}
.service-heading > svg {
  color: var(--primary);
}
.service-heading h2 {
  font-size: 14px;
}
.connection {
  display: flex;
  gap: 5px;
  align-items: center;
  margin-left: auto;
  font-size: 12px;
  color: var(--green);
}
.connection.offline {
  color: var(--amber);
}
.service-card p {
  font-size: 12px;
  color: var(--muted);
  margin-top: 13px;
}
.management-tabs {
  display: flex;
  gap: 24px;
  border-bottom: 1px solid var(--line);
  margin-bottom: 25px;
}
.management-tabs a {
  display: flex;
  gap: 8px;
  align-items: center;
  padding: 12px 3px;
  font-size: 13px;
  color: var(--muted);
  border-bottom: 2px solid transparent;
  text-decoration: none;
}
.management-tabs a.active {
  border-color: var(--primary);
  color: var(--primary);
}
@media (max-width: 650px) {
  .management-heading {
    align-items: flex-start;
    flex-direction: column;
    gap: 14px;
  }
  .management-heading h1 {
    font-size: 18px;
  }
  .management-options {
    grid-template-columns: 1fr;
  }
  .management-card {
    padding: 24px;
  }
  .management-notes,
  .service-card {
    padding: 20px;
  }
  .service-heading {
    flex-wrap: wrap;
  }
  .connection {
    margin-left: 0;
  }
}
</style>
