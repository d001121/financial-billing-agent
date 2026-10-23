# 无模板海外材料：提取与融合支持度

日期：2026-10-21。本文记录本轮已实现的领域优化及验证边界。实现包为 `document-extraction 1.3.0`、`evidence-linking 1.2.0`、`billing-reconciliation 1.1.0`、`billing-confidence 2.0.0`。历史任务继续使用固定能力，不套用新规则重算。

本轮skills已通过CAS发布v6，能力快照 `0dd7d9b036a29571747e`，见[发布记录](../../backend/tests/reports/global-confidence-publication.json)。最终全量为 **353 passed、43 warnings、4 subtests passed，220.45秒**，见[文本报告](../../backend/tests/reports/global-confidence-pytest.txt)及[XML](../../backend/tests/reports/global-confidence-pytest.xml)。新增在线任务与浏览器的实际结果单列于§6，离线数量不代替这些集成证据。

## 1. 文章来源与取舍

用户提供的[FineReport文章](https://www.finereport.com/blog/article/6909d294d2527e0eb718bb7b)标题为《ai单据正确率怎么提升？企业数字化运营优化新策略》，页面标注发表于2025-11-04 18:16:52。本轮HTTP抓取200，副本保存于 `backend/.build/research/finereport-6909d294.html` 与同名txt；正文副本SHA256为 `334B52DAE0F48D5B549C496EBB5E19B9B55159E6A20AFD261355210DA364A2A2`。

文章提出OCR与语义提取结合、数据清洗标准化、业务规则校验、误识/漏识/人工干预监控及持续反馈。它没有提供融合公式、校准数据或可复现实验；文尾声明内容由大模型按关键词生成，不承诺真实、准确或完整。匿名案例的92%、96%、98%等数字不作为本项目效果依据。

| 文章建议 | 本项目采用方式 | 不采用或保留的边界 |
| --- | --- | --- |
| 数据标准化 | 统一输出语义、规范金额、ISO币种及来源契约，同时保留原文 | 不要求供应商模板，不按国家、语言或港口猜金额格式 |
| OCR与NLP融合 | 指定OCR保留原响应，原生Agent形成有出处的语义候选，确定性函数回读 | 模型自报分或多模型同意不替代证据；结构化OCR不冒充逐字原件 |
| 业务规则校验 | 所属Skill核对数量单价、分单据/币种总额、费用角色、主体和更新语义 | 不跨币种相加，不为配平改原金额，不把差异当更新授权 |
| 模板归类、减少冷门样本干扰 | 按业务问题和材料家族整理回归样例 | 不过滤无模板或长尾材料，不复制固定坐标模板抽取 |
| 监控与反馈 | 页面解释来源、候选和核验不足，人工修订进入revision体系 | 本轮未新增运营看板、模型训练或自动共享规则发布；独立金标及分层指标仍需验证 |
| PDCA | 复用明确选择、候选评测、人工发布与回滚 | 一次纠错只影响本任务，不静默修改全局Skill |

## 2. 官方复用与领域缺口

本轮先经LangChain Docs MCP读取structured-output与Skills用法，API Reference MCP核对 `langchain.agents.structured_output.ToolStrategy`、`deepagents.SkillsMiddleware`；确定性评测另核对LangSmith code-evaluator与 `EvaluationResult`。安装组合仍为LangChain 1.4.6、Deep Agents 0.7.29、LangSmith 0.14.11。

原生Pydantic/ToolStrategy负责类型、schema和结构修复，SkillsMiddleware负责发现、披露和工具执行，通用评测接口接受业务评分函数。这些能力不定义航运账单的国际数字歧义、字段归属、折扣规范化或相关证据权重。本轮只补领域职责，不新增Agent循环、Skill runner、Hook运行时或模型评委；原生编排、统一Hook、共享预算和审批路径沿用现有组合，评分本身没有模型/OCR请求。

官方依据：

- https://docs.langchain.com/oss/python/langchain/structured-output
- https://reference.langchain.com/python/langchain/agents/structured_output/ToolStrategy
- https://docs.langchain.com/oss/python/deepagents/skills
- https://reference.langchain.com/python/deepagents/middleware/skills/SkillsMiddleware
- https://docs.langchain.com/langsmith/code-evaluator-sdk
- https://docs.python.org/3/library/decimal.html

## 3. 无模板提取与唯一规则归属

| 所属包 | 当前职责 |
| --- | --- |
| `document-extraction 1.3.0` | 原生schema声明 `raw_amount/raw_currency/raw_quantity/raw_unit_price`；缺值为null，保留原始费用名，数量/单价独立归因 |
| `evidence-linking 1.2.0` | 唯一原文数字/币种解释及字段支持实现，保存真实偏移、原文、候选、冲突和歧义；预览复用同一解析 |
| `billing-reconciliation 1.1.0` | 唯一金额计算、角色规范化及Decimal校验，向当前revision提供 `normalized_charges` 事实，不复制原文格式解析 |
| `billing-confidence 2.0.0` | 消费当前证据和财务事实，分组评分并解释不足；不重解析原文或计算乘法 |

原文数字支持点/逗号小数与分组、空格/NBSP/窄空格、撇号、合法印度分组、全角与阿拉伯数字、明确阿拉伯小数/分组符、括号负数和Unicode负号。保留原文及任意十进制精度，不假定所有币种仅两位小数。畸形分组、单号后缀或OCR字母数字混淆不做静默局部修复。

| 原文示例 | 行为 |
| --- | --- |
| `1.234,56`、`1 234,56` | 唯一金额归属时可支持1234.56，保留原文与偏移 |
| `1,23,456.78` | 合法印度分组可支持123456.78 |
| `١٬٢٣٤٫٥٦` | 明确阿拉伯分隔符可支持1234.56 |
| `(50.00)` | 保留负号语义，可支持-50；不据此机械反转AR/AP |
| 单独 `1,234` 或 `1.234` | 保留1234与1.234候选；模型所选值和算术配平不能消除歧义 |
| `0.125` | 前导零分组不成为另一种合法读法，保留正常小数解释 |

币种支持完整ISO代码、明确限定符号及ISO数据集的唯一官方全名，例如US$、CA$、€、US Dollar、Canadian Dollar，并有有限复数规则。本地名仅明确支持人民币、欧元、日元、美元、加元、澳元、港元、英镑、Chinese Yuan、Japanese Yen，不宣称覆盖所有语言。单独 `$`、`¥/￥`、`kr`、`Rs`、`C$` 等仍有歧义，单号内字母不充当币种证据。同单据独立引用的币种表头可供支持，不借用无关附件或另一总额的引用。

合法费用可没有单号、数量或单价，缺值保持null，不为凑算式制造操作数。跨页仍按逻辑单据、列语义及全部片段来源重建，重复表头、承前转后和总计不新增费用。

## 4. 三组融合算法

这是可解释业务支持度，`calibrated=false`，并非统计正确率：

`S = 70 × (0.45A + 0.35C + 0.20N) + 20 × max(0.5L, T) + 10V`

| 变量 | 当前取值与约束 |
| --- | --- |
| A/C/N | 金额、明确币种、原始费用名当前来源支持；只有 `supported` 为1，其余为0。回读和数值合法性不重复计分 |
| L | 数量、单价、金额均有不同物理token支持，当前原金额校验通过且财务Skill判定行算术通过时为1，否则0 |
| T | 当前逻辑单据/币种范围只有一个适用总额，索引、金额、币种绑定当前证据，回读及金额核对通过且总额token不同于各费用金额token时为1，否则0 |
| V | 当前覆盖校验通过为1，否则0；证明范围有处理去向，不证明没有语义漏提 |

字段来源70、相关一致性20、覆盖10。L最多贡献10分、T最多20分，取最大而不相加，不把一张单据的相关观察当独立概率。默认高分90、中分65，缺检查不重新归一化；任务取费用最低分，不用平均分掩盖弱项。权重和阈值没有按真实金标拟合。

单号支持仍展示，不计核心权重。来源充分但没有操作数/总额的费用为80分、建议复核；有来源行算术且无总额可到90；有不同位置总额可到100而无需单号或操作数。不同位置不等于统计独立。复制附件、同一OCR的多轮解释、重复引用和多模型票数都没有数量奖励；本轮未实现近重复材料的统计独立性分类器。

`source_support_v2` 绑定当前revision、候选值、费用ID、已核验引用及真实偏移。重复hash/anchor/token去重，同内容不同真实单元格仍保留各自锚点。显式矛盾不能被另一个恰好匹配的引用掩盖。旧协议、过期事实或无唯一位置时不可用，不回退到旧英文解析。财务规范化事实也须来自通过的当前金额校验并绑定输入/输出值；明确discount角色的50规范化为-50由财务唯一函数解释，评分器不自行改符号。

## 5. 评分与放行分开

已提供的金额、币种和费用名只有来源 `supported` 才能通过evidence Hook。`unsupported/unavailable`产生 `FIELD_VALUE_UNSUPPORTED`，数字格式、币种或重复位置歧义产生 `FIELD_VALUE_AMBIGUOUS`。只引用数量、复制匹配值或仅quote可回读不能代替字段支持。缺值仍交既有schema/财务门禁，不新增单号/数量/单价模板要求。

缺总额只得不到支持；显式引用与声明金额/币种矛盾仍是 `TOTAL_VALUE_UNSUPPORTED` 硬错误。这些错误与schema、覆盖、方向、冲突、revision、审批、能力和预算统一生效；批准及正式导出返回422，而非仅界面警告。高分不能抵消硬错误，评分不自动审批或记账。

`review_route`为 `quick_confirm/review_suggested/blocked`。高分且门禁通过仍须用户显式确认；修订生成新revision并使旧审批失效。历史任务和发布快照不被新规则改写。

## 6. 界面与验证

面板沿用布局与tokens，展示后端数量单价/原文总额核验及不可用原因、字段原文和候选。新 `signals/observations/review_route/fusion` 为可选契约，兼容保存的v1结果；前端不复制金额或评分算法，不直接展示内部融合实现术语。

本轮 `npm.cmd run build`（Vue/TypeScript及Vite生产构建）退出0。Vue SSR固定数据验证通过，覆盖v1、新核验、缺少依据及字符串/对象候选。随后在真实浏览器验证本轮v2的100分欧洲费用、原文块定位、缺操作数解释和24分歧义待复核；前端错误日志为空，记录在 `backend/tests/reports/global-confidence-ui.json`。旧v5浏览器闭环保留历史身份。

[合成差分报告](../../backend/tests/reports/global-confidence-comparison.json)包含9个显式已知答案场景，基线为v5快照 `3eb8bfbc62c9d4f41004`，候选为本轮实现，模型/OCR调用0。无关宿主门禁使用固定通过fixture，因此它是领域回归而非完整在线效果：

| 合成场景 | 旧策略 | 本轮策略 |
| --- | --- | --- |
| 普通USD | 100分，通过 | 100分，通过 |
| 欧洲分隔符、窄空格、印度分组、阿拉伯数字、括号负数，共5例 | 各15分，总额来源误拦 | 各100分，来源/金额校验通过 |
| 歧义 `1,234` | 100分，可快捷确认 | 48.5分，歧义阻断 |
| 未从原文取得的数量/单价 | 95分，可快捷确认 | 80分，建议复核，不奖励内部配平 |
| 总额复用费用金额token | 100分 | 90分，无总额奖励；来源行算术仍可得10分 |

这些样例参与本轮设计与回归选择，不能当独立金标、整体正确率提升或校准结果；单次纯函数耗时也不代表端到端时延或P50/P95。

另有真实Qwen合成端到端验证（`global-confidence-online.json`）：法英混合欧洲格式邮件正确提取两条CREATE/AP，1234.56和65.44 EUR，原文总额1300且没有单号/数量/单价，支持度100、未审批；21模型/18工具、活跃365.668秒。`$1,234`保留raw和null金额/币种，PENDING_REVIEW、24分，实际批准/正式导出均422；19模型/16工具、活跃325.139秒。两次run均success，模型关闭思考，无OCR；这些为明确合成的功能回归，不是独立测量。时延仍高，本轮不声称提速。

全部14个旧任务对象哈希与2146个旧快照文件逐项未变；新能力51文件独立发布，无历史迁移/续跑/代答，见 `global-confidence-history.json`。独立真实海外文档家族、字段/整单正确率、漏提/重复、金额币种关键错误、高分错误率及分层阈值校准仍需人工标签和独立评测。真实长PDF/跨页性能、首结果时延、峰值内存及生产强恢复继续保留原验收边界。
