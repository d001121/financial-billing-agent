# Markdown 定位提取与文本 OCR 路径（2026-10-21）

## 已核对的参考

用户指定 Codex 会话 `01a15e87-95dc-7b20-a0a7-c2304a8cf1f2`（整理 AR/AP 费用信息）已通过桌面会话工具读取。实际顺序为标准库解包 EML、pypdf 提取两个 PDF 文字层、pypdfium2 渲染并查看两个 PDF 原页及嵌入 JPG，然后输出结果。记录 durationMs=130589，包含询问记账主体等待；不是 20 秒验收样例。会话未调用本项目指定 OCR、财务 Hook 或完整证据流程，不能与本项目端到端等价比较。参考会话中临时假定主体的回答不构成当前系统默认主体授权。

本轮复用的是一次清点、快速工具读取、紧凑上下文和减少模型往返的策略。用户已明确本项目没有多模态：PDF/图片由指定 OCR 识别，模型只读文本，不复刻参考会话中的图片查看路径。

本地 Codex 源码固定提交 `d138398cef7d49e46fe33f1d0ddbd2ca0ed16aa4`。`codex-rs/core/gpt-5.2-codex_prompt.md` 偏好 rg/rg --files；unified_exec 与 output-truncation 明示输出预算及截断。没有把命中一次或工具成功视为全文读完。具体读取边界见提取 Skill 的 references/markdown-reading.md。

用户 ZIP `pdf-ocr-md-3.4.0.zip` SHA256 为 `e91067e48fd675d2bd3be60268f817ffbf40e2fd960879a2f0a1028f0d8375be`。采用其按页/段落/表格组织 Markdown 的策略与来源记录，OCR 接本项目已有服务；未安装其 PaddleOCR/ONNX 等引擎，未宣称 deskew/unwarp 效果。原始说明保存在接入 Skill references/pdf-ocr-md-upstream.md。

## 当前实现

- 全格式先生成每来源 Markdown 和原文 map；PDF 保留指定 OCR 字段表、可用文字层及版式各自身份，Word/Excel 保留表格和内容锚点。结构化 OCR 不伪装逐字全文。
- 全文放原生 StateBackend `/materials/<source_id>.md`，模型消息只提供目录、覆盖块身份。原生 grep 定位，read_file 按行读；read_markdown_evidence 回读真实原文偏移并保存读取回执。搜索命中/eof 均不证明此前或整份已读，费用表仍逐行覆盖。
- 同一提取 Skill 的 read_document_sources 支持 text/layout/ocr。OCR 补读将指定原页切成单页 PDF（不渲染 PNG），图片按 frame，复用接入 Skill 的 OBS、指定 HTTP OCR、真实响应映射与存档。成功补读复用；失败保留错误，单页成功不洗掉先前多页失败。模型没有新版本原图/原页多模态工具；历史不可变能力内容保留。
- EML 根附件在有界线程池并发 IO/OCR，嵌套串行。一次提交仍检查全部来源，真实不同单据隔离，重复表示不加费用或置信度。
- 减少重复 schema、共享正文和证据返回；简单任务主控直接提取，专家按需。save(finalize=true)复用既有确定性核对，prepare_export使用原生return_direct；原有低置信度中断、证据和财务校验继续生效。

## 官方能力与最小缺口

查询 Docs MCP：LangChain tools 的 ToolRuntime/Command/ToolMessage；Deep Agents skills 的 pinned_skills、include_tools、StateBackend/原生文件工具。Reference MCP 成功核对 langgraph.prebuilt.ToolRuntime。安装组合为 LangChain1.4.6/Deep Agents0.7.29。原生框架继续负责 Agent、工具调度、Skill 渐进披露与状态更新。指定 orderChange 请求、响应 pointer、OBS 原页映射及财务证据不是通用框架协议，业务包只适配该实际缺口，没有增加 Agent runner、OCR 引擎或检索框架。

## 验证边界

本轮相关定向测试 16 passed、2 warnings、7.26秒，报告 backend/tests/reports/text-only-ocr-targeted.xml。覆盖单页 PDF OCR、真实页号及哈希、图片帧 OCR、失败保留、成功补读复用、Markdown 原文映射、原生 grep 回读及宿主文本输出。OCR/模型均为受控合成响应；这是测试耗时，**不是整单提取耗时**。按用户要求未做全量测试。

已CAS发布skills v18/agents v9、能力7cd94124068b95ff201e；正常重启后PID24616，数据库/Redis健康，25个线程状态一致。回执为text-only-ocr-publication.json及text-only-ocr-restart.json。另2项提示冻结/附件并发测试通过；本轮未重跑真实OCR。当前尚未用新版完整重跑指定 EML；20秒端到端目标和完整真实准确性仍待实测，不能由这些离线测试推导。
