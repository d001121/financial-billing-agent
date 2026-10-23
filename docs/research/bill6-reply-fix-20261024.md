# 账单6人工回复失败排查

2026-10-24，只读检查原账单与原生线程后修复宿主回复适配；未触发真实模型、OCR或账单恢复，未重启后端。

## 实际故障

账单6（ac7b55f1）的用户回复为“本次记账主体是TAR。”。初次材料处理已结束；失败发生在主体回复轮，原生 run 最终 success、检查点 next/tasks 均为空，业务为 incomplete/R1、主体仍空。框架运行结束不能代表人工修改成功。

1. `entity_from_reply` 的 ROLE 正则直接包含 TAR/SHA，使明确主体选择无法命中原有零模型快路径。conversational 回复转入原生模型循环。
2. `_role_is_explicit` 的 `ar\b` 只有右边界，错误匹配 TAR 后缀，允许模型附加用户未要求的 creditor/debtor 修改。
3. 模型首次工具调用漏 reply_id，原生参数校验正确返回错误；补齐后仍漏两项 operations 的 op。原工具签名仅为 list[dict]，未向模型披露子项结构，也未在原生参数层拒绝。human-review 返回两项 REVIEW_OPERATION，宿主写入不可恢复 decision_error。模型下一次只设置主体也被终止边界阻断。

本轮回复使用5次模型调用，全任务累计15次；不是持续运行的后台死循环。当前只看到已保存一项费用，未重新核对整个材料的提取准确率。原始快照保存在忽略目录 `backend/tests/reports/bill6-diagnosis/`。

## 最小修复

- 移除把 TAR/SHA 当作角色的规则；AR/AP 英文角色使用两侧 ASCII 标识符边界，保留中文相邻“是AR”的支持。选择主体不会授权模型修改交易双方。
- 将 operations 子项声明为原生 TypedDict，op 必填且枚举 set/delete/split；其余字段保留缺省语义，不推断 op、不补财务值。沿用 LangChain 原生 schema 错误回传与既有预算，使模型可以纠正格式，不提前写业务失败。
- human-review 财务算法和固定发布版本不变；不改历史账单、不清空或自动重放失败回复。

## 官方能力查证

操作：工具子项结构披露、参数验证与错误回传。

- Docs MCP：`/oss/python/langchain/tools` 与 `/oss/python/migrate/langchain-v1` 的工具错误章节。schema mismatch 已由框架处理，不能另写一套重试机制。
- Reference MCP：`langchain_core.tools.structured.StructuredTool`，args_schema/from_function；本项目 LangChain1.4.6、LangGraph1.2.16，沿用已有 `@tool`/原生 ToolNode。
- 本机 Codex `codex-rs/core/src/tools/handlers/mod.rs` 的 RespondToModel 错误语义同样将可纠正输入错误反馈给模型。业务上的“选择主体不等于修改交易双方”继续由既有宿主适配表达，框架不判断公司名称。

## 验证与生效范围

先新增复现：6 failed / 2 passed，失败点分别是 TAR/SHA 进入模型、主体名称识别以及缺 op/非法 op 导致 decision_error。修复后同组8 passed（8.13秒），相关既有回复检查11 passed（7.23秒），合计19项定向离线检查，存在既有 MCP beta 提示。模型HTTP均为 MockTransport、存储为隔离夹具；未跑全量测试。

代码需后端重载后生效。本轮未重载、未恢复账单6，不能声称该历史任务已恢复或线上验证通过。后续重新提交真实回复仍应沿原线程/新reply_id处理，保留原失败记录，不需要重做OCR。
