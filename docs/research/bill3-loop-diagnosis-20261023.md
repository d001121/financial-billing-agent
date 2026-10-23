# 账单3：材料、委派与停止边界排查

日期：2026-10-23。范围：只读现有任务、原件、原生检查点和代码；离线回放固定版本 Skill。没有调用真实模型/OCR，没有重跑任务、增加预算、改业务数据或启停服务；未跑全量测试。本次只增加研究记录与诊断快照。

任务 `1976a08b-a4eb-48d6-97f6-bea387245af8`，原生线程 `01a168d7-b3cb-74c5-9e88-17258382b901`，R1，能力 `d8cb85b69f817092c6e4`，skills配置v37，runtime v7。实际模型为 `qwen3.7-flash`，不是 AGENT.md 历史段落中的 qwen3.8-max；当前 .env 与实际回执一致。不能把 Codex 模型上的提示效果直接当作当前模型已验证效果。

## 结论

这次不是材料没有金额或币种。最初两笔候选的金额和币种引用均正确，后续纠错反而破坏引用；宿主没有把明确的停止条件转换成原生控制流。暂不需要增加常驻监督模型，应先修材料表格表示、专家权限与任务边界、保存校验及确定性退出。监督模型会新增调用，并不能替代硬停止。

## 已核实事实

- 一张图片、两条费用。原图表头是 `Base / Rate / Curr / Amount / R.O.E. / Curr / Amount`，没有 quantity 表头。主控委派中却写成 `Qty: c(1)`、`Qty: 11c(实际应为1)`，并要求专家判断数量和单价何者可信。这是没有原文依据的列语义和数量假设，触发了不必要委派。
- 接入有一个远程OCR结构化块（1431字符）和一个本地OCR文本块（955字符）。模型读到141行、5161字符Markdown，`truncated=false`，金额、USD、日期、单号及对应引用都在。没有证据表明核心字段丢失或截断。
- 但本地文字是一行一个文本片段，列/行几何关系没有传给模型；远程结构字段含大量空项，并与本地文字重复。原件可见的表格被线性化，使 Base 容易被错误解释为数量。应保留可用的几何/表头/行列关系；不能由代码猜出数量或补造字段。
- 本次远程OCR缓存命中，总耗时0.104951秒，HTTP为0；接入工具整体7.039秒。整体活跃133.267秒；主控8次、billing-specialist16次模型调用，共24次，随后下一次请求被预算阻止。25条模型轮回执含最后的错误，不等于25次成功模型调用。
- 模型回执累计input tokens 442363（其中cache_read 338432）、output tokens 13069；这是各轮累计输入，不能据此直接计算费用。955字符的本地正文之外，Skills、工具参数及反复生成的整单候选占据了很多上下文；专家单轮输入最高24686 tokens。

## 专家检查点给出的因果链

专家消息已从 SQLite 以 `mode=ro` 读取对应子图最新检查点，不再只依赖父图中保留的专家总结。

1. 主控已读材料，却在保存候选前委派 billing-specialist；专家 `read_task_context` 得到空charges/records。
2. 专家把HTTP产物路径交给原生 `read_file`，失败；随后glob无结果；调用OCR补读又因没有document-intake能力失败。之后 `read_materials` 一次就读到完整材料。
3. 两次单独write_todos后，调用不存在的 `write_document_extraction`，失败，再改为真实保存工具。
4. 首次保存两条费用，金额/币种引用都正确。日期证据仅写在documents中，而校验要求每条charge的document_date引用，因此返回两条BILL_DATE_EVIDENCE_REQUIRED。
5. 专家只补charge-1日期，charge-2仍报错；接着原样重复两次。没有修复回执指定的charge-2。
6. 专家把两行的金额、币种、日期等引用改成各自费用名称ref，消耗第二轮额度并覆盖之前正确引用。此保存默认finalize=false，仅运行提取校验，未立即对金额/币种执行字段支持校验。
7. 专家随后提出正确的两行引用，已被两轮限制挡住。最后标记todos全部完成，返回status=done、saved=true和“未发现具体差异”；该总结没有准确表达最后修复未保存及证据仍有问题。
8. 主控收到总结后没有先读取已保存候选，继续重新抄写整单保存，仍被挡住；prepare_export得到completed_with_gaps后又保存一次，最后共享额度耗尽。主体询问位于after_agent，模型始终调用工具，直到预算异常，未走到该收尾入口。

## 代码问题与离线验证

