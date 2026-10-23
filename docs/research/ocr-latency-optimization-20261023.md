# OCR 与账单处理时延优化（2026-10-23）

本轮修改当前目录的代码。OCR 在远程服务器，本机未修改远端模型、队列或推理实现；没有重新请求在线 OCR/Qwen，没有重算历史账单。

## 已确认的瓶颈

会话 7 首轮耗时 240.632 秒，其中 `intake_documents` 157.104 秒；15 次真实模型请求、15 次工具调用，包含 5 次单独计划更新。对同一个三页 PDF 单独实测：上传/签名 0.527207 秒，OCR HTTP 208.739338 秒，其中连接约 0.061 秒、等待响应头约 208.626 秒。等待发生在远程响应阶段，不能归因于本地上传，也不能从客户端测量进一步断言远端排队或推理各占多少。详见 [实测回执](../../backend/tests/reports/ocr-timing-20261023-020146/timing.json)。

## 实现

- `document-intake 1.7.0`：以文件内容 SHA256、端点、固定请求参数及服务契约版本为键，缓存成功的原始 HTTP 响应；跨进程文件锁合并相同文件在途识别，等待期间检查任务控制。命中后不上传、不签名、不请求 OCR。失败、空单据、超期或损坏缓存不复用；缓存写入失败保留当前任务的成功回执。每个任务仍生成自己的 source_id、原页映射和原始响应副本，不缓存账单判断或证据身份。
- 本地 PDF 文字层/版式读取后立即保存只读初读内容，并通过原生 `ToolRuntime.stream_writer` 发进度；Vue 使用当前 `@langchain/vue 1.2.5` 的 `useChannelEffect` 订阅 custom 通道，触发既有业务视图刷新。初读表格明确显示正在核对，不可当正式账单审批。上传、等待远程、缓存命中和识别返回分别显示阶段。
- `document-extraction 2.2.0`：相同 PDF、页码和读取方式已有结果时返回 `added_anchors=[]`，宿主返回简短复用回执；版式读取即使命中已有内容也验证原件哈希。局部修正保留未提交字段，显式 null 仍可清空。
- 主控减少独立计划更新轮次，直接使用已 pin 的 Skill；计划变化与业务调用同轮提交。Markdown 财务行优先展开费用名、币种、金额、数量、单价和原始行，仍保留完整原文及定位映射。
- `evidence-linking 2.1.1`：同一位置的全名/归一化子串不再被算成两次出现；真正重复位置仍报歧义。`human-review 2.0.4` 清除主体已补充后的过时主体告警，并按字段合并单据头。`billing-confidence 3.0.1` 统一总额作用域，info 不作为阻断项，已有独立行金额时额外引用总额不会取消总额支持；仅复用同一数值的伪总额仍不加分。
- 没有 coverage 的修正同样受重复候选与每范围两轮上限约束，人工新 revision 重置修正计数。空 tool_call id 在原生 `ModelResponse.result` 内修复，保留 structured_response；增加原生图级关联测试。
- 增加模型轮次、输入/输出/cache-read token、工具刷库耗时及逐来源 OCR 的上传、HTTP、缓存等待回执。模型轮次耗时包含 middleware/handler 工作，不能冒充纯模型 HTTP 耗时。列表中的待答问题以当前官方检查点刷新，避免继续显示旧 thread summary 中断。

列表先对比 summary 中断的 revision、业务 review_request 和线程状态，只对不一致项读取检查点，最多同时三项；正常问题清单不会逐单加载完整消息。

配置版本为 skills **v30**、agents **v12**，runtime 保持 **v6**。历史不可变发布目录不修改；新任务固定新 Skill 能力，旧任务不迁移。

## 缓存配置与边界

