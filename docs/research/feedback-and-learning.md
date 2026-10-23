# LangChain 官方源码：人工干预、反馈与跨任务改进

> **研究快照。** 固定案例与探针结论保留；当前改进能力归feedback-improvement Skill，遵守[当前实现方案](../implementation.md)及[最终开发计划](../superpowers/plans/2026-10-21-final-development-plan.md)中的样本划分、候选审核、版本发布与回滚，不直接改写共享规则。

核验时间：2026-10-21（Asia/Shanghai）。范围为公开官方仓库的冻结 HEAD 源码、示例控制流和测试；主要使用 GitHub MCP `get_file_contents` / `get_commit`。为定位文件另作浅克隆。没有读取项目或仓库的 `.env`，没有执行会发送邮件或调用在线模型的示例，没有修改 AGENT.md。

这三个仓库分别提供教学应用、记忆/提示词优化原语、评测原语；不能把它们合称为已经验证的财务自学习系统。以下是静态源码审计，不是声称在本地跑通其完整测试或在线集成。

## 冻结版本

| 官方仓库 | 核验 HEAD | GitHub committer date（UTC） |
| --- | --- | --- |
| langchain-ai/agents-from-scratch | `603fc7a4ac6119004f43894395e504a1fefcc6c0` | 2026-08-11T15:37:42Z |
| langchain-ai/langmem | `48e3c11f5bb527282c7d5339c6a87a0b35abccfc` | 2026-10-02T19:35:19Z |
| langchain-ai/openevals | `9166120ee4e7daaf847b82dd6f18993777a5cc30` | 2026-10-19T12:06:21Z |

提交页面：

- https://github.com/langchain-ai/agents-from-scratch/commit/603fc7a4ac6119004f43894395e504a1fefcc6c0
- https://github.com/langchain-ai/langmem/commit/48e3c11f5bb527282c7d5339c6a87a0b35abccfc
- https://github.com/langchain-ai/openevals/commit/9166120ee4e7daaf847b82dd6f18993777a5cc30

## 1. agents-from-scratch：邮件助手的真实人工反馈控制流

核心源码：

- `src/email_assistant/email_assistant_hitl_memory.py`：`get_memory`、`update_memory`、`triage_router`、`triage_interrupt_handler`、`llm_call`、`interrupt_handler`、`should_continue`。
- https://github.com/langchain-ai/agents-from-scratch/blob/603fc7a4ac6119004f43894395e504a1fefcc6c0/src/email_assistant/email_assistant_hitl_memory.py

控制流核验：

1. `triage_router` 先读 `("email_assistant", "triage_preferences")` 下的偏好，路由 respond / ignore / notify。notify 进入 `triage_interrupt_handler`，由 `interrupt([request])[0]` 等人工输入；response 转入响应 Agent，ignore 结束。两个分支都会调用 `update_memory`。
2. `llm_call` 每次从 store 读取 `cal_preferences` 和 `response_preferences`，拼入后续模型系统提示词。这是已实现的跨任务偏好消费入口，不只是把反馈写进日志。
3. `interrupt_handler` 对 `write_email`、`schedule_meeting`、`Question` 中断。accept 使用原参数调用工具；edit 使用人工参数执行工具并更新 AIMessage 里的工具参数；response 不执行当前工具，把自然语言反馈变为 tool message 交回模型；ignore 不执行该动作并结束。
4. edit 分支在工具调用成功后调用 `update_memory` 写 response/cal 偏好；response 分支也更新偏好；ignore 被解释为以后类似邮件不应 respond，并更新 triage 偏好。这种从一次反馈归纳以后规则的行为真实存在。
5. `update_memory` 本身读旧 profile，调用结构化 LLM 生成整个新 profile 字符串，然后 `store.put` 覆盖该 key。提示词要求保留旧信息，但源码层没有字段差异审查、版本 CAS、人工推广确认或评测门禁。

精确定位：

- 记忆读取和更新：`email_assistant_hitl_memory.py:30-80`。
- 任务分流与人工分流：`:83-222`。
- 每次模型调用消费偏好：`:224-250`。
- 工具中断及 accept：`:253-326`。
- edit 后执行工具并写跨任务偏好：`:328-379`。
- response 反馈后重新规划及写偏好：`:423-446`。
- 图构建：`:471-501`。这是 `StateGraph` 教学实现，不能直接照搬为本项目主编排；本项目应保留 LangChain `create_agent` 主控并通过 middleware 实现对应人工接口。

暂停与续跑示例：

- `notebooks/memory.ipynb` 的 code cell 38 使用 `MemorySaver`、`InMemoryStore`、thread_id，首次 stream 到 interrupt；cell 40/42 使用同一 thread config 与 `Command(resume=[{"type": "accept"}])`；cell 48/51 演示 edit；cell 57/61 演示 response 自然语言反馈。cell 编号为 notebook cells 数组的一基编号。
- https://github.com/langchain-ai/agents-from-scratch/blob/603fc7a4ac6119004f43894395e504a1fefcc6c0/notebooks/memory.ipynb