| 问题 | 代码/回放证据 | 影响 |
| --- | --- | --- |
| 拦截只返回错误，不转换执行状态 | middleware/dispatch.py 的PolicyDenied分支返回ToolMessage；同一分支未记录attempts失败 | 相同失败可继续消耗模型调用，5次业务保存被阻止仍未进入待复核 |
| 无进展仅按完整候选hash判断 | tools/skill_bindings.py:425起 | 改坏引用也成为“新候选”，不能证明业务进展 |
| 先保存，再可选完整校验 | save_document_extraction默认finalize=false；专家无财务能力 | 本可支持的金额/币种引用退化后仍覆盖已存结果 |
| 错层参数被静默忽略 | 专家把replace放在result内；ExtractionResult默认忽略未知字段 | 模型预期与真实合并行为不一致，反馈未提示参数错误 |
| 专家权限和角色冲突 | billing-specialist提示只给建议/saved=false，但暴露document-extraction保存工具和通用提取Skill | 核验变成再次提取、写入和反复修复 |
| 各图运行额度独立 | 主控、专家均装配相同ModelCallLimitMiddleware；共享HTTP计量另计 | 专家能用16次，主控8次后共享24耗尽，未保留统一收尾空间 |
| 完成后的重入 | prepare_export在codex模式不是return_direct；TaskOutcome也可jump_to=model | 最终核验结果仍可启动新修复，停止条件需要贯穿所有返回模型的入口 |

固定版本、只在内存回放专家第18/20/26/28条消息中的候选（0模型、0OCR、0任务写入）：首次两行amount/currency均supported；第26条改坏后均unsupported；第28条正确修复均恢复supported且无日期证据错误，但在线时该候选已经被上限拒绝。证明“原文缺字段”不足以解释本次失败。单独回放不代表端到端修复通过。

## 诊断阶段的建议顺序

以下为当时建议。本轮经用户确认实施退出、证据保护、专家职责和共享预算四项，见[四项收尾记录](loop-controls-20261023.md)。未实施模型重写材料。

1. 在已有middleware及原生图边界，把无进展/纠错到限转换成结构化停止原因；下一次模型调用前原生jump_to=end。子Agent返回blocked和真实产物摘要；主控确定性保存当前结果并进入现有原生待复核/待主体中断。同步约束after_agent的返回模型入口，避免结束后重开循环；保留明确人类新revision的恢复。
2. 保存时对受影响的金额/币种/证据执行现有便宜Hook。相同原件、无新增证据的修复不能静默破坏已有可核验证据；候选保留在修复记录中，给出具体字段反馈。真实新证据冲突应保留双方并进入复核。
3. billing-specialist保持只读核验，使用明确候选、疑点和真实引用；主控保存。复杂材料仍可委派document-specialist。单图两行且必需字段已齐时直接处理，可选数量歧义留空并说明，不升级成整单重提取。
4. 修正参数错层反馈；日期等单据级字段在明确document_id/source绑定下复用实际证据，或一次批量提示受影响行，不要求模型逐行重复整单。工具/API URL明确区分，未授权能力不作为可用路径误导专家。
5. 改善图片Markdown的表格版式信息，减少空结构项和重复表示；始终保留完整原始响应和引用。只有坐标关系明确时分组，不用金额关系反推数量，不按样本表头硬编码财务判断。
6. 专家额度按共享剩余量和任务复杂度缩小，并保留主控收尾空间；模型/工具/活跃时间硬上限继续保留。简单样例可把4–6次模型调用作为优化目标，必须离线计数回归和用户授权的单例在线测量后再报告实际时延，不能保证固定秒数。

## 官方参考与适用边界

- OpenAI Codex prompting guide（本次实际HTTP 200读取）：https://developers.openai.com/cookbook/examples/gpt-5/codex_prompting_guide 。可借鉴的是：无进展时结束、简单任务少用计划、批量独立工具、避免反复微小修改。此页不能证明Codex桌面内部存在一个专门负责中断的监督Agent，也不能证明Qwen可直接取得相同性能。
- Docs MCP实际读取 Python custom middleware：https://docs.langchain.com/oss/python/langchain/middleware/custom 。原生jump_to=end进入结束/after_agent链；不是返回一句错误文字就会退出。
- Docs MCP与Reference MCP实际核对 ModelCallLimitMiddleware：https://reference.langchain.com/python/langchain/agents/middleware/model_call_limit/ModelCallLimitMiddleware ，支持thread_limit/run_limit/exit_behavior。当前安装LangChain1.4.6、LangGraph1.2.16、DeepAgents0.7.30、SDK0.4.8；同时核对安装源码。任务共享计量保留，不另建runner或队列。

诊断快照：backend/tests/reports/bill3-{task,state,trace,expert-messages}-readonly.json。快照是业务原始材料与轨迹，仅供本地核查。