宿主缓存目录为 `backend/data/cache/ocr`。`OCR_CACHE_TTL` 默认 86400 秒，`OCR_CACHE_VERSION` 默认 `orderChange-v1`；这是服务契约的手动失效标记，远端真实服务版本仍记 unknown。端点或契约版本改变产生新键，缩短 TTL 对已存条目立即生效。模型、提示词或本地解析器改变会重新映射原响应，不要求重新识别相同文件。共享缓存只用于本地部署中原有同一信任范围的任务。

将本次此前真实实测的一个 PDF 响应核对原件哈希、HTTP 状态、响应长度及成功单据后回填缓存，保留原收到时间和原 TTL；没有批量回填其他历史响应。见 [单条导入回执](../../backend/tests/reports/ocr-optimization-20261023/cache-import.json)。测试缓存使用临时目录。

## 验证与性能解释

[可复现回放脚本](../../backend/tests/reports/ocr-optimization-20261023/replay.py) 使用真实三页 PDF 和此前保存的真实 OCR 原始响应，网络请求为 0。第一次注入已有响应并建立临时缓存，完整接入 1.733026 秒、本地初读 1.720182 秒；新上传身份命中内容缓存，完整接入 0.877699 秒、本地初读 0.867975 秒。两次均保留 1 个单据、1 条费用、3 页映射，source_id 不同，原始响应副本指向各自任务目录。详见 [回放计时](../../backend/tests/reports/ocr-optimization-20261023/timing.json)。

这些数值只验证本地解析与缓存路径，不是新任务含在线模型的端到端耗时，也不是新的冷 OCR 测量。首次未命中的远程识别仍可能等待约 209 秒；前端可先显示本地初读结果。尚无本轮真实在线任务的调用次数对比或规模分层 P50/P95。

实际新发布能力 `c16c912c031923ddbb8f` 的独立进程读取上述业务缓存，完整接入 **1.752991 秒**、网络请求 0；包含该进程首次加载 PDF 依赖，不能与同进程暖运行混为同一测量。见 [发布能力缓存验证](../../backend/tests/reports/ocr-optimization-20261023/published-cache.json)。

## 框架查证与检查结果

通过已配置的 `https://docs.langchain.com/mcp`，用官方 MCP Python 客户端实际调用 `query_docs_filesystem_docs_by_lang_chain` / `search_docs_by_lang_chain`，核查 custom middleware、ModelResponse、get_stream_writer、图节点缓存、Deep Agents Skills 与 Vue custom stream channels。Reference MCP 同时查询 ModelResponse、get_stream_writer、CachePolicy。安装组合为 langchain 1.4.6、langgraph 1.2.16、deepagents 0.7.30、httpx 0.28.1、@langchain/vue 1.2.5。新增 filelock 4.2.4 并锁定依赖；`pip check` 通过。图节点 CachePolicy 不能直接缓存任务特定 intake 内部的 HTTP 原始回执，因此只在既有 intake Skill 中补内容缓存，执行、调度和流式仍用原生框架。

- 全部 Skill + host/conversation/codex_reading/workspace/config/version 定向：495 passed（随后增加图级与列表回归，单独通过）。
- `pytest backend/tests backend/skills -q --tb=short`：**584 passed、7 failed、4 subtests passed**。7 项与 AGENT.md 既有记录一致：test_improvement 5 项仍期望缺少正文依据的 payment_term；test_task_runtime_streaming 2 项夹具缺 capability。本轮不放宽财务规则来使旧夹具通过。
- 增补的原生 custom 进度流、ModelResponse 图级调用 ID、独立总额和版本检查：4 passed；最终列表回归：7 passed。
- 前端 `npm run build`（含 vue-tsc）通过。未把静态构建和图级 custom 事件测试说成新在线 OCR 的浏览器验收。
- 后端通过现有 start.cmd 重启至 PID **13952**，GaussDB/Redis 均健康；64 个线程的 ID/状态与重启前一致，会话 7 revision=2、旧能力及保存账单的哈希不变，列表已显示当前收付款角色问题。见 [重启核对](../../backend/tests/reports/ocr-optimization-20261023/restart.json)。
