# Vue 原生 SDK、Agent Server 与便携交付复用核验

> **版本/协议研究快照，2026-10-21复核。** 固定源码与包元数据保留，发行号不代表本地已安装、组合已通过或仍为最新。后续按[当前实现方案](../implementation.md)及[最终开发计划](../superpowers/plans/2026-10-21-final-development-plan.md)锁定CLI/API/runtime、Vue SDK/协议与LangGraph并实测；不自写替代协议服务器。

核验日期：2026-10-21，Asia/Shanghai。范围为前端与服务端架构研究；本次未安装依赖、未读取 `.env`、未调用业务服务。证据来自已连接的 LangChain Docs/API Reference MCP、GitHub MCP 的固定提交源码及 npm/PyPI 官方包元数据。

## 1. 明确推荐

**本地笔试交付首选：`@langchain/vue` v1 + 官方 Python Agent Server 的 `langgraph dev` + 同进程 FastAPI 业务扩展。** 主控仍为 Python `langchain.agents.create_agent`；Agent Server 承担原生线程、运行、后台执行、状态、协议、流订阅和人工中断恢复。FastAPI 只添加材料、证据、业务 revision、审批和扩展配置等领域接口，不再自写一套 Agent Server、运行队列或 Vue 流状态机。[S1][S2][S6][S7]

这是**本地开发/验收配置**，有官方本地文件状态保存能力，但不能据此承诺生产级无损恢复。Windows 便携运行、暂停后重启和断线重连仍须在本项目 `bishi1/` 实测；本次研究未把文档与源码核验写成运行通过。[S6][S15]

若后续要求进程硬崩溃也不丢任何已受理状态，转到官方持久化 Agent Server 配置，或先验证官方 custom checkpointer 扩展，而不是立即自研整个 v2 服务。生产/独立部署需要 PostgreSQL 核心数据库、Redis、容器基础设施及相应 key/license 条件；**现有 GaussDB 不能未经验证就作为 PostgreSQL 替代品**。[S8][S9][S10]

## 2. 当前版本证据与边界

| 组件 | 2026-10-21 核验结果 | 本项目状态/使用限制 |
| --- | --- | --- |
| `@langchain/vue` | npm `latest=1.2.5`；依赖 `@langchain/langgraph-sdk=1.12.5`，peer 为 `vue ^3.0.0`、`@langchain/core ^1.1.48` | 尚未安装。候选锁定组合，须经前端构建与服务端协议联调后提交锁文件 |
| Vue v1 文档 | 使用新事件协议，提供原生 `useStream`、Vue refs 和 selector composables | 不使用 React hook 代替 Vue API |
| `@langchain/vue@0.4.7` | npm 存在；依赖 SDK `1.8.10`、peer core `^1.1.27` | 仅作为旧协议后端的兼容备选，不是首选 |
| `langgraph-cli` | PyPI `0.4.37`；`inmem` extra 安装官方 API 和 inmem runtime；有 `langgraph_cli/__main__.py` | 未安装；后续通过项目解释器调用模块入口 |
| `langgraph-api` | PyPI `0.16.2`，Python `>=3.11`，wheel 为 `py3-none-any` | 未安装；包含原生 protocol v2 路由，不能仅凭元数据声称 Windows 运行已通过 |
| `langgraph-runtime-inmem` | PyPI `0.36.2`，wheel 为 `py3-none-any` | 未安装；开发用本地 pickle 保存，见 §5 |
| 已安装 Python LangGraph | 本地 `langgraph 1.2.16` 的 `pregel/main.py` 确实有 `stream_events/astream_events(version="v3")` | v3 API 标记 experimental；默认参数仍为 v2，调用时必须显式选 v3 |

npm 元数据与固定源码相符：API Reference 指向的 GitHub 提交 `cc29753d529caa5eed97a65e765ba26c0f88c631` 中，Vue 为 `1.2.5`、SDK 为 `1.12.5`。该 JS 版本号与已安装的 Python `langgraph-sdk 0.4.8` 属不同发布线，不能互相代替。[S3][S11][S12][S13]

迁移指南建议 Vue `^3.4`，而包 peer 范围较宽。新工程按现有工具链核对后选择具体 Vue 3 版本；不把 peer 的宽范围当全部构建场景的验证结果。[S3]

## 3. Vue 能直接复用什么

API Reference 明确 `@langchain/vue/useStream` 是 Vue Composition API 绑定；`messages`、`values`、`toolCalls`、`interrupts` 等为只读响应式投影，`submit/stop/respond/disconnect` 为命令方法。嵌套工作可通过 `subagents/subgraphs` 发现，再使用 `useMessages/useToolCalls/useValues` 等选择器订阅具体作用域。[S1][S2]

