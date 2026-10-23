# 账单7：会话决策、停止和重试收敛

日期：2026-10-24。用户授权同一账单真实联调，禁止全量测试和批量真实调用。本文区分离线回归、在线失败定位和修复后结果。

## 发现的根因与修复

1. 普通问题被旧 completion 中断覆盖。原账单主体已确定，但 `charge_002` 没有费用名和金额，其 AR/AP 提问仍抢占“是不是有一个费用是没用的”。现在本轮问题优先；旧问题保留为独立非阻塞待办，原生 `ask_user` 只用于本轮确有必要的询问。
2. `answer` 被提前当作终态提案。现在普通观察不占用修订提案，模型可以继续说明、读取证据或询问删除确认。当前消息结束有响应 ID 绑定，TaskOutcome 不再把普通回答送回整单核验循环。
3. 删除费用后旧待办仍悬挂。修订后重新读取当前校验，删除其依赖的费用会使相应 completion 问题解除；自定义问题保留。历史问题缺少字段元数据时，只在与当前确定性问题完全一致时补回描述字段。
4. 耗尽一次提取额度后，后续人工纠错永久被拒。累计计量不清零；明确的新消息、重试和继续获得有限的人工回合额度，主控、专家及真实 HTTP 派发共同计量。当前配置为每人工回合最多 6 次模型、16 次工具、720 秒活跃时间；专家仍受自身额度和主控预留约束。自动续跑不创建新额度，旧运行不能使用新人工回合额度。最终预算 Hook 与派发使用同一有效上限。
5. 失败重试或图已结束后使用空恢复命令。现在读取真实检查点：待执行节点按原检查点恢复；已结束图用普通 input 开启新回合；真实人工中断按实际 ID 恢复。同一请求身份的成功重放幂等，失败尝试保留历史。
6. 首次在线联调暴露旧回复编号的回执被复用。现在有活动回复时，其他回复编号返回明确工具错误及当前真实编号，不能用旧回执终结新请求。
7. 已保存账单的原生中断回复仍可重做提取。现在与普通聊天采用相同工具边界，允许读取证据、询问和通过 revision 修订；禁止用重新提取覆盖既有账单。尚无候选的初次处理中，保留保存首份候选的恢复路径。
8. `return_direct` 工具被拒绝时，错误曾可能被当作最终回答。现在无提案的错误回到原生模型节点，让模型在同一有限预算内修正；停止回合明确标记失败，保留非阻塞待办，允许显式重试。
9. 第二次在线确认已得到正确删除提案，但宿主仍等待模型生成结束语，弱模型反复调用工具后把预算耗尽，提案未提交。现在使用官方 `awrap_model_call` 的短路能力：合法提案出现后返回宿主消息，不再调用模型，由既有 after_agent 提交与重算。停止检查不会阻止已验证提案的确定性提交；同版本、同内容的失败请求可复用已保存提案，保留失败尝试和提案审计。

主控继续使用 LangChain create_agent / Deep Agents 官方装配、原生 todos、工具节点、interrupt、检查点与 call-limit。没有新增监督 Agent、固定财务 DAG、第二个 runner 或自动无限重试器，没有把原件重写为自然语言摘要。

## 官方依据与具体缺口

当前环境：LangChain 1.4.6、LangGraph 1.2.16、Deep Agents 0.7.30、SDK 0.4.8、Agent Server 0.16.2。没有升级依赖。

| 操作 | 本会话 Docs/API MCP 查证 | 原生组合与本项目最小缺口 |
| --- | --- | --- |
| 新会话、恢复和重试 | Docs `graph-api#input-to-invoke-or-stream`、`interrupts`；API `langgraph.types.Command`、`langgraph_sdk._async.runs.RunsClient.create` | 普通 input 与实际 interrupt resume 分开；项目 API 选择正确入口，不实现执行器。0.16.2 commands 对已结束线程的兼容处理继续保留。 |
| 工具失败后纠正 | Docs `thinking-in-langgraph#handle-errors-appropriately`；API `langchain_core.tools.structured.StructuredTool` | ToolException / error ToolMessage 返回模型；只修复 return_direct 提前终结这个组合缺口。 |
| 调用额度 | Docs LangChain middleware built-in call limits；API `langchain.agents.middleware.model_call_limit.ModelCallLimitMiddleware` | 原生 thread/run 安全网继续启用；跨主控、专家、人工回合的业务累计账本沿用项目既有条件写入，新增有限人工回合上限，统一派发与校验读取。 |
| 人工问答 | Docs dynamic interrupts；GitHub Deep Agents Code `ask_user.py` | 原生中断保留，项目只绑定真实回复、revision 和业务待办，不伪造已答复或批准。 |
| 合法提案收口 | Docs `middleware/custom` 的 Wrap-style hooks；API `AgentMiddleware.awrap_model_call` | 官方明确 handler 可调用零次，返回 AIMessage。项目短路多余模型结束语，既有事务提交仍执行；没有绕开版本、审批或证据检查。 |

