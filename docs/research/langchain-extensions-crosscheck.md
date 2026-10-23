# LangChain 1.4.6：动态工具、MCP、Skills 与 Hook 交叉核对

> **研究快照，2026-10-21复核。** 下文缺可选依赖是补齐前状态，不能作为当前缺依赖结论；统一网关等早期建议已由官方middleware装配替代。当前规则见[实现方案](../implementation.md)、[Skill/Hook设计](../skills-and-hooks.md)，实施见[最终开发计划](../superpowers/plans/2026-10-21-final-development-plan.md)。

依赖状态更新（2026-10-21）：用户随后要求补齐 MCP 可选依赖，现已安装 FastMCP 4.1.2、MCP 2.3.0，并通过本地 stdio 发现及发现上下文退出后调用。下文未安装和未连接的描述保留为先前研究时快照，当前状态与复验命令见 [portable-environment.md](../portable-environment.md)。实际安装版本中，单服务 MCPConfig 保留原工具名 `add`；多服务或 ClientGroup 的命名规则需按实际目录确认，不能一律自行拼接服务前缀。

核对日期：2026-10-21，Asia/Shanghai。本记录先查询 LangChain 文档 MCP，再用 GitHub MCP 固定官方源码，最后对照项目便携式 Python 的已安装源码。未安装或升级依赖，未读取 `.env`，未修改 `AGENT.md`，未调用在线模型、OCR、数据库或实际 MCP 服务。本文是研究与设计依据，不代表功能已经实现。

## 1. 版本与证据范围

| 对象 | 本次范围 | 核对结果 |
| --- | --- | --- |
| LangChain | 本机 `1.4.6`；tag `langchain==1.4.6` | GitHub commit `84ba23c414eca6bf6f6ebd1394a3006378113540`，2026-10-14T17:19:35Z |
| langchain-core | 本机 `1.6.12` | 读取包元数据；本文不把当前网页等同于该包全部 API |
| LangGraph | 本机 `1.2.16` | 读取包元数据；仅作 `create_agent` 底层运行时 |
| langgraph-prebuilt | 本机 `1.1.1`；tag `prebuilt==1.1.1` | GitHub commit `5eb60aef6f3837a1fb632a8abc6cf8e8da81785b`，2026-10-15T01:31:09Z |
| 内置 MCP | 本机有 `langchain/mcp/` 源码 | `fastmcp` 未安装；实际 `import langchain.mcp` 得到 `ModuleNotFoundError: No module named 'fastmcp'` |
| 旧适配包 | `langchain-mcp-adapters` | 本机未安装 |
| Deep Agents | 复用已完成的固定源码研究 | `0.7.29`，commit `3abfb0abcda658d4b64e74782f3316a11efc3faa`；不声称其为此刻 main 的最新提交 |

对 LangChain 的 `agents/factory.py`、`agents/middleware/types.py`、`tools/tool_node.py`、`mcp/{adapter,tools,elicitation,__init__}.py` 逐个计算本机文件 Git blob SHA，与 GitHub MCP 文件响应完全一致。`langgraph/prebuilt/tool_node.py` 同样与上述 prebuilt commit 一致（blob `c0398f8f46e6f0cda3376fae6958e4713e51cbb6`）。因此下述执行语义确实对应本机源码，不只是当前在线文档。

官方文档属于查询当日的滚动页面；固定 commit 源码才是本次选定版本的实现依据。Deep Agents 的交付研究记录见 [deepagents.md](deepagents.md)；`.build/research/deepagents-source-review-2026-10-21.md` 为可排除的原始笔记，此处仅复用与扩展入口有关的结论。

Primary sources：

