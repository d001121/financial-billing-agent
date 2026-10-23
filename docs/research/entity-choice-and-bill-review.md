# 会话确认主体与合并账单核对

2026-10-22，按两张标注截图实现。

提交页仅收材料、账单名称和可选要求，记账主体为空。先解析、提取并保存可查看结果，再在账单助手中询问记账公司；候选来自已保存费用和文档头的 issuer/recipient/creditor/debtor。去重后提供完整名称，不从邮箱、文件名猜公司，即使只有一家也不自动选择。用户点击候选只填入聊天草稿，发送才形成真实回复；可自填其他主体或暂缓。

主控提示词要求提取后再问。human-review 2.0.2 的 `entity_question` 仅构建业务问题；completion Hook 消费同 revision 校验和该任务固定 Skill，使用既有 ConversationReplies 的原生 interrupt/Command 路径兜底收束。人工回复仍由模型解释、`record_review_decision` 提案、`apply_revision` 事务提交、既有财务规则重算。无新 runner、表单中断或 AR/AP 判断算法。主动选择“修改记账主体”也显示可用候选。历史 Skill 没有该函数时维持历史行为，不迁移历史任务。

账单详情取消独立“材料与证据”侧栏，费用表下内嵌所选费用、置信度、提取原文、原件定位和修订入口；材料清单收在同一核对卡内。原文按来源/页码/锚点/内容合并重复展示，默认两处，其余可展开。费用原始引用和后端产物不变，点击具体字段仍用其真实引用定位。置信度中相同原文观察去重，仅改展示，不改评分。

## 官方能力依据与补充范围

- Docs MCP：LangChain human-in-the-loop 的 respond、frontend custom interrupt forms，LangGraph interrupts；API Reference MCP：`langgraph.types.interrupt`、`AgentMiddleware`。安装版本 LangChain 1.4.6 / LangGraph 1.2.16 / Agent Server 0.16.2，原生 `interrupt` 传 JSON 公司候选，`Command(resume=...)` 恢复；没有重写中断层。官方 middleware 提供工具与 after_agent 扩展点，公司的候选构造和“本次由谁记账”属于业务语义，最小实现放在既有 human-review Skill。
- 前端仍用 `@langchain/vue` 的 useStream 和原有回复 API，候选只是原生中断 payload 的 UI 投影，不建立新的会话状态系统。
- 编写、运行按 stop-that-shit change，页面按 design 与 ui-styling 的既有 token、层级、窄屏和可访问性指导实施。

## 验证与发布

- `backend/tests/test_conversation.py` 定向 20 passed、1 个现有 MCP beta warning（10.03 秒）。覆盖缺主体候选、所有已保存文档头、去重、单候选不自动选、无候选、当前 revision、历史无函数兼容、原生中断回复后 revision+1 / AP、主体不一致追问与原有回复幂等。
- Vue 类型与最终生产构建通过，2501 modules，Vite 1.03 秒，入口 index-D0ZuYs_R.js。
- 隔离 Agent Server + 合成模型/材料：先保存费用，再真实中断展示 Carrier/Client；浏览器选择 Client 并发送，金额保持 100，revision 1→2，AP，approval 为 null，历史仅一条。主动修改主体再出现真实候选。见 `backend/tests/reports/entity-choice-native.json`。夹具初次没有产生同 revision 校验，未打开中断；补齐夹具的真实核验步骤后重启验证通过，不当作生产失败或外部模型验证。
- 发布 skills 配置 v22 / human-review 2.0.2，能力 7f0d339560e7dc403618。正式服务正常 Ctrl+C 重启 PID39940→35060，33 线程 ID/status 一致，数据库和 Redis 健康。见 entity-choice-restart.json。发布脚本进程退出时的池线程提示已补显式 close，不重发已成功版本。
- 页面检查：提交页无主体输入且账单名称占完整一行；真实历史账单核对卡内显示置信度和原文，金额仍为 245.0000；390px 会话候选、输入框、发送按钮完整且页面无横向溢出。合成回复不触碰真实账单。

本轮不做全量测试、打包或真实 OCR/Qwen 整单重跑；不声明提取准确率或端到端时延已验收。截图与回执在 backend/tests/reports/entity-choice-*、bill-review-unified-*。

最终页面回执：bill-review-unified-ui.json 确认同卡展示、无独立侧栏、默认两处原文、245.0000保留且无页面错误。原件预览实际打开 PDF 第1/3页及 page:1/layout 锚点；该历史引用的唯一原文上下文未匹配，沿用原有“对应页展示、未自动标记”的诚实提示，不宣称精确坐标高亮。截图 entity-choice-source-preview.png。提交页账单名称与表单宽度均612.33px，主体输入数量0；390px页面无横向溢出。