已用 GitHub MCP 读取 `langchain-ai/deepagents` 固定提交 `edb9a78696e5232f3f5936dc752d3381796bc27f` 的 `libs/code/deepagents_code/ask_user.py`。该真实 Agent 明确区分 answered/cancelled/error，通过 interrupt 和 Command/ToolMessage 返回结果，不把错误伪装成回答。本项目参照其“回合与结果绑定、错误回到模型”的职责边界，未复制其 CLI 或替换现有服务。另核对本机 Codex 工具处理中的 RespondToModel 错误语义。

官方入口：

- https://docs.langchain.com/oss/python/langgraph/graph-api#input-to-invoke-or-stream
- https://docs.langchain.com/oss/python/langgraph/thinking-in-langgraph#handle-errors-appropriately
- https://docs.langchain.com/oss/python/langgraph/interrupts
- https://docs.langchain.com/oss/python/langchain/middleware/built-in
- https://reference.langchain.com/python/langgraph/types/Command
- https://github.com/langchain-ai/deepagents/blob/edb9a78696e5232f3f5936dc752d3381796bc27f/libs/code/deepagents_code/ask_user.py

## 验证记录

离线：使用项目便携解释器、隔离仓库和模拟模型 HTTP；不调用真实模型/OCR，不跑全项目测试。分阶段检查覆盖原生中断后普通问答、修订、旧待办、重复回执、失败重试、已结束图继续、有限人工预算、旧运行隔离、首份候选恢复及 return_direct 错误恢复。最终常驻会话31项通过（13.94秒，待办收口补充断言再单独通过1项）；既有会话55项中48项先通过，7项旧断言要求支付额外“结束语”调用，更新为新的少调用行为后7项通过（10.49秒），业务版本、金额、角色和审计断言保留。前端待办类型和紧凑提醒已通过 Vue 类型检查/生产构建（本次未重复构建未变更的前端）。

真实场景限定为既有账单7，task `bd57ca32-d64e-4f7e-b936-a745162ba466`，原线程 `01a169a6-16c4-7147-8c62-fe72014143e5`。联调前 R2，主体 TARGETING A INC，模型20/工具18/活跃126.626758秒。

首次在线定位 run `01a169c3-d4e6-74f9-a79d-f13e353b0b30`：旧回复回执错误引导模型调用导出、重做提取，6 次模型上限确实停止。模型累计20→26、工具18→24、活跃增加44.011122秒；没有新远程 OCR。候选曾被模型在同 revision 重写，不能将此失败轮称为正确完成；相关历史快照和原生消息均保留。随后补修回复编号隔离、已有账单修订边界及直接返回工具错误处理。

本机发现两份旧服务，其中一份请求2024但实际监听11308。确认无 busy 线程后正常停止，最终保留一个2024服务；检查点和原始材料保留。重载的初始化等待不属于模型活跃处理耗时。

## 同一账单真实闭环

| 阶段 | 原生 run | 真实结果 | 新模型 / 工具 | 活跃计量增量 |
| --- | --- | --- | --- | --- |
| 首次定位 | `01a169c3-d4e6-74f9-a79d-f13e353b0b30` | 旧回执导致跑偏，6次上限停止 | 6 / 6 | 44.011122秒 |
| 重新询问多余费用 | `01a169cf-e25f-740f-baa6-7569cf0bc916` | 自主读取现有记录，旧编号被拒后纠正，指出 HBL 无费用行，主动 ask_user 请求删除确认 | 4 / 3 | 18.059918秒 |
| 测试人工确认删除 | `01a169d0-bce7-7143-a4c3-9e90289bee13` | 得到只删除 charge_002 的合法提案，旧收口等待模型导致6次上限停止；明确 failed，提案保留 | 6 / 5 | 19.329539秒 |
| 同一失败请求重试 | `01a169d7-716f-74ee-9eba-b27d5445a2df` | 复用原 reply_id 和提案，实际提交 R3并重算，原生图结束 | **0 / 0** | 0.096550秒 |