- [LangChain 1.4.6 commit](https://github.com/langchain-ai/langchain/commit/84ba23c414eca6bf6f6ebd1394a3006378113540)
- [1.4.6 依赖声明](https://github.com/langchain-ai/langchain/blob/84ba23c414eca6bf6f6ebd1394a3006378113540/libs/langchain_v1/pyproject.toml#L24)
- [prebuilt 1.1.1 commit](https://github.com/langchain-ai/langgraph/commit/5eb60aef6f3837a1fb632a8abc6cf8e8da81785b)
- [Deep Agents 研究快照](https://github.com/langchain-ai/deepagents/commit/3abfb0abcda658d4b64e74782f3316a11efc3faa)

## 2. 动态工具：模型可见与执行权限分别控制

文档区分两种能力：从预先注册的工具中动态筛选，使用 `wrap_model_call` 修改 `ModelRequest.tools`；运行时才发现的工具，还必须用 `wrap_tool_call` 提供执行实现。推荐形式为 `handler(request.override(tool=resolved_tool))`；异步路径对应 `awrap_model_call` 与 `awrap_tool_call`。

1.4.6 源码与此一致：

- `factory.py:1135-1157` 用注册工具创建 `ToolNode.tools_by_name`，再以该集合初始化模型请求；`factory.py:1424-1427` 用 `request.tools` 构造本次模型绑定的工具表。修改后者并不删除前者的执行对象。
- `factory.py:1372-1397` 在没有 tool wrapper 时检查模型请求中的未知工具；存在 wrapper 时允许动态执行解析。**仅仅装了 wrapper 不会自动实现动态工具注册或权限检查。**
- `ToolNode._run_one/_arun_one`（1031、1191 行起）按工具调用名称取注册对象，构造 `ToolCallRequest` 后先运行 wrapper；未知工具的校验推迟到实际执行处。wrapper 因而能拒绝调用、暂停，或注入动态 `BaseTool`。
- `_execute_tool_sync/_execute_tool_async`（930、1090 行起）执行的是 `request.tool`，不是再次读取本次模型可见列表。`ToolCallRequest.override()` 使用 dataclass `replace`，实际支持替换 `tool`。

项目应在规划前向模型暴露当前允许的 schema，并在每次实际派发前检查任务状态、当前启用状态、能力版本、权限与最终参数。模型过滤用于减少不合适选择；派发检查负责拦住旧计划、恢复中的旧调用和手工构造的调用。动态工具尚未解析时 `request.tool` 可以为 `None`，读取 MCP metadata 之前应先解析或按空值处理。

工具名称也不能代替不可变版本。对一次被接受的调用，固定实际实现引用、参数、规则与能力版本；不在执行过程中按相同名称静默换成新实现。已有注册对象、模型 schema、新目录和执行许可需要由同一个运行时能力快照协调。

Primary sources：

- [文档：Runtime tool registration](https://docs.langchain.com/oss/python/langchain/tools#runtime-tool-registration)
- [文档：Custom middleware](https://docs.langchain.com/oss/python/langchain/middleware/custom)
- [1.4.6：工具注册与模型绑定](https://github.com/langchain-ai/langchain/blob/84ba23c414eca6bf6f6ebd1394a3006378113540/libs/langchain_v1/langchain/agents/factory.py#L1135)
- [prebuilt：派发前 wrapper](https://github.com/langchain-ai/langgraph/blob/5eb60aef6f3837a1fb632a8abc6cf8e8da81785b/libs/prebuilt/langgraph/prebuilt/tool_node.py#L1031)
- [prebuilt：实际异步执行](https://github.com/langchain-ai/langgraph/blob/5eb60aef6f3837a1fb632a8abc6cf8e8da81785b/libs/prebuilt/langgraph/prebuilt/tool_node.py#L1090)

## 3. MCP：使用内置入口，额外依赖仍未具备

当前官方迁移文档说明 MCP 从 LangChain 1.4.0 起进入 `langchain.mcp`，替代独立适配包。1.4.6 的确有 `MCPAdapter`、`as_langchain_tool` 和 `MCPToolArtifact`，且 namespace 明确标为 beta。`pyproject.toml:51` 的 extra 是 `mcp = ["fastmcp>=4.0.11,<5.0.0"]`。本机虽有适配源码，却没有 FastMCP，不能写成“已可使用 MCP”。本次不为研究安装依赖。

选定版本的准确入口：

```python
from langchain.mcp import MCPAdapter

config = {"mcpServers": {"service_id": {"url": "https://example.com/mcp"}}}
async with MCPAdapter(config) as adapter:
    tools = await adapter.list_tools(cache_mode="refresh")
    # tools 进入项目统一注册/版本发布流程，再由 LangChain 主控使用。
```

`MCPAdapter(target)` 接收 URL、显式 `Path`、transport、MCPConfig 字典、预建 FastMCP Client 或 ClientGroup 等。**裸字符串只能是 http/https URL**；本地 stdio 要显式用 `Path`、transport 或包含 `command/args` 的 MCPConfig，不能把字符串路径直接当 target。多服务器目录使用 `{server}_{tool}` 名称。Windows 便携交付还要携带相应 stdio 可执行程序并使用可迁移路径；SDK 不提供这些程序。

旧资料中的 `MultiServerMCPClient.get_tools()`、`tool_interceptors`、`ToolCallInterceptor`、`MCPToolCallRequest`、`MCPToolCallResult` 不应成为新实现入口。当前使用 LangChain tool middleware 拦截本地与 MCP 工具。来源位于 `(request.tool.metadata or {}).get("mcp", {})`，再分 `tool.annotations`、`tool._meta`、`server`；字段都可能缺失。MCP annotations 是服务器声明的提示，不能提升权限或独立决定财务动作的审批策略。

`mcp.server` 来自连接的 `server_info`，是协议实现身份，不足以充当项目的注册服务 ID、租户、凭据主体或工具版本。项目注册表仍需明确写入这些归属。`isError=True` 被转换为 `ToolMessage(status="error")`；传输或内容转换错误仍会抛出。该区分应进入结构化错误分类，不能将两者统一按“模型修一下再重试”处理。

迁移并非所有旧 helper 功能均有同名替代：当前 namespace 主要包装工具，未包装 prompts/resources；需要时可以专门评估底层 FastMCP 调用。现阶段不能以安装 MCP 适配器推定 Skills、资源权限和生命周期均已具备。

Primary sources：

- [官方 MCP 迁移指南](https://docs.langchain.com/oss/python/migrate/langchain-mcp-adapters)
- [1.4.6：MCP target 与入口](https://github.com/langchain-ai/langchain/blob/84ba23c414eca6bf6f6ebd1394a3006378113540/libs/langchain_v1/langchain/mcp/adapter.py#L125)
- [1.4.6：裸字符串 URL 校验](https://github.com/langchain-ai/langchain/blob/84ba23c414eca6bf6f6ebd1394a3006378113540/libs/langchain_v1/langchain/mcp/adapter.py#L84)
- [1.4.6：MCP metadata](https://github.com/langchain-ai/langchain/blob/84ba23c414eca6bf6f6ebd1394a3006378113540/libs/langchain_v1/langchain/mcp/tools.py#L183)
- [1.4.6：异步工具与错误转换](https://github.com/langchain-ai/langchain/blob/84ba23c414eca6bf6f6ebd1394a3006378113540/libs/langchain_v1/langchain/mcp/tools.py#L234)

## 4. 连接、刷新与热更新边界

`MCPAdapter.__aenter__/__aexit__` 委托底层 client/group；`list_tools()` 自己也进入一次 adapter 上下文。返回的工具捕获该 client，实际调用时再执行 `async with client`，然后请求远端。因此：

- 退出发现时的 `async with MCPAdapter(...)` 只释放该上下文的连接占用，**不会让已返回的工具失效**；之后调用仍可重新进入 client。补齐后的 FastMCP 4.1.2 默认 stdio `keep_alive=True`，最终退役需显式 `await adapter.client.close()`；上下文退出本身不能证明子进程已经关闭或下一次调用必然重建连接。
- 保持 adapter 上下文包住 Agent 的一次运行，可由可重入 client 复用连接。实际传输、会话与现代协议的行为由 FastMCP 协调，不应假定所有服务器都需要同一种长期 session。
- `list_tools(cache_mode="use")` 默认使用已配置缓存与服务器 TTL；`refresh` 重新获取并填缓存，`bypass` 跳过缓存。缓存本身在 client 配置，发现刷新没有发布事务的含义。
- 新目录不会自动替换既有 Agent 的 `ToolNode`，也不会原子撤销旧工具对象；关闭 adapter 上下文同样不是撤权操作。

项目热更新至少需要候选配置校验与发现、生成能力版本、原子发布可见快照、派发处再次检查，以及旧版本引用计数/在途排空后释放。发现失败保留上一有效快照；更新不能覆盖已经接受的一次调用。远端服务器是否提供不可变实现或版本校验也要单独确认；本地固定一个工具包装对象并不能阻止远端原地升级。无法保证版本时，不能声称固定了远端实现，应限制副作用或要求重新规划/审批。

审批绑定版本、参数摘要及规则版本；刷新、禁用、重规划或人工改参造成依赖变化时由项目使审批失效。恢复时缺少旧版本要明确迁移或重新审批，不按工具同名自动换版。暂停/禁用只能阻止后续派发；已发出的远端操作需记录真实结果，未知结果先核对再重试。

Primary sources：

- [文档：连接生命周期与缓存](https://docs.langchain.com/oss/python/langchain/mcp/connections)
- [1.4.6：连接入口与 list_tools](https://github.com/langchain-ai/langchain/blob/84ba23c414eca6bf6f6ebd1394a3006378113540/libs/langchain_v1/langchain/mcp/adapter.py#L207)
- [1.4.6：每次工具调用进入 client](https://github.com/langchain-ai/langchain/blob/84ba23c414eca6bf6f6ebd1394a3006378113540/libs/langchain_v1/langchain/mcp/tools.py#L283)

## 5. Hook：最终派发、重试与执行事实

`AgentMiddleware.wrap_tool_call` / `awrap_tool_call` 的合同是返回 `ToolMessage` 或 `Command`。可以不调用 handler 来短路；不应照抄旧 Skill 中返回普通字符串的拒绝样例。若项目支持同步与异步调用，应实现两条路径；仅实现一种而通过另一种 `create_agent` 调用会触发明确的 `NotImplementedError`。内置 MCP 工具本身为异步 coroutine，项目宜统一使用 `ainvoke/astream`，并明确拒绝不支持的同步入口。

middleware 列表首项为最外层。handler 允许被多次调用，所以仅把权限检查放在最外层、再把 retry 放到内层，可能导致内层再次执行时不经过该检查。权限、暂停、版本与预算的最终检查应置于实际网关派发入口，确保每次重试都检查；参数修改也要先完成，再用最终参数重校验及核对审批绑定。工具直接被别的代码调用、opaque 子图或工具内部自发的外部操作，并不会自动被父 Agent middleware 覆盖。

LangChain 的模型/工具 middleware 适合包装调用；账单 `before_commit/after_commit`、人工编辑版本、审批失效和跨重启执行账本是项目业务设施。应分别保存 `tool_execution` 和 `hook_execution`：外部操作成功后 observer Hook 失败，只重试后处理，不能重跑已成功的提交。必需校验失败则应在提交前停止。不要用一个宽泛异常重试包住“外部操作 + 所有后置 Hook”。

Primary sources：

- [1.4.6：tool middleware 合同](https://github.com/langchain-ai/langchain/blob/84ba23c414eca6bf6f6ebd1394a3006378113540/libs/langchain_v1/langchain/agents/middleware/types.py#L674)
- [1.4.6：async tool middleware](https://github.com/langchain-ai/langchain/blob/84ba23c414eca6bf6f6ebd1394a3006378113540/libs/langchain_v1/langchain/agents/middleware/types.py#L756)
- [1.4.6：wrapper 顺序](https://github.com/langchain-ai/langchain/blob/84ba23c414eca6bf6f6ebd1394a3006378113540/libs/langchain_v1/langchain/agents/factory.py#L710)
- [1.4.6：sync/async middleware 组装](https://github.com/langchain-ai/langchain/blob/84ba23c414eca6bf6f6ebd1394a3006378113540/libs/langchain_v1/langchain/agents/factory.py#L1091)

## 6. MCP elicitation 与人工审批不是同一种恢复请求

选定版本默认将支持的服务器 elicitation 映射为 LangGraph interrupt；调用者提供自己的 elicitation handler 时保留该 handler。中断 payload 的 `type` 为 `mcp_elicitation`，含 `tool_name` 与带 key 的 requests。应使用 checkpointer 和同一个 thread ID，按 `Command(resume={"responses": {key: answer}})` 恢复；每个 answer 的 action 为 `accept/decline/cancel`。不能把它混同工具审批的 approve/edit/reject 数据结构。

源码 `_call_tool_with_interrupts()` 明确写明：interrupt 会展开整个工具调用，恢复会从首轮重新发出。服务器在提问之前已经执行的工作可能重复。需要远端幂等键、调用回执或状态核对；图检查点本身不能证明副作用恰好执行一次。

这一机制只回答 `InputRequiredResult` 中的 elicitation。sampling、roots、没有问题的 continuation 轮次会被拒绝；仅支持 legacy server-pushed elicitation 的服务也不能由此自动处理。连接测试应覆盖目标服务器的实际协议与交互方式，不以存在 `MCPAdapter` 类推定所有 MCP 服务均兼容。

Primary sources：

- [文档：MCP tools / elicitation](https://docs.langchain.com/oss/python/langchain/mcp/tools#elicitation)
- [1.4.6：中断与恢复类型](https://github.com/langchain-ai/langchain/blob/84ba23c414eca6bf6f6ebd1394a3006378113540/libs/langchain_v1/langchain/mcp/elicitation.py#L94)
- [1.4.6：恢复重发及支持边界](https://github.com/langchain-ai/langchain/blob/84ba23c414eca6bf6f6ebd1394a3006378113540/libs/langchain_v1/langchain/mcp/elicitation.py#L312)

## 7. Skills 与子 Agent：复用已核对的 Deep Agents 快照

Skills 是指令与资源，不是 MCP 工具协议或自动授权机制。Deep Agents 0.7.29 的 `SkillsMiddleware` 可用于渐进暴露：模型最初看到索引；完整 Skill 正文通常由 `read_file` 按需读入，或由 pinned skill 主动插入。索引扫描实际会下载完整 `SKILL.md` 再解析 frontmatter，因此这是上下文渐进披露，不能声称磁盘 I/O 永远只读索引字节。

`skills_metadata` 已存在时会缓存；置为 `None` 才在下次 `before_agent` 重新加载。未见默认文件监听、整体校验后原子发布、失败保留旧版本的生命周期。`metadata.include_tools` 配合 tools resolver 可在读取 Skill 后向模型披露工具，并在 `wrap_tool_call` 时重新解析；撤回 resolver 中的工具会使调用失败。但模型时和执行时重新解析也可能拿到不同实现，版本快照和审批失效仍需项目负责；`allowed-tools` 是元数据，不是权限系统。

普通声明式子 Agent 独立组装 middleware；默认 general-purpose 子 Agent只继承匹配默认槽的定制项，并不普遍继承任意父 Hook。`CompiledSubAgent` runnable 原样使用；实验性 fork 模式的继承规则也不能推及 isolated 模式。仅拦父 `task` 工具看不到 opaque 子图内部每个工具派发。所有可执行子 Agent 需显式安装项目适配器并使用同一工具网关，或只返回提案而无直接提交权限。

这些结论复用既有研究，没有再次安装或运行 Deep Agents。LangChain 仍作主控；Deep Agents 仅作为受控可选子 Agent，不因引入 Skills 而替换主编排。

Primary sources：

- [Deep Agents：Skill 扫描](https://github.com/langchain-ai/deepagents/blob/3abfb0abcda658d4b64e74782f3316a11efc3faa/libs/deepagents/deepagents/middleware/skills.py#L687)
- [Deep Agents：SkillsMiddleware 加载缓存](https://github.com/langchain-ai/deepagents/blob/3abfb0abcda658d4b64e74782f3316a11efc3faa/libs/deepagents/deepagents/middleware/skills.py#L1168)
- [Deep Agents：动态 Skill 工具](https://github.com/langchain-ai/deepagents/blob/3abfb0abcda658d4b64e74782f3316a11efc3faa/libs/deepagents/deepagents/middleware/skills.py#L1322)
- [Deep Agents：子 Agent middleware 栈](https://github.com/langchain-ai/deepagents/blob/3abfb0abcda658d4b64e74782f3316a11efc3faa/libs/deepagents/deepagents/graph.py#L723)
- [Deep Agents：general-purpose 继承边界](https://github.com/langchain-ai/deepagents/blob/3abfb0abcda658d4b64e74782f3316a11efc3faa/libs/deepagents/deepagents/graph.py#L854)
- [Deep Agents：compiled 与 isolated 行为](https://github.com/langchain-ai/deepagents/blob/3abfb0abcda658d4b64e74782f3316a11efc3faa/libs/deepagents/deepagents/middleware/subagents.py#L575)

## 8. 已执行验证与实现时的必要调整

本机通过 `python.cmd -B -` 执行无网络、无真实副作用的最小异步探针：在局部测试图中包装 `ToolNode`，拒绝 wrapper 返回 `ToolMessage(status="error")` 后 spy 计数为 **0**；对空注册表以 `request.override(tool=async_probe)` 注入实现，返回 `7` 且 spy 计数为 **1**。这只验证派发语义，没有验证 Qwen、MCP 网络、Skill、账单或持久恢复。直接独立 `ToolNode.ainvoke` 的初次探针因缺少新版本所需图 runtime 报错；补为局部图运行后成功，不将初次错误隐藏为通过。

后续实现应落实以下差异：

1. 以 `langchain.mcp.MCPAdapter` 为候选接入 API，锁定 optional extra 的完整依赖；当前状态仍是未安装 FastMCP、未做实际 MCP 调用。
2. 一个统一网关承担每次实际派发的禁用、暂停、权限、最终参数、版本、审批和预算检查；模型筛选与重发现只负责可见性和目录更新。
3. 能力候选校验、原子发布、旧版本保留、在途排空、失败回退、远端版本能力与恢复迁移分别实现，不能把 `cache_mode="refresh"` 称为完整热更新。
4. MCP 来源加项目 server ID、租户/凭据主体、能力版本；服务器 annotations 与 Skill 文本均不能授权。
5. tool middleware 明确覆盖异步路径；重试不能绕过最后一次派发检查。子 Agent 显式接入同一网关，不假定父 Hook 全部继承。
6. 账单提交校验、执行回执与 observer 后处理分开持久化；MCP elicitation 与业务审批分开建模，恢复先核对版本和已有执行事实。

本文未更改架构基线或依赖，是供主报告整合的固定版本研究记录。