```vue
<script setup lang="ts">
import { ref } from "vue";
import { useStream } from "@langchain/vue";

const threadId = ref<string | null>(null);
const stream = useStream<AgentState>({
  apiUrl: "/agent",
  assistantId: "billing_agent",
  threadId,
  onThreadId: (id) => { threadId.value = id; },
});
// AgentState 为本项目定义的前后端状态契约，不是框架内置类型。
// <script setup> 中读取 stream.values.value、stream.interrupts.value。
</script>
```

上例是拟定集成形态，尚未运行。`assistantId` 对应 `langgraph.json` 的 graph 名；Python 后端状态用显式 TypeScript interface 建模，不能照抄 `typeof myAgent` 来推断跨语言 Python 类型。[S1]

可复用的界面基础包括：运行加载状态、消息与工具生命周期、结构化状态、人工中断、线程重连及嵌套执行投影。仍需编写 Vue 业务组件：原件预览、字段证据定位、旧新值对比、原生 todos 与任务进展、审批影响、过期编辑冲突、部分完成范围及扩展配置。SDK 不提供本项目财务工作台成品。[S1][S2]

`stream.stop()` 默认向服务端取消运行；`disconnect()` 仅断开客户端连接。业务“暂停”先持久化控制状态，由原生工具 middleware 的薄 wrapper 阻止新调用，再在可控边界停止；不能直接把停止网络订阅解释为业务已暂停，也不能把运行取消解释为已撤回远端动作。[S3；业务约定 AGENT.md §7.4–7.5]

## 4. 自定义 FastAPI 能否直接接 Vue v1

**可以使用自定义后端，但必须满足新 Agent 协议；普通 `astream_events(..., version="v2")` 的 `on_chain_*` SSE，或把 `stream_events(version="v3")` 原始事件直接逐条输出，都不足以替代完整服务端。** Python 内部 v3 事件流与外部 protocol v2 服务是不同层次；数字不同不能据此判定不兼容，也不能视为相同接口。[S3][S4][S5][S14]

### 4.1 v1 的准确入口

```ts
import { HttpAgentServerAdapter, useStream } from "@langchain/vue";

const stream = useStream<AgentState>({
  assistantId: "billing_agent",
  transport: new HttpAgentServerAdapter({
    apiUrl: "/api/agent",
    threadId: "<thread-id>",
  }),
});
```

这段代码只说明官方扩展点，不是本项目建议自研的后端。连接官方 Agent Server 的默认最少代码是直接使用 `useStream({ apiUrl, assistantId, threadId })` 的内置 server 模式，`assistantId` 明确填写 `langgraph.json` 中注册的 graph 名。只有需要自定义后端或传输适配时才显式传入 adapter；custom adapter 分支不会自动创建用于线程、运行和历史等管理 API 的 LangGraph `Client`，需要这些 API 时另行创建。`assistantId` 属于 `useStream` 选项，不放进 adapter 构造参数。[S1][S3][S4]

v1 自定义分支接收 `AgentServerAdapter`；传入 adapter 后，不同时传 `client/apiUrl/apiKey/fetch/webSocketFactory` 到 `useStream` 顶层，相关参数放进 adapter。`paths` 可以改 URL，`fetch` 可以加认证，但不会将任意响应转换成协议。[S3][S4]

### 4.2 `HttpAgentServerAdapter` 对 HTTP 服务端的契约

| 默认接口/行为 | 必须满足的内容 |
| --- | --- |
| `POST /threads/{thread_id}/commands` | 请求含整数 `id`、`method`、方法专属 `params`；例如 `run.start`、`input.respond`。返回协议 success/error，而不是任意 `{ok:true}` |
| 命令与运行分离 | 创建运行的命令受理后在后台执行；订阅断开不等于后台工作结束 |
| `POST /threads/{thread_id}/stream/events` | 请求 `channels`，可选 `namespaces/depth/since`；响应 `text/event-stream`，SSE 的 `data` 为协议 `Message/ProtocolEvent` 对象 |
| `GET /threads/{thread_id}/state` | 用于 hydration，返回 `values`，可包含 `next/tasks/metadata/checkpoint/parent_checkpoint`；不存在时可返回 404 |
| 事件过滤与回放 | 支持 channels 与 namespace 前缀过滤；保存首次订阅打开前已产生的事件；扩宽订阅过滤后新连接仍能回放匹配历史；客户端按稳定 `event_id` 去重 |
| 重新连接 | 官方 API 文档允许 `since` 回放。固定 SDK 源码在首次连通前携带初始 `since`，连接成功后的重连会省略 `since`，依赖完整回放与 `event_id` 去重；不能自作主张把连接内 `seq` 当永久业务游标 |