测试实际证明什么：

- `tests/test_response.py:136-175` 检查所需工具是否出现，明确允许额外工具调用；`:182-223` 用 LLM judge 判断响应是否满足 criteria。
- 但 `:147-151` 与 `:195-199` 明确只支持自动测试 `email_assistant` baseline；HITL/memory 模块会 raise。`setup_assistant` 虽可组装 MemorySaver/InMemoryStore，但不能据此说其人工编辑或记忆收益通过了这些测试。
- `tests/test_notebooks.py:test_notebook_runs_without_errors` 执行 notebook 并检查是否报错，不比较纠错前后质量或未见样本回归；notebook 的 memory 场景会重新创建 InMemoryStore。它展示记忆更新及当前任务行为，不等于受控跨任务效果评测。
- https://github.com/langchain-ai/agents-from-scratch/blob/603fc7a4ac6119004f43894395e504a1fefcc6c0/tests/test_response.py#L136-L223
- https://github.com/langchain-ai/agents-from-scratch/blob/603fc7a4ac6119004f43894395e504a1fefcc6c0/tests/test_notebooks.py#L22-L50

必须保留的局限：

- 示例固定 namespace 没有 tenant/user/accounting_entity 隔离；共享 store 就会共享这些偏好。
- `tools/default/email_tools.py:6-9` 的 write_email 只返回字符串，没有真实发送。不能用默认示例证明真实副作用恢复和幂等性。
- 工具成功后记忆更新报错，是副作用已发生、后处理失败；示例未实现财务级执行账本/幂等回执。
- MemorySaver/InMemoryStore 本身不能证明进程重启恢复和持久跨任务记忆。
- https://github.com/langchain-ai/agents-from-scratch/blob/603fc7a4ac6119004f43894395e504a1fefcc6c0/src/email_assistant/tools/default/email_tools.py#L5-L9

## 2. LangMem：记忆 CRUD 与提示词优化确有实现，但不自动证明改进

核心源码：

- `src/langmem/knowledge/tools.py:create_manage_memory_tool` 创建同步/异步 memory 工具，允许动作受 `actions_permitted` 限制。create 自动生成 UUID；update/delete 要求 id；写入或删除在 namespace 对应 store 中进行。`create_search_memory_tool` 调用同 namespace 的 store.search/asearch。
- 实际写入 `tools.py:271-337`；搜索 `:436-474`；动作与 namespace 参数 `:25-57`。
- https://github.com/langchain-ai/langmem/blob/48e3c11f5bb527282c7d5339c6a87a0b35abccfc/src/langmem/knowledge/tools.py#L271-L355
- https://github.com/langchain-ai/langmem/blob/48e3c11f5bb527282c7d5339c6a87a0b35abccfc/src/langmem/knowledge/tools.py#L436-L485

提示词优化控制流：

- `prompts/optimization.py:create_prompt_optimizer` 将 kind 分派到 gradient、metaprompt 或 prompt_memory；返回 Runnable。
- `prompts/gradient.py:GradientPromptOptimizer._process_input` 将 trajectories 与反馈整理成文本；`invoke/ainvoke` 在没有轨迹时返回旧 prompt。反思步骤有上限；`recommend.warrants_adjustment=False` 时也原样返回；否则 `_update_prompt/_aupdate_prompt` 让模型生成新的 prompt 字符串。
- 这条路径是基于轨迹和反馈的提示词改写，没有重新运行业务任务测量新旧 prompt 收益、留出集评测或权重训练。
- https://github.com/langchain-ai/langmem/blob/48e3c11f5bb527282c7d5339c6a87a0b35abccfc/src/langmem/prompts/optimization.py#L260-L268
- https://github.com/langchain-ai/langmem/blob/48e3c11f5bb527282c7d5339c6a87a0b35abccfc/src/langmem/prompts/gradient.py#L293-L399

真实跨任务演示：

- `examples/intro_videos/procedural_memory.ipynb` code cells 3-4 在 store 保存提示词并在 agent prompt 函数中读取；cell 8 用一次轨迹和“总是以 William 署名，会议提供 Zoom/Google Meet”反馈调用 optimizer；cell 10 把候选字符串 `store.put` 为新提示词；cells 11-12 再调用新任务。第二部分演示多提示词选择与更新。
- 示例使用打印输出，没有独立样本统计或回归门禁。旧的 `create_react_agent` 等示例 API 也不应直接当作本项目当前主编排规范。
- https://github.com/langchain-ai/langmem/blob/48e3c11f5bb527282c7d5339c6a87a0b35abccfc/examples/intro_videos/procedural_memory.ipynb

测试核验：

