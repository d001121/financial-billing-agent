# Harbor 后端

`backend/` 是后端工程，也是 Python 包本身。它组合 LangChain 主控、Deep Agents 专家、官方 Agent Server 和业务 API；领域规则保留在七个业务 Skill。开发约定统一维护在根 [AGENT.md](../AGENT.md)。

## 运行

确认本目录 `.env` 的外部服务配置及本机 Redis 可用，然后在此目录执行：

```powershell
.\start.cmd
```

也可双击仓库根 `start.cmd`，它会转调此入口并将工作目录固定为 `backend/`。默认访问 `http://127.0.0.1:2024/app/`；生产页面读取同级 `../frontend/dist/`，运行已有构建不需要 Node。

## 目录与调用边界

| 目录 | 职责 |
| --- | --- |
| `agents/` | 工厂及 supervisor/document/billing 三种角色装配、各自提示词 |
| `middleware/` | 官方 middleware 组合；Skill 资源、MCP 披露、派发与任务结果边界 |
| `tools/` | 上下文/人工输入工具、产物保存与包内业务函数的官方工具绑定 |
| `hooks/` | 独立校验注册、原生 guard 及统一验证入口；领域算法调用 Skill |
| `mcp/` | 内置 `langchain.mcp` 的连接生命周期与工具命名适配 |
| `extensions/` | 能力快照、不可变 Skill 发布与固定版本函数/资源访问 |
| `harness/` | 派发校验、共享预算和活跃区间计量 |
| `api/` | FastAPI 装配；health/assets/tasks/reviews/exports/extensions/improvements 路由 |
| `infrastructure/` | 模型适配、事务仓储、资产定位和官方 SQLite 检查点生命周期 |
| `config/` | 设置、配置 schema/校验/事务、角色提示词解析及五类 YAML |
| `skills/` | 七个业务包，各含 SKILL.md、references、scripts 和独立测试 |
| `tests/`、`evals/`、`examples/` | 宿主与跨包验证、固定评测及已验收输出 |
| `data/` | samples 原题样本、assets 原件/派生件、releases 固定 Skill、SQLite |
| `scripts/` | 环境、迁移及测量等工程工具 |
| `bishi1/`、`python.cmd` | 项目私有解释器及统一命令入口 |
| `.env`、`requirements*.txt`、`langgraph.json` | 外部服务配置、依赖及官方服务注册 |

服务入口为 `backend.agents:make_graph` 与 `backend.api:app`；检查点入口为 `./infrastructure/checkpoints.py:checkpointer`。内部调用直接导入职责模块，例如 `backend.infrastructure.repository`、`backend.extensions.snapshots`、`backend.config.transactions` 和 `backend.tools.artifacts`。`__init__.py` 仅显式导出公共入口，不保留旧平铺模块的兼容别名。

## 测试

在 `backend/` 执行：

```powershell
.\python.cmd -m pip check
.\python.cmd -m pytest -q tests skills
```

从仓库根调用时，解释器、脚本、测试路径均加 `backend/`。本地 dev 元数据位于 `.langgraph_api/`，临时缓存与迁移工作目录在 `.build/`。

本轮按职责重构已完成全量163项回归（43 warnings、4 subtests、68.90秒），后续配置修复定向40项通过（28.73秒），项目外运行时与pip check通过。官方服务四HTTP全200，三个历史任务的检查点、消息、原中断和revision保留，未新建或恢复Agent运行。报告为 `tests/reports/responsibility-tests.txt`、`responsibility-configuration-tests.txt`、`responsibility-runtime.json` 和 `responsibility-after.json`。用户已明确先完成需求，交付包制作、更新和迁移暂缓。

扩展约定见 [Skill 与 Hook](../docs/skills-and-hooks.md)，运行时来源见 [便携环境](../docs/portable-environment.md)，验收范围见 [验收记录](../docs/acceptance.md)。职责迁移不改写历史任务规则版本、原始响应或已发布 Skill，也不自动续跑人工中断。