`AgentServerAdapter` 的底层方法为 `open()`、`send(Command)`、`events(): AsyncIterable<Message>`、`close()`，以及可选 `openEventStream(SubscribeParams)`、`setThreadId()`、`getState()`、`getHistory()`。`openEventStream` 返回 `{ events, ready, close }`。省略某些方法会影响 hydration、历史和连接行为，不能据此声称完整能力仍存在。[S4][S5]

**最小代码结论：使用已经实现这些路由的官方 Python Agent Server。** 在 FastAPI 里手写 commands、过滤订阅、队列、回放、取消、输入恢复和快照，等于重建一个服务端，不符合本次最大复用目标。[S5][S6]

### 4.3 旧 `FetchStreamTransport` 不可混用

Vue v1 迁移指南明确旧 transport 应替换为 `HttpAgentServerAdapter/AgentServerAdapter`，且 v1 不能连接只讲旧协议的服务。API Reference 同时可以搜到旧 SDK `react/FetchStreamTransport` 页面，那不证明新 Vue v1 仍支持它。[S3]

只有官方本地服务在 Windows 上出现无法解决的兼容问题、又决定保留旧 HTTP 流后端时，才评估锁定 `@langchain/vue@0.4.7 + SDK 1.8.10`，并按旧包真实源码核对其 payload、事件格式、checkpoint、resume 和断线行为。本次未完成旧版本端到端契约证明，因此不把“0.4.x + FetchStreamTransport”写成已经验证的可运行备用方案，也不为省代码推荐无约束降级。[S11]

## 5. 官方本地服务与 Windows 便携边界

官方文档规定 `langgraph dev` 无需 Docker，直接在 Python 环境运行，使用 inmem runtime，并将状态 pickle 到本地目录；用于开发与测试。`langgraph up` 才使用 PostgreSQL/Redis 容器作接近生产的验证。[S6]

候选依赖是 `langgraph-cli[inmem]==0.4.37`、`langgraph-api==0.16.2`、`langgraph-runtime-inmem==0.36.2`。它们尚未安装，本次没有改变已有依赖。API 元数据要求 Python `>=3.11`；`uvloop` 与 `httptools` 依赖显式排除 Windows，API/runtime 自身提供通用 wheel。因此 Python 3.13/Windows 在包声明层面没有被直接排除，但二进制传递依赖、FastAPI/Starlette 兼容和实际移机运行仍须验证。[S12][S13]

后续候选启动入口：

```powershell
.\python.cmd -m langgraph_cli dev --no-browser --no-reload --host 127.0.0.1 --port 2024
```

CLI wheel 确实含 `langgraph_cli/__main__.py`。使用模块入口可避免复制 `Scripts/` 后旧绝对路径问题。启动脚本还应先切到项目根目录；inmem 的 `.langgraph_api/` 是相对当前工作目录的位置，不能从不同 cwd 启动而误以为任务丢失。[S12][S15]

### 5.1 本地持久恢复的实际实现

对 PyPI `langgraph-runtime-inmem==0.36.2` wheel 的只读源码核验发现：

- `_persistence.py` 默认每 **10 秒**调用已注册 `PersistentDict.sync()`。
- `database.py` 从 `.langgraph_api/.langgraph_ops.pckl` 及 retry counter 文件恢复；启动时把遗留 `running` 的运行改为 `pending`，供后续执行。
- `checkpoint.py` 使用 `.langgraph_api/.langgraph_checkpoint.*.pckl`；checkpoint、core resources 和 retry counter 为多个文件。
- 正常 shutdown 会关闭并同步相关存储；进程被强制结束时，最近未 flush 的内容仍可能丢失。多文件快照也不等于跨资源原子事务。开发缓存反序列化失败或代码结构变化时，源码存在移除不兼容缓存的处理。

这些是固定发行包源码事实，**不是本项目重启测试结果**。本地开发服务可以作为笔试演示和正常重启恢复的首选验证路径；不能作为任意断电零丢失、跨进程强一致或正式财务事实的唯一存储。[S15]

源码 wheel SHA-256：`04e3fb054411672c17890d6d3bb521bf69b44f3ac1aab6b4a5a885c6714611f6`。没有为了验证而安装或执行其代码。

