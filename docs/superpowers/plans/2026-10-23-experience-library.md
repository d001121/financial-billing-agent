# Experience Library Implementation Plan

> **For agentic workers:** Use executing-plans inline; no subagents. User approved implementation. This directory has no Git repository, so do not initialize or commit.

**Goal:** 从真实纠错生成可审核经验，减少填写，并在后续账单处理中检索参考。

**Architecture:** 扩展现有feedback-improvement Skill。FastAPI只绑定存储和原生模型接口，LangChain BM25负责检索；任务快照固定经验，原生工具返回有来源的参考。Vue以经验卡片为主，旧映射发布功能保留在执行规则标签内。

**Tech Stack:** Python portable runtime, LangChain structured output/BM25Retriever, GaussDB opaque repository, Vue3/TypeScript/Vite.

## Task 1: 领域契约

- [x] 在backend/tests/test_experience_library.py先添加失败用例：同主体已审核经验可以检索，草稿/其他主体/无关键词匹配不能返回。
- [x] backend/skills/feedback-improvement/scripts/skill.py添加ExperienceDraft、summary_context、validate_experience、retrieve_experiences。
- [x] 安装并锁定rank-bm25==0.2.2，复用已安装官方BM25Retriever，不实现排名算法。

```python
assert retrieve_experiences([draft], accounting_entity='A', query='币种') == []
```

## Task 2: 总结与审核HTTP

- [x] 添加backend/api/routes/experiences.py；复用已有测试MemoryRepository，不连真实数据库。
- [x] POST summarize绑定task/revision并一次调用with_structured_output；独立生成回执最多1次调用，同输入成功缓存。
- [x] GET列表、PATCH草稿、POST启用/停用、GET来源引用记录。激活只接受approved=true且主体明确，草稿编辑使旧审核失效。
- [x] 模型工厂增加可选请求计量回调，总结调用关闭思考并限制输出；失败后显式重试，无自动付费重试。

```python
assert client.post('/api/improvements/experiences/summarize', json={'task_id':'t1','expected_revision':2}).status_code == 409
```

## Task 3: Agent参考工具

- [x] snapshots.py纳入经验快照；skill_bindings.py注册search_reviewed_experiences并记录真实检索回执。
- [x] 当前记录已停用时过滤，旧任务不读取发布后新增经验。主控与专家按配置获得工具，提示说明经验不能充当当前原件证据。
- [x] 用离线工具调用检查主体过滤、停用和引用记录；不执行真实模型。

## Task 4: 使用界面

- [x] 新增ExperienceLibrary.vue：账单选择、可选一句话、AI总结、卡片编辑/确认/停用、来源和真实引用记录。
- [x] ManagementPage与账单详情接入，旧ImprovementPanel保留为执行规则页签，导航改进化库。
- [x] api/client.ts和types/contracts.ts定义具体契约。异步操作禁止重复点击并显示失败，空态提供真实使用步骤。

## Task 5: 定向验证和说明

- [x] 执行新经验测试、既有费用映射回归和版本一致性检查；不运行全量。
- [x] 前端npm run build；必要时用静态本地预览和模拟API核对实际交互，保持正式后端关闭。
- [x] 更新AGENT.md、README与研究记录，说明已验证范围和未执行真实模型调用。

## 完成证据

2026-10-23：27项定向离线检查通过（11.65秒），frontend构建及类型检查通过；独立内存模拟API浏览器核对草稿、确认入库、停用和原有执行规则入口。未运行全量或真实模型/OCR，正式数据库新接口和线上收益未验；详见docs/research/experience-library-20261023.md。