人工干预是本次授权联调中的测试确认：只删除没有费用名和金额的费用候选，不批准整单，不补填缺失字段。既有账单沿用原线程和能力快照，没有新建第二条完整提取任务。

最终实际断言：

- R2→R3；仅保留 `charge_001`，`charge_002` 从 charges/records 删除，HBL 原始材料仍在。
- 主体仍为 TARGETING A INC。删除前后剩余记录的单据字段、交易方、费用字段、财务属性、债权人/债务人及来源/文档 ID 完全一致；金额50、历史记录的USD及AR没有被这次删除修改。
- 全部 sources、asset_ids、intake 与联调前相同；没有新接入或新远程 OCR HTTP 请求。
- 当前原生 `next=[]`、interrupts为空、active_depth=0，run_status=success，回复completed。原 charge_002 的待办为answered；没有再追问主体或已删除费用的AR/AP。
- 再发送同一成功请求返回同一 run/R3，不重复删除、不创建R4，也不调用模型。
- `status=completed_with_gaps`、`validation.ok=false`、`approval=null`。剩余硬错误为 charge_001 的 currency 缺少可回读证据；保留历史值不代表USD已被本轮证实。草稿导出200，只有1条 PENDING_REVIEW；正式导出422。

累计真实消耗：模型20→36（新增16）、工具18→32（新增14）、活跃126.626758→208.123886秒（新增81.497128秒）。16份原生模型usage回执合计输入561465、输出5846、总567311 tokens，其中输入缓存读取311296 tokens；这是回执用量，不是人民币费用，也不把缓存token视为免费。本次消耗含两次在线定位失败轮，不能当作普通账单的稳定性能；墙钟包含排查、测试、重载和人工等待，不能以81.50秒冒充端到端时延。

本机完整回执位于忽略目录 `backend/tests/reports/bill7-diagnosis/`：`task-before/state-before`、各阶段请求/响应、停止与最终快照、`verification.json`、草稿和正式导出响应。原始业务材料及完整模型对话没有上传 Git。

边界：真实验证覆盖本账单的自主判断→原生人工确认→失败停止→同请求重试→revision提交→导出门禁，未做全量、批量、其他格式、跨进程硬崩溃或数据库高并发验证，也未宣称总体准确率提高。旧原生todos仍保留初次提取计划（in_progress/pending），但不代表存在运行中的节点；本次未改写历史计划。旧提取issues还带有一条 ENTITY_UNRESOLVED 的info，实际主体已确认，该提示不是新的主体缺失事实；未静默迁移历史Skill版本或将其包装成全部通过。

## 2026-10-24 后续精简：多文件读取与核对

用户指出正常业务只需逐文件提取再对照。本阶段删除主控重复的中英文流程说明，简单提取、多文件核对及局部修改不再要求写todos或委派专家。主控save_document_extraction默认finalize=true，已有证据/金额/关联/历史/评分函数一次返回核验；分批暂存可显式false，专家默认仍只暂存。保存及reconcile回执可满足主控已见核验的结束检查，无需为prepare_export再跑一轮；之后写入仍使旧回执失效。真正漏做核验时仍将实际检查结果反馈主控一次。低分反馈中的Decimal原生序列化曾退化为Python repr，现仅将保存回执转为JSON兼容投影，不改变库内Decimal或原始证据。

操作查证：Docs MCP读取custom middleware的after_agent及wrap handler零/一次调用、tools的运行时注入说明；Reference MCP核对TodoListMiddleware(system_prompt, tool_description)、AgentMiddleware、InjectedToolArg、ToolCallRequest.override。安装组合LangChain1.4.6、LangGraph1.2.16、Deep Agents0.7.30不变。官方原生计划、工具循环、Skill加载与结束Hook可直接复用；最小业务适配仅默认保存核对及识别已存在的核验回执。对照本机Codex plan_spec.rs，计划工具本身不承担财务完成判定。提取Skill指令2.2.4/config40去掉例行prepare_export，旧release不改写，历史任务不迁移。

定向离线检查共13项分批通过（最后一项旧规划测试更新过时的非JSON委派契约、缺依据编号与固定100分断言后单独通过）。两个文件只需一次read_materials、一次save和一次答复，模拟HTTP计数3；包含缺主体原生中断、主体已给直接结束、不同单据字段隔离、缺币种保持null及金额矛盾保留硬错误。旧规划/可选委派、未校验写入失效、漏校验反馈和专家暂存仍有覆盖。全部使用隔离仓库与模拟HTTP，无真实模型/OCR、全量测试或线上账单修改；3次是合成控制流结果，不是线上性能或准确率结论。后端尚未重载。