### 5.2 GaussDB 与 Redis 的职责

业务产物 revision、材料与证据索引、人工修改、审批绑定、控制与能力版本、预算和真实回执继续写 GaussDB；这些不依赖 UI SSE 缓冲是否还在。规划直接复用 `TodoListMiddleware/write_todos` 的原生状态与检查点，不增加独立 Plan/DAG 或第二套可写计划事实。Redis 可承担本项目需要的通知等服务职责；官方 dev 自带运行队列，不为同一 Agent run 再搭一套并行主队列。[项目约定；S6]

运行所有权、调度与线程并发控制由 Agent Server 管理。项目只通过原生 middleware wrapper 在每次实际调用前核对业务 control/revision、能力版本、审批参数摘要和预算；审批等待后按约定原子重验相关业务版本、参数和预算，并保存已发生的真实回执。不增加带计划步骤和分布式租约的执行系统。

若严格验收要求更强 checkpoint durability，优先评估官方 `checkpointer.path` 扩展。该功能当前 alpha，官方要求通过 `langgraph-checkpoint-conformance`；许多开源 saver 尚不覆盖 Agent Server 全部操作，因此不能把 `AsyncSqliteSaver` 或 GaussDB saver 插入示例视为已经兼容。也不能只更换 saver 就承诺 core resources、run queue 与业务 revision 全部具备同一事务保证。[S10]

## 6. FastAPI 的最小扩展形态

```json
{
  "dependencies": ["."],
  "graphs": { "billing_agent": "./src/billing_agent/agent.py:agent" },
  "http": { "app": "./src/billing_agent/webapp.py:app" }
}
```

此为未来目标配置，不代表文件已经存在。Python graph 导出 `create_agent(...)` 结果，**不在 graph 内另配 checkpointer/store**；Agent Server 按部署配置注入。`webapp.py` 导出 FastAPI app，使用 lifespan 初始化 GaussDB/Redis 连接与官方 MCP 适配器等资源，添加 `/api/tasks`、材料、证据、字段修订、审批和能力配置接口。Vue 构建产物可以通过扩展 app 服务或由前端代理同源接入。[S7][S8]

官方 custom routes 支持完整 FastAPI/Starlette 兼容 app。自定义路由优先于默认路由，因此业务路由使用独立前缀，避免无意覆盖 `/threads`、`/runs`、协议命令和流接口。这样 UI 使用原生运行协议，业务修改与审批另走明确领域契约。[S7]

## 7. 独立/生产 Agent Server 与薄 FastAPI 主机的区别

| 方案 | 框架负责 | 本项目负责 | 适用条件 |
| --- | --- | --- | --- |
| 官方 `dev` + FastAPI 扩展 | 原生 Agent HTTP API、开发运行队列、线程、checkpoint 注入、v2 协议和流 | 领域规则/数据/证据/控制、Vue 页面、真实服务适配 | 首期本地笔试；需完成本项目 Windows 与重启验收 |
| 官方 standalone + FastAPI 扩展 | 同一原生 API，加持久运行基础设施 | 相同领域代码及部署配置 | 支持 PostgreSQL/Redis、容器及相应 key/license；官方生产推荐 Kubernetes |
| 独立薄 FastAPI host | `create_agent`、直接 graph stream、interrupt、saver 等库能力 | HTTP、后台任务、连接生命周期、恢复协调及前端适配 | 仅在官方 server 不满足交付条件时另行评估；不能宣称天然具备 Agent Server 的线程/queue/协议能力 |

standalone 文档明确：core assistants/threads/runs/crons 始终使用 PostgreSQL；checkpoint 可替换，store 可扩展，但不能藉此免除核心 PostgreSQL。Redis 承担信号、取消与 streaming pub/sub，核心 run 数据在 PostgreSQL。standalone 前置条件列出 `DATABASE_URI/REDIS_URI/LANGSMITH_API_KEY/LANGGRAPH_CLOUD_LICENSE_KEY` 和相关连通条件；Docker/Compose 示例定位开发测试，生产测试路径为 Kubernetes。[S8][S9]

PyPI 开发 API 发行包带 Elastic License 2.0，前端 SDK 为 MIT；开发包与生产许可路径不能混为一谈。打包时保留依赖原有 license/notice，并按实际部署方式核对条件，不擅自绕过许可功能。[S3][S13]

## 8. 实现前的最小验证闭环

