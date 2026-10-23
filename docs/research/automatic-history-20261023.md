# 自动历史账单检索（2026-10-23）

已核对原题 `C:/Users/dzx/Downloads/AI agent 笔试题 (2026_10_20 22：39：50).html`：验收第5项要求区分新增与更新，第7项要求识别重复和冲突。匹配顺序为单据号+费用名、提单号+费用名+币种、订舱号+费用名+币种、箱号+交易双方+日期+金额。新旧差异本身不构成更新授权；UPDATE 仅修改明确字段，其余继承。

## 实现

常规提交发送 `history_mode=automatic`，API 未指定旧账单范围时也默认自动模式。后台通过现有 repository 一次读取任务/费用投影，`limit=None` 明确省略 SQL LIMIT；不读取历史原件或 OCR 正文，不限制为最新100项。已提供 existing_records/existing_bills 的接口调用保留 provided 模式，旧任务没有 history_mode 时保持原规则。

同一标准化记账主体下，仅已完成/已批准、当前 revision 校验通过的 CREATE/UPDATE 费用参与匹配。排除当前任务、删除、拒绝、未完成和未解决记录；没有主体则等待补充并在后续核对时重新检索。候选由 billing-reconciliation 1.4.0 使用既有匹配算法筛选，skills 配置 v37。宿主仅负责读取、持久化、调用固定 Skill，不另建检索 Agent 或模型循环。

候选 ID 按任务/revision/费用隔离，并记录来源。UPDATE 通过精确父版本关系替代旧候选；独立重复、分支更新和多行复用同一旧费用保留歧义。NO_CHANGE 不再生成新的历史基线。明确更新可以继承旧账单未修改字段；没有匹配时缺失值仍为空，不用其他历史值补齐。费用映射与本次核对一同保存，保证批准和导出时使用相同映射。

检索回执 `history_lookup` 绑定主体、revision、候选摘要与来源，与保存人工修订记录的 `history` 列表分开，避免覆盖已有审计。统一 Hook 在批准和正式导出前重新查询：候选变化产生 HISTORY_STALE，要求重新核对；查询失败产生 HISTORY_UNAVAILABLE，不把故障当作没有历史。工具结果和任务上下文包含回执。历史任务金额不被改写，输出仍是 CREATE/UPDATE/NO_CHANGE/PENDING_REVIEW 提案。

## 官方能力依据

| 操作 | 官方入口/符号 | 安装版本 | 原生组合与业务缺口 |
| --- | --- | --- | --- |
| 工具内读取应用数据库 | Docs MCP `/oss/python/langchain/tools.mdx`，ToolRuntime/Store | langchain 1.4.6；core 1.6.12 | 复用现有 repository 和原生核对工具；通用数据库访问不定义本题的历史来源资格、匹配顺序和更新规则 |
| 工具绑定与调用 | Reference MCP `langchain_core.tools.convert.tool` | deepagents 0.7.30；langgraph 1.2.16 | 保持原生工具与固定 Skill；领域选择/lineage/摘要门禁放在现有 billing-reconciliation 包内，无新调度器 |

## 定向验证与边界

- 财务核对、历史策略、Skill版本测试：43 passed。
- 宿主定向历史/API/审批/导出检查：15 passed，含固定费用映射、补充主体、历史变化与查询故障。
- SQL投影构造：1 passed，验证无截断和普通列表默认限制保留；使用假连接，未调用正式数据库。
- Vue 类型检查及生产构建通过；保留既有 Vite 大包提示。

合计59项相关离线检查通过。未跑全量测试，未调用真实模型、OCR或正式历史查询，未启动/重启正式后端，也未迁移已有任务能力。没有新增模型/OCR费用。该能力只检索本项目持久任务，不连接外部财务系统；候选变化检查不等同于跨任务原子记账，真实 GaussDB SQL 集成与并发提交仍未实测。
