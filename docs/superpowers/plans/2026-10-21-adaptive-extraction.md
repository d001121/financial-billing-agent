# 单个提取 Skill 递进读取实施计划

> 执行方式：本会话按 executing-plans 顺序实施，不新增格式 Skill，不改发布过的历史任务。

**目标：** 在现有 document-extraction 内，由 Agent 选择补读方式，所有文件参与比较，最终仍输出题目合同。

**架构：** 保留既有接入、提取、证据和财务边界。接入按真实格式完成基础读取及必需 OCR；PDF 补读由提取 Skill 的原生绑定工具按需执行。SKILL.md 是任务入口，references 保存不同格式、跨文件核对和输出说明。无额外运行时或固定业务图。

**技术：** LangChain 1.4.6、Deep Agents 0.7.29 SkillsMiddleware、pypdf、官方社区 PDFPlumberLoader、现有覆盖/证据 Hook。

- [x] 1. 先写失败测试：OCR-only 接入不提前加入 PDF 全文/版式；按需补读保留 source_id、原页和哈希；指定 OCR 失败不被补读伪装成功。
  命令：`./backend/python.cmd -m pytest backend/skills/document-intake/tests/test_intake.py backend/skills/document-extraction/tests -q`。
- [x] 2. 最小实现：intake 增加兼容参数 pdf_text_mode；extraction 增加 supplement_pdf；宿主 read_document_sources 仅绑定任务材料并保存产物、失效旧校验。补读不重复 OCR。
  宿主测试覆盖任意材料越权、补读后重建全部 chunks、遗漏其他已接入文件仍不能完成。
- [x] 3. 重写现有 SKILL.md 的递进步骤；新增 references/reading-strategies.md、cross-file-review.md、output-contract.md。所有格式共用同一提取 schema，缺失为 null，冲突与失败分别记录。
- [ ] 4. 运行相应回归及依赖检查，CAS 发布新 Skill/专家配置；正常重启后用指定深圳容宇 EML 新建开发验证任务。核对全部来源、单笔50、原件编号、付款关系、币种歧义和原件定位，不回复人工中断、不审批。
- [x] 5. 更新 AGENT.md、研究及验收文档，报告真实结果和剩余限制。当前目录无 Git，不能虚构提交。

**最新状态：** skills v17/agents v8，document-extraction1.6.4，能力7e98a1650f2a80341eee。156项相关回归通过（2 warnings、29.87秒）。单提取Skill、原图读取、日期归属与warning/info不阻断已实现；1.6.3完整EML任务746914ee-4775-414e-acc4-68300058cba3以budget_exhausted结束，24模型/24工具，活跃732.93秒/观察墙钟815.56秒，最终3项断言失败（HBL主单角色、顶层证据投影、币种中断收尾）。1.6.4随后仅修复warning误阻断并发布，没有重置旧任务预算或重跑整单。第4项真实验收仍未完成；需要继续解决编号语义、调用效率与时延，不能把离线回归当整单成功。以下为前序阶段记录。

最终当前skills v16/agents v8、document-extraction1.6.3/human-review1.1.3，能力e6d88ea2ed7e8fcd6dde，服务PID42484。原图查看在同一个提取Skill中用原生多模态ToolMessage执行；155项相关回归通过。完整真实EML任务1f202de0-825c-4561-87cd-ad677234f311在1.6.2下：4来源/9块/1笔50，PDFtext/layout与原图读取、运输编号、证据/定位和仅币种中断均通过，但邮件Date误作账单日期导致1项断言失败。随后增加日期归属校验，真实定向回归日期为null、旧错误候选被拒；裸模型的另一个USD猜测由既有证据校验阻断。新版全流程尚未重跑，4项因此保持未完成；不把框架run success当完整原件验收通过。活跃558.64秒/观察墙钟649.83秒的时延还需优化。历史能力不迁移、未代答真实中断或审批。完整报告与范围见docs/acceptance.md。

4项进度：完整回归398项及4项子测试通过，pip check通过；配置skills13/agents6，能力d2bcb79a60b6e3bcaac2。正常Ctrl+C重启后21线程ID/状态一致，数据库/Redis健康。指定原EML验证任务d0a1b46e-8b96-4d05-9e24-240c4c9c22f8已启动，待真实结果及原文定位断言，不代答。

官方查证：Docs MCP /oss/python/deepagents/skills 的三级渐进披露、metadata.include_tools；API Reference SkillsMiddleware。原生组件提供读取和工具执行，不提供本项目财务字段范围、OCR完成范围与不可变来源合并规则；只补这些领域函数。PDFPlumberLoader 见官方 document_loaders 目录，API MCP 未收录该符号，已核对安装包源码与实际签名；langchain-community 0.4.2 已提示停止主动维护，当前锁定版本使用，不将其作为 Agent 编排层。