1. 在 `bishi1/` 固定依赖解析；验证 API、FastAPI/Starlette、Windows 二进制依赖能共同导入，不调用真实模型/OCR。
2. 用最小离线 graph 验证 Vue v1 与官方本地 server 的 submit、values、tool lifecycle、多中断、resume、stop/disconnect 和线程切换；再接 `create_agent`。
3. 保存 `.langgraph_api/` 与业务数据库状态，验证暂停后正常关闭/重启，仍以同一 task/thread 恢复；确认人工 revision、能力版本、预算和回执一致。
4. 分别测试浏览器断开/刷新、在途连接重开、订阅范围扩宽、正常 server 重启和强制结束；记录哪些由 snapshot 恢复、哪些事件已不在回放窗口。不能把正常重启成功扩写成强制崩溃无损。
5. 完成移目录、项目外 cwd 启动与解压迁移验证；把 Vue build 和实际 server 依赖一同打包，Node 仅在需要运行时扩展时另核对。

上述步骤是后续验证计划。本次仅完成文档/API/固定源码核验；不要求为了文档修改运行业务测试。

## 9. 来源

- **S1** LangChain frontend overview（Docs MCP）：https://docs.langchain.com/oss/python/langchain/frontend/overview
- **S2** Vue API Reference（Reference MCP）：https://reference.langchain.com/javascript/langchain-vue/useStream ；https://reference.langchain.com/javascript/langchain-vue/UseStreamReturn
- **S3** 固定 Vue v1 迁移指南与 package（GitHub MCP，commit `cc29753d529caa5eed97a65e765ba26c0f88c631`）：https://github.com/langchain-ai/langgraphjs/blob/cc29753d529caa5eed97a65e765ba26c0f88c631/libs/sdk-vue/docs/v1-migration.md ；https://github.com/langchain-ai/langgraphjs/blob/cc29753d529caa5eed97a65e765ba26c0f88c631/libs/sdk-vue/package.json
- **S4** Adapter API（Reference MCP）及固定实现：https://reference.langchain.com/javascript/langchain-vue/AgentServerAdapter ；https://reference.langchain.com/javascript/langchain-vue/HttpAgentServerAdapter ；https://github.com/langchain-ai/langgraphjs/blob/cc29753d529caa5eed97a65e765ba26c0f88c631/libs/sdk/src/client/stream/transport.ts ；https://github.com/langchain-ai/langgraphjs/blob/cc29753d529caa5eed97a65e765ba26c0f88c631/libs/sdk/src/client/stream/transport/http.ts
- **S5** 官方 protocol v2 HTTP 契约（Docs MCP）：https://docs.langchain.com/langsmith/agent-server-api/streaming/protocol-v2-command ；https://docs.langchain.com/langsmith/agent-server-api/streaming/protocol-v2-event-stream-sse
- **S6** 官方 local dev/testing 与 CLI（Docs MCP）：https://docs.langchain.com/langsmith/local-dev-testing ；https://docs.langchain.com/langsmith/cli
- **S7** 官方 custom routes/lifespan（Docs MCP）：https://docs.langchain.com/langsmith/custom-routes ；https://docs.langchain.com/langsmith/custom-lifespan
- **S8** Agent Server persistence、queue、graph 注入（Docs MCP）：https://docs.langchain.com/langsmith/agent-server
- **S9** 官方 standalone 部署（Docs MCP）：https://docs.langchain.com/langsmith/deploy-standalone-server
- **S10** 官方 checkpointer 扩展与一致性测试（Docs MCP）：https://docs.langchain.com/langsmith/custom-checkpointer ；https://docs.langchain.com/langsmith/configure-checkpointer
- **S11** npm 官方元数据（只读 HTTP 核验）：https://registry.npmjs.org/@langchain%2Fvue ；https://registry.npmjs.org/@langchain%2Fvue/0.4.7
- **S12** CLI 官方 PyPI 元数据与 wheel（只读核验）：https://pypi.org/pypi/langgraph-cli/0.4.37/json
- **S13** API 官方 PyPI 元数据与 wheel 源码（只读核验，含 `api/event_streaming.py`、`LICENSE`）：https://pypi.org/pypi/langgraph-api/0.16.2/json
- **S14** Python event streaming（Docs/Reference MCP）：https://docs.langchain.com/oss/python/langgraph/event-streaming ；https://reference.langchain.com/python/langgraph/pregel/main/Pregel/stream_events
- **S15** runtime 官方 PyPI 元数据与固定 wheel 源码（只读核验，`_persistence.py/database.py/checkpoint.py`）：https://pypi.org/pypi/langgraph-runtime-inmem/0.36.2/json