- `tests/test_docstring_examples.py:collect_docstring_tests` 扫描 src、README 和 docs 的 Python 示例；`test_docstring_example:239-297` 顺次 exec/await 示例。是否有断言取决于例子本身。
- 对已读的 prompt optimizer 示例，运行后打印新 prompt 而非评估新旧方案的未见任务效果。此测试 runner 和源码均不能作为“自动持续学习已被评测证明”的证据。
- https://github.com/langchain-ai/langmem/blob/48e3c11f5bb527282c7d5339c6a87a0b35abccfc/tests/test_docstring_examples.py#L183-L238
- https://github.com/langchain-ai/langmem/blob/48e3c11f5bb527282c7d5339c6a87a0b35abccfc/tests/test_docstring_examples.py#L239-L297

补充边界：`prompts/stateful.py:update_general` 也有模型认为该更新就直接 store.aput 新提示词的实现；它不是自带评测推广机制。应用仍需自行定义是否采用、版本审计、权限、并发写冲突及回滚。

## 3. OpenEvals：提供可执行评测，但不会自行修改记忆或发布提示词

控制流：

- `trajectory/match.py:create_trajectory_match_evaluator` 选择 strict/unordered/subset/superset scorer，标准化消息，然后交给 `_run_evaluator` 返回 score/feedback。
- `trajectory/strict.py:_scorer:20-76` 比较消息数量和 role、是否有 tool_calls、工具名与参数。工具调用在同一 assistant message 内通过 seen 数组寻找未使用匹配，不强制该 message 中工具顺序一致。
- 重要源码边界：该 `_scorer` 没有比较普通 message.content 或工具返回 content；名字 strict 和 docstring 中的 content 不能代替实际实现。trajectory_strict_match=True 不能证明最终账单金额、解释或 JSON 正确。
- https://github.com/langchain-ai/openevals/blob/9166120ee4e7daaf847b82dd6f18993777a5cc30/python/openevals/trajectory/match.py#L67-L104
- https://github.com/langchain-ai/openevals/blob/9166120ee4e7daaf847b82dd6f18993777a5cc30/python/openevals/trajectory/strict.py#L20-L76

测试：

- `python/tests/trajectory/test_trajectory.py:test_trajectory_match_strict_params:349-384` 明确同一工具参数 SF 与 San Francisco：exact=False，ignore=True；还覆盖消息数量、subset 和嵌套字段匹配器。它证明评测器的匹配语义，不证明某个业务 Agent 已改进。
- https://github.com/langchain-ai/openevals/blob/9166120ee4e7daaf847b82dd6f18993777a5cc30/python/tests/trajectory/test_trajectory.py#L349-L384

结构化结果评测：

- `json/match.py:_prepare_parameters:204-249` 对不在 rubric/exclude_keys 的字段直接与 reference 比较，缺字段记 0；`create_json_match_evaluator` 将 rubric 指定字段交给 LLM judge，其余字段用确定性比较。可以逐字段评分，也可 average/all 聚合。
- `tests/test_json.py:test_json_match_average:37-44` 有一个字段错返回 0.5；`test_json_match_all:59-66` 同输入返回 0。财务关键字段不应因为平均分很高就放行。
- `test_works_with_evaluate:615-625` 演示和 LangSmith client.evaluate 结合，断言有 score；不是模型升级后真实收益的业务实验。
- https://github.com/langchain-ai/openevals/blob/9166120ee4e7daaf847b82dd6f18993777a5cc30/python/openevals/json/match.py#L204-L249
- https://github.com/langchain-ai/openevals/blob/9166120ee4e7daaf847b82dd6f18993777a5cc30/python/tests/test_json.py#L37-L66
- https://github.com/langchain-ai/openevals/blob/9166120ee4e7daaf847b82dd6f18993777a5cc30/python/tests/test_json.py#L615-L625

## 对航运账单项目的建议

默认一次人工纠错只更新当前 task/bill revision。把反馈记录成带来源的事件；不在 edit Hook 中直接写全局 fee mapping、规则或共享 Skill。

跨任务推广应有明确动作与独立生命周期：

1. 用户主动选择沉淀，生成候选规则/Skill/prompt version，保留原反馈、适用主体、交易方/单据类型、旧新差异、提出者和证据。默认最小适用范围，不把一次例外归纳为普遍规则。
2. 用锁定输入和模型配置比较 baseline 与候选；将用于生成候选的反馈样本与留出/回归样本分开。金额、币种、AR/AP、误 UPDATE/CREATE、同名多行误合并、重复提交用确定性断言；语言表达可补 LLM judge。
3. 将关键错误设为独立门禁，建议关键错误零新增；不能用整体平均分掩盖金额、主体、币种或误更新退步。保留每条失败样本与差异。
4. 经过明确审核后才发布新的能力/规则版本；可回滚到上一有效版本。已经运行的任务固定依赖版本，版本迁移后重新校验并使受影响审批失效。

可对外准确表述：已实现人工复核和任务内纠错；可选实现有来源、可评测、需明确推广的跨任务记忆与提示词优化。不能仅因 profile 更新成功或 LLM 自评改善就称为“越用越聪明”或“经过验证的自动学习”。
