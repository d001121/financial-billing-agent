# 业务 Skill 与统一 Hook 设计

更新日期：2026-10-21。本文补充 [implementation.md](implementation.md)，开发约定以 [AGENT.md](../AGENT.md) 为准。八个业务包、独立入口与十一类 Hook 已有实现；本文同时保留完整设计合同和尚待验收的边界。

逐项实施、验证和交付统一按 [最终开发计划](superpowers/plans/2026-10-21-final-development-plan.md)；本文件维护业务包与Hook合同。

## 1. 核心边界

项目由通用 Agent 宿主、可插拔业务 Skills、统一管理的 Hooks 和 Vue 工作台组成。业务能力通过 Skill 包挂载；主控依据目标、已加载能力、工具结果和人工反馈做 Plan，不在后端写死“先解析、再记账”的业务流程。

- **Skill 产出业务结果**：文档解析/OCR、跨页重建、费用提取、财务规则、证据关联、人工修改影响、题目 JSON 导出及反馈改进，全部归对应 Skill。
- **Hook 检查与拦截**：结构、金额、证据、覆盖、匹配、revision、审批、工具启用和预算各自独立，由同一管理入口装配、执行和记录。
- **宿主提供通用能力**：官方 Agent/middleware、Skill 工具绑定与执行 backend 配置、模型、MCP、文件与记录存储、版本/控制、HTTP及通用 UI。宿主不包含特定费用名称、匹配优先级、AR/AP算法或账单字段判定。

所有智能体相关自写代码先执行 [AGENT.md](../AGENT.md) §3.5 的铁律：先查LangChain MCP，官方已有能力直接复用，只有查证缺少该项具体能力才允许补最小实现；Hook和业务Skill脚本没有豁免。下文完整职责仍按实际代码和验收证据逐项判断，目录存在不代表全部场景已通过。必要业务代码位于包内 `scripts/`，随业务版本迁移；不能只放说明性的SKILL.md，实际实现仍藏在backend。

当前八包均有 `SKILL.md/references/scripts/requirements.txt/tests`，包内 `scripts/skill.py` 提供业务函数及 `--input/--output`/标准输入输出入口；`backend/tests/test_skill_cli.py` 已覆盖项目外调用、结构化拒绝和退出状态。`backend/agents/factory.py` 通过 `StateBackend`、`FilesystemMiddleware` 与 `SkillsMiddleware(tools=...)` 装配原生文件/Skill 工具，未启用 shell `execute`。原生读取后披露并执行业务函数、真实本地 stdio MCP、热禁用与重试派发检查已有测试，不能外推为任意宿主或 sandbox 均已验证。

此前Office批次完整回归为 **234 passed、43 warnings、4 subtests passed，151.92秒**，报告为 `backend/tests/reports/office-confidence-pytest.txt`/`office-confidence-pytest.xml`；SQLite 58个必需基础conformance作为其中1项测试执行，不另加总。该报告不覆盖后续海外提取与v2评分变更。本轮前端类型/生产构建及v1/v2固定数据SSR呈现已验证，9个显式合成差分见 `backend/tests/reports/global-confidence-comparison.json`，不冒充独立金标、在线模型或真实浏览器验收。实际范围见 [acceptance.md](acceptance.md) 及[海外融合研究](research/global-extraction-confidence.md)。包内references保留各版本的验证记录；本轮暂不制作交付包或进行移机验收。

本轮最终全量为 **353 passed、43 warnings、4 subtests passed，220.45秒**，报告为 `backend/tests/reports/global-confidence-pytest.txt`/`global-confidence-pytest.xml`。skills经CAS发布v6，能力快照 `0dd7d9b036a29571747e`，见 `global-confidence-publication.json`；历史任务未迁移。离线回归不等同于新增在线任务或浏览器联调通过。

## 2. 严格遵循的 Skill 格式

LangChain Deep Agents 采用 Agent Skills 标准。标准要求目录内的 `SKILL.md`；`references/`、`scripts/`、`assets/` 是标准约定的可选资源目录。本项目按用户要求进一步规定：**每个业务 Skill 必须同时提供 SKILL.md、references/ 和 scripts/**，且内容实际被引用/调用，不建立空壳目录充数。

```text
skills/<skill-name>/
├─ SKILL.md                 # 触发场景、输入输出、操作说明、资源与脚本入口
├─ references/              # 详细规则、格式、契约、错误及适用范围
├─ scripts/                 # 可独立执行的确定性业务实现
├─ assets/                  # 按需：JSON Schema、映射、模板和小型示例
├─ tests/                   # 按需：随包迁移的独立用例
└─ requirements.txt         # 按需：包依赖；安装仍由宿主统一锁定
```

### 2.1 SKILL.md

使用 YAML frontmatter，`name` 与目录名一致，为1–64字符的小写字母、数字和连字符；`description` 必填，说明“做什么”和“何时使用”，不超过1024字符。需要时使用标准的 `license/compatibility/metadata`；自定义版本等属性放在 metadata，不发明一套顶层 Skill 格式。

下面是编写格式示例，不代表该 Skill 已存在或入口已经实现：

```markdown
---
name: billing-reconciliation
description: 对航运费用进行标准化、已有账单匹配、增量修改及AR/AP判断；在需要核对新材料与已有账单时使用。
compatibility: Requires Python and the dependencies listed in requirements.txt; accepts JSON input and produces JSON output.
metadata:
  version: "1.0.0"
  include_tools: reconcile_charges validate_amounts
---

# 账单核对

## 输入与输出
读取任务显式指定的记账主体、费用候选、证据引用和已有账单。
输出候选操作、变更差异、来源及问题，不把候选视为已执行记账。

## 执行
1. 按需读取 [匹配与更新规则](references/matching-and-update.md)。
2. 本宿主通过官方Skill工具绑定调用 scripts/reconcile.py 中的 reconcile_charges；
   validate_amounts调用scripts/check_amounts.py中的同一校验函数。
   具备shell执行backend的宿主也可通过原生execute运行同一实现的CLI：
   python scripts/reconcile.py --input input.json --output output.json
3. 核对脚本退出码与结构化结果；不以工具消息成功代替校验通过。
4. 存在歧义时返回问题和受影响范围，请主控补充信息或安排复核。

## 资源
- [输入输出契约](references/io-contract.md)：首次接入或字段不明时读取。
- [匹配与更新规则](references/matching-and-update.md)：处理标准化、匹配和局部更新时读取。
- scripts/check_amounts.py：供金额Hook及离线用例调用的唯一金额校验实现。
```

`metadata.include_tools` 是 **Deep Agents 扩展**，文档要求 `deepagents>=0.7.22`；值使用空格分隔字符串，不是 YAML 列表。它负责工具披露，不等于脚本注册或调用授权；也不能与实验性 `allowed-tools` 混为一谈。其他平台可忽略该扩展，仍依照正文的脚本入口使用业务包。

本方案的 `pinned_skills` 另要求 `deepagents>=0.7.23`。pin会在下一模型调用前插入内容快照；未知或不可读项会跳过，消费后输入键清空。因此须检查真正读入的内容和工具披露，不能把字段已提交当作成功。最低版本仍须与整套依赖组合和便携运行实际验证。

SKILL.md 保持短小，详细规则放 references；每个引用说明内容和何时读取，路径相对包根目录，避免多层引用链。assets保存可机器读取的schema/映射；references说明其含义及适用条件。

### 2.2 包内脚本与移植契约

- 脚本提供可调用函数和复用该函数的独立入口，输入/输出为明确 JSON 或文件引用；标准输出与错误日志分离，退出码和结果字段共同表达失败。工具入口、CLI和Hook不能各复制一份业务实现。
- `--input/--output` 和产物信封属于**项目移植约定**，不是 LangChain 官方脚本协议。
- 精确金额、匹配、证据解析等实际算法在包内实现；不得由LLM临时生成代码替代经过验证的脚本。
- 不反向导入 backend、frontend 或项目 hooks，不引用开发机路径；资源相对自身文件/包根目录定位，不依赖调用者当前工作目录。
- 记账主体、候选旧账单、资源位置和服务配置由输入/宿主注入；不绑定某个GaussDB表、Redis键、Codex目录或默认公司。
- 包声明依赖、工具与外部条件。当前宿主统一安装到 bishi1 并锁定；换平台由目标宿主安装依赖，不能声称目录可拷贝就等于任意平台零配置运行。
- 跨包通过产物契约与引用衔接；必需共享库必须声明为可安装依赖并随包说明，不能隐式导入同仓库其他私有目录。

## 3. 业务包与归属

| Skill | references 的主要内容 | scripts 的职责 |
| --- | --- | --- |
| `document-intake` | EML/MIME、各格式读取、题目OCR、转换与错误 | 递归清点、格式库适配、PDF切片/原页映射、OCR请求与原响应产物 |
| `document-extraction` | 长材料分块、逻辑单据、跨页续表/半行、Word锚点、原始数值与无模板缺值 | 表/行重建、范围划分、原生候选schema及字段归因，不复制原文数字解析 |
| `evidence-linking` | 文件/出现位置/派生件关系、字段引用、全球数字/币种歧义 | 来源映射、原文回读、唯一原文数值/币种解释和字段支持事实，预览复用 |
| `billing-reconciliation` | 费用映射、精度/金额关系、匹配、更新意图、AR/AP | 标准化、精确运算、匹配/更新提案及金额/重复等校验函数 |
| `billing-confidence` | 当前证据/校验支持度、分项权重、字段定位、快捷复核条件与硬门禁 | 复用新鲜校验结果评分，解释支持与不足；不替代校验、审批或统计正确率 |
| `human-review` | 人工值优先级、字段变化影响、复核问题 | 修订语义、受影响产物判定、依赖失效与定向重算提案 |
| `billing-export` | 题目JSON层级、operation、数字序列化、复核标记 | JSON组装、业务输出schema及导出产物 |
| `feedback-improvement` | 候选/选择/独立评测、关键断言、审核发布 | 候选规则与Skill改进材料、评测比较及报告 |

这里列的是可调用能力，不是固定执行顺序。Agent可以组合所需Skills或因证据不足回到前一个能力，简单任务可跳过不需要的包。每个包独立版本化；禁用必需能力会明确显示不可满足，不转用后端隐藏的同等硬编码实现。

当前工作树版本：`document-intake 1.2.0`、`document-extraction 1.3.0`、`evidence-linking 1.2.0`、`billing-confidence 2.0.0`、`billing-reconciliation 1.1.0`、`human-review 1.0.0`、`billing-export 1.0.0`、`feedback-improvement 1.1.0`。此前CAS v5固定的是extraction 1.2.1、evidence 1.1.2、confidence 1.0.2及reconciliation 1.0.1等旧包。工作树版本不等于任一历史任务的固定版本；历史能力没有评分包时明确不可用，不静默装载今天的规则。

Office接入由 `document-intake` 组合项目内LibreOffice 26.8.1.1，转换旧DOC/XLS、重算缺失或声明陈旧的公式缓存，并生成Word派生PDF。原件与派生件分别保存哈希，转换日志保留版本、参数、返回码与输出；原始公式、原缓存和重算值不互相覆盖。Word证据仍以原内容锚点为准，预览页映射绑定派生PDF哈希，不能当作DOCX稳定物理页。`DOC_CONVERTER` 相对路径由 `backend/config/settings.py` 相对backend解析；预览参数默认True，没有 `OFFICE_PREVIEW` 环境开关。二进制来源与运行边界见 [portable-environment.md](portable-environment.md) 和 [vendor说明](../backend/vendor/README.md)。

置信度通过宿主工具 `assess_task_confidence` 调用固定版本纯函数 `assess_confidence`，先取得当前revision的新鲜Hook事实。v2默认 `S = 70 × (0.45A + 0.35C + 0.20N) + 20 × max(0.5L, T) + 10V`，字段来源70、一致性20、覆盖10；A/C/N是金额/币种/原始费用名支持二值，L要求来源操作数与金额不同token且财务校验通过，T要求同单据/币种唯一适用总额且不复用费用金额token，V是覆盖通过。任务取最低费用分，缺检查不重归一化，单号可缺失不计核心权重，重复引用/文件或模型票数不加分。原文解释只在evidence包，金额计算/规范化只在财务包，confidence不另写解析或乘法；未经独立金标校准，分数不是概率。

无数量/单价/总额的合法费用保留缺值并说明缺少支持，不强加模板。已提供的金额/币种/费用名若 `unsupported/ambiguous/unavailable`，统一evidence Hook返回硬错误，包含重复位置或无适用字段引用；批准及正式导出422，而不只是界面低分。显式总额证据不支持声明金额/币种仍为 `TOTAL_VALUE_UNSUPPORTED`。全球数字原文与候选、有限币种名称支持、当前 `source_support_v2` 和财务 `normalized_charges` 绑定合同见[研究记录](research/global-extraction-confidence.md)与各包references。框架装配及原生Hook机制不因本轮调整，无额外模型评分请求。

领域schema随业务包携带；backend只保留任务、产物引用、问题、revision、回执等通用信封。Vue按发布包提供的字段/列/问题元数据呈现表单和结果，不在UI重新实现财务规则；首期用少量通用组件，无需建设低代码页面平台。

## 4. 发现、执行与热插拔

### 4.1 直接复用原生 SkillsMiddleware

配置 `sources` 指向**包含各技能目录的父目录**，例如 `/skills/`；不把单个含 SKILL.md 的目录误当技能库。主控和子Agent显式挂载需要的库，复用元数据发现、按需读资源、pinned_skills和动态工具披露。

新增、替换或禁用业务包通过配置发布，不修改主控分支或预编译一张业务DAG。当前 `backend/config/transactions.py` 管理配置事务，`backend/extensions/snapshots.py` 对配置、改进注册表及启用 Skill 文件生成内容摘要并保存不可变发布目录，新任务固定 `capability`；`SkillResources.abefore_agent` 挂载该版本资源、重置 `skills_metadata=None` 并提交pin，父子分别装配。在途任务继续用原快照，每次派发及重试读取实时启停配置，已禁用能力不能新发起调用。修改配置不会自动迁移旧任务、替换历史pin或重跑旧审批。

原设计要求的恢复时版本迁移、旧指令清理以及所有子Agent/MCP版本的完整回滚仍须分别验收；当前可用证据主要覆盖新任务快照、配置条件写入/并发原子替换、原生MCP派发及实时禁用。不能把保存配置成功写成全部热插拔场景通过。

pin输入键消费后清空不表示历史内容被移除；元数据重载不会替换历史pin消息，再pin只是追加快照。迁移时显式处理旧指令快照及审计。Skill工具隐藏仅限只交给SkillsMiddleware的工具；Agent全局同名工具本就可用，摘要移除对应消息后的工具披露也须验收。

### 4.2 复用官方加载与执行层

LangChain/Deep Agents 已有完整的组合入口，不能从“加载Skill不会自动执行所有脚本”推导出“没有执行层”。官方支持以下两条路径，均无需项目另写Agent循环、通用脚本runner或subprocess执行桥：

| 路径 | 原生组合 | 本项目使用方式 |
| --- | --- | --- |
| Skill关联工具 | `SkillsMiddleware(tools=工具列表或SkillToolResolver)` + LangChain原生工具调用 | 当前便携Web方案的默认路径：包内函数/成熟工具通过官方API绑定，读取或pin相关Skill后按需披露；业务代码仍全部在scripts，不在宿主复制 |
| Skill脚本与shell | `SkillsMiddleware` + `FilesystemMiddleware` + 实现`SandboxBackendProtocol`的backend | 需要shell时启用原生`execute`运行包内CLI；先选已有backend，验证运行环境和文件同步，不能重新写一套同等执行器 |

第一条路径的 `tools` 支持普通函数，由官方组件转换为工具；resolver只解析当前固定版本的工具对象，再交原生handler执行，不能绕过middleware。配置保存已发布包及入口绑定，宿主只做必要装配。`metadata.include_tools` 与`SkillToolResolver`负责披露/关联，不会自行把任意`scripts/*.py`导入执行。默认不保留自定义`run_skill_script`工具。

第二条路径中，`FilesystemMiddleware`检测到实现`SandboxBackendProtocol`的backend便提供原生`execute`，结果带`ToolMessage.artifact`中的`ExecuteArtifact`。`StateBackend`及普通只读文件backend不具备shell执行能力；`CompositeBackend.execute`固定走默认backend，`/skills/`文件路由不会把脚本自动同步到执行环境。使用隔离sandbox时，按官方示例在`before_agent`显式上传固定版本Skill、输入和必要依赖，运行后取回产物，保留原件与路径映射。

执行backend的已知条件：

| 选择 | 官方边界与当前状态 |
| --- | --- |
| `LocalShellBackend` | 官方已有本地执行，无额外服务账号；无OS隔离，文档将Web/API及不可信输入列为不适用，不能因为可在本机执行就直接定为本项目Web默认方案；Windows兼容仍须实测 |
| 现成隔离sandbox backend | 优先核对官方集成所需平台、服务/凭证、依赖、文件同步、生命周期与便携要求；不能把需要新账户或额外运行设施的方案描述成当前已具备 |

设计初稿中“没有安装 Deep Agents/执行 Skill”的状态已过期：当前 Deep Agents 0.7.29 已安装，包内函数的原生 Skill 工具执行已验证；本项目没有启动 sandbox，也没有把原生 shell 路径作为已完成能力。以后确需该路径，先通过MCP确认候选backend再做最小兼容验证；现成实现有平台缺口时记录具体限制，不能未经查证新增自写执行层。当前函数绑定路径不要求 Docker 或 sandbox 账号。

所有路径均返回结构化状态、产物和问题，Hook检查输出schema、revision和证据；shell路径另查执行artifact和退出码。`ToolMessage(status="success")` 不等于脚本exit_code为0，更不等于金额/覆盖检查通过。

框架wrapper只能看到经过它的调用。脚本内部HTTP/SQL/子进程不会自动逐项触发LangChain工具Hook：需要逐请求计量/校验的外部动作必须经注入的受控客户端或拆成可检查的工具边界。纯离线金额/证据函数无需人为变成多个Agent工具。

### 4.3 跨平台复用验收

交付单包时携带规则、脚本、schema/映射、依赖和最小样例，不能只交SKILL.md。在项目宿主之外，通过独立CLI/另一兼容宿主运行相同样例，比较业务JSON与证据引用；缺少依赖/服务时返回明确错误。

其他宿主仍需要可用的解释器、文件/网络能力，以及原生shell执行或工具绑定能力。Hook统一管理是本项目宿主能力，Agent Skills标准本身不自动提供；迁移后须接入目标宿主的校验拦截路径。不能把原包可读误称为跨平台执行与校验已经通过。

## 5. 不同校验是不同 Hook

Hook 负责在正确时机检查产物与动作，不能由Agent自行选择是否跳过。每项Hook先核对官方现成middleware/参数/集成；可配置完成的直接统一装配，不能先创建自写处理器。以下ID/事件/返回值是项目约定；框架级触发点通过官方middleware实现，业务产物/导出若确无对应能力，才补已记录缺口的接入，不冒充内置API。

| Hook | 检查内容 | 触发边界 |
| --- | --- | --- |
| `schema` | 输入/产物/工具参数结构、类型、枚举 | 输入接收、脚本返回、人工修改、导出 |
| `coverage` | 页/块/行去向、缺失范围、未闭合跨页片段 | 提取产物保存、聚合、导出 |
| `evidence` | 引用存在、原文可回读、来源/派生版本 | 证据关联后、人工修改后、导出 |
| `amounts` | 精确金额、币种组、税/折扣/明细/总计关系 | 费用提案/修订、导出 |
| `matching` | 候选唯一性、同名真实多行、重复材料 | 核对产物保存、修订、导出 |
| `updates` | 更新意图、缺失/清空/新值、旧值继承与变更范围 | 更新提案、人工修订、导出 |
| `posting` | 记账主体、交易关系、AR/AP依据与歧义 | 核对提案、主体修改、导出 |
| `revision` | 输入版本、人工确认字段与新旧结果一致 | 读取、派发、保存、恢复 |
| `approval` | 决策绑定的参数、产物/工具/Skill/规则版本 | 实际派发、提交、导出 |
| `capability` | Skill/MCP/工具启用与绑定版本 | 每次真实派发及重试 |
| `budget` | 共享用量、并发与控制状态 | 模型/工具/外部请求实际派发 |

每种校验是独立配置项，不等于必须新增一个Python文件。先查询MCP：官方已有审批、重试、调用限制等能力直接引用其middleware；确证缺少领域校验时才新增独立处理器，而非向一个大函数追加条件。必要的金额、证据等领域校验的**唯一算法实现**留在对应Skill scripts；hooks/amounts.py等仅为经查证后可能需要的接入示例，不复制公式/规则。

校验脚本同时供Hook、Skill与离线测试使用；管理器调用确定性校验入口时不重新进入同一业务Hook链，避免自触发递归。若需外部请求，该请求依然经过客户端层的控制/计量。

### 5.1 统一管理的最小合同

设计语义包含Hook身份/版本、事件/顺序、启停/必需性及Skill校验入口；只实现实际需要的配置字段。统一入口复用官方middleware的配置装配及领域产物校验薄接入，不建设另一套事件总线、任务队列或工作流引擎；设计示例中的 `backend/hooks/manager.py` 并非当前文件。

当前配置实际使用 `version`、各条目的 `name/enabled/required/priority/skill/function/native`，不能把设计中的其他示例键当成已支持项。十一类在当前文件中的名称为 `schema/coverage/evidence/amount/matching/update/posting/revision/approval/capability/budget`（其中 `amount`、`update` 对应上表的 amounts、updates）。实际 `backend/hooks/validation.py:validate` 调用固定版本包内校验，并返回 `ok/revision/issues/checks/at/event`；`backend/middleware/` 组合原生模型/工具 wrapper 与共享派发策略。必需Hook缺失/禁用阻断导出、过期审批/人工revision失效、重试前暂停和实际调用计量已有测试，完整异常/超时/所有外部请求组合仍按验收矩阵保留剩余项。

设计中 `allow/block/request_input` 表达业务决策语义；当前结果以 `ok/issues/checks` 表达允许或阻断，Agent/人工请求另走原生HITL，不存在同名通用Hook返回协议。缺失数据进入待补充或复核，关键Hook失败/异常不得转成财务成功。默认校验不修改业务值；确需受约束参数修改时重新校验，并使旧审批失效。

当前十一类必需集合由 `backend/hooks/validation.py` 的 `REQUIRED` 常量确定；配置虽有 `required` 字段，但尚未实现由独立profile任意选择必需集的设计。前端可以改启停/顺序，关闭或缺失必需项会阻断正式导出。该固定集合是当前实现偏差，不能宣称必需profile已经完整可配置。

统一记录Hook ID/版本、事件、包/入口摘要、任务/revision、耗时、结果及问题；界面可筛选具体Hook并跳转证据。工具真实回执与Hook结果分开保存，后置观察失败不得触发重复副作用。

### 5.2 原生middleware装配

工具wrapper保持“固定版本动态解析 → HITL → 原生ToolRetry → capability/revision/approval/budget等派发检查 → handler”；业务产物Hook在产物接收/正式导出时必须执行，不能只检验聊天里的候选。

父子Agent显式接入相同Hook管理入口；摘要/修复模型使用同一实际请求计量。重试内层重验暂停/禁用与额度，Hook的阻断不是可重试网络错误。Skill资源发现、pin和后台文件读取也不天然等于read_file工具事件，需要校验的已发布包在挂载入口检查。

## 6. 开发插件的强制使用

### 6.0 每个智能体操作先查 LangChain MCP

从现在开始，创建/调用Agent、规划、Skill发现/读取/执行/刷新、工具/MCP调用、子Agent委派、Hook、人工介入/恢复、检查点、上下文、计量和反馈改进，每项操作在实施或调整前都必须先查LangChain Docs MCP，再查API Reference MCP核对符号/参数与适用包版本；必要时用GitHub MCP读取固定提交源码。已核实且当前版本/组合仍适用的同一操作可以复用依据，不能仅用框架总览代替新增操作查证。

研究/实现记录保留“操作、官方入口/符号、适用与安装版本、原生组合、实际验证/未验证缺口”。MCP不可用先恢复并推进独立工作，不凭记忆先实现后补引用；该纪律约束开发过程，不要求运行产品每次处理文档都查询开发MCP。格式库、数据库、Vue构建等另查各自官方资料。

**只有查证官方确实没有满足该项具体职责的能力，才允许自写智能体相关代码或脚本。** 包括Hook、Skill脚本、工具适配、共享计量和反馈循环；“薄适配”不是豁免。查证现成可配置项、官方集成及版本限制，说明具体缺口后才决定最小补充；没有搜索命中、未安装依赖或尚未运行成功不能证明能力不存在。普通环境准备、纯构建/打包脚本不属于此规则的LangChain能力范围，但其中涉及Agent逻辑的部分仍适用，stop-that-shit要求照常执行。

### 6.1 代码编写与运行：stop-that-shit

按用户明确要求，任何项目代码编写/修改，以及运行代码、脚本、测试、构建或依赖验证之前，必须读取并应用当前会话可用的stop-that-shit插件Skill，使用change工作流完成已授权范围及必要验证；只读审查使用review。子Agent也遵守。

当前可用入口：`C:/Users/dzx/.codex/plugins/cache/stop-that-shit/stop-that-shit/0.2.5/skills/stop-that-shit/SKILL.md`。后续版本路径以当前会话技能目录为准。

宿主支持时采用Skill列出的Codex原生指令，例如 `$stop-that-shit change -- <当前任务>`。这是宿主/提示入口，不是在PowerShell执行的程序；不伪造不存在的MCP方法、shell命令或Guard回执。当前已读取Skill指导，不据此声称机器级Guard已启用或每次动作自动受拦截。

若要求的插件/Skill不可用，先恢复其能力并说明缺口，不能绕过用户要求继续写/跑代码。此约定是开发阶段纪律，不将Codex插件绑定为交付程序运行依赖。

### 6.2 前端编写：design

前端开始编写或修改前必须调用当前可用的design Skill，按其路由完成页面目标、信息层级、设计tokens、布局、组件状态与浏览器核验；代码和构建运行同时遵守stop-that-shit。

当前入口：`C:/Users/dzx/.codex/skills/design/SKILL.md`，已读取其 `references/design-routing.md`。按任务需要使用design-system、ui-styling等配套指导；采用Vue兼容实现，不能因Skill例子使用React就替换用户指定技术栈。无需为工作台额外生成logo或引入无关模型服务。

界面统一间距、排版、颜色语义、组件密度和状态；任务/材料/费用/证据联动，加载、空态、失败、复核、过期修改与暂停都有实际反馈。设计决策放 `docs/ui-design.md`，tokens集中在前端样式目录；实现后再提供真实截图，不用效果图冒充可运行页面。

## 7. 目录与面试展示

完整树维护于implementation.md。根目录按 backend、frontend 两个工程组织，公共说明在 docs/；业务包位于 backend/skills/，校验装配在 backend/hooks/，配置在 backend/config/。避免service/domain/engine等重复层，以及backend中暗藏账单逻辑。

README首屏说明项目用途、架构、快速启动入口和核心演示路径；随后展示Skill/Hook清单、真实测试结果及实际截图。本次目录整理已将后端的代码、Skill、Hook、配置、运行时和测试归入 backend/，Vue 工程归入 frontend/。题面在 docs/assignment/，原题材料在 backend/data/samples/；内容保持原样，运行与迁移结果以验收记录为准。

当前反馈链路使用 `feedback-improvement` 与原生本地 LangSmith 实验，候选包含来源任务/revision/能力摘要、差异和适用范围，发布须明确人工审核，注册表支持回滚。实际会影响后续新任务的仅为 `accounting_entity` 作用域的 `charge_mapping`，其他候选类型保留为草稿。界面已验证合成集 5/7→7/7、发布与回滚；该合成比较不能充作原题真实金标、通用提示词/Skill自动优化或模型训练的证据。

当前OBS自动上传与指定OCR基础链路已有真实验证，不能继续将可下载URL写成普遍缺失；LibreOffice项目内入口及Office合成材料有本轮回归。它们不能替代真实复杂DOC/跨页端到端、独立真实金标或全负载P95；本轮在线及浏览器验收按实际新增报告记录，不由离线通过数推断。最新结果分别见 [acceptance.md](acceptance.md)、[recovery.md](recovery.md)、[performance.md](performance.md) 和 [sample-inventory.md](sample-inventory.md)。

## 8. 验收补充

1. 每个业务包都具备有效SKILL.md、references和scripts，引用路径/依赖完整；可使用官方指向的skills-ref工具验证格式。
2. 新增/替换业务Skill只改挂载/绑定配置；宿主Agent组合与业务前后顺序不写死。
3. 禁用Skill后实际入口不可执行；旧版本运行按边界规则处理，不偷偷调用backend兜底实现。
4. 独立运行包内脚本，不导入项目backend；相同样例得到一致业务结果和来源引用。
5. 每类校验有独立Hook，统一启停/顺序/版本/记录；必需Hook阻断正式输出。
6. Hook和Skill共用同一份校验算法，检查失败、执行异常、脚本非零退出和工具成功消息分别处理。
7. 跨宿主迁移验证包与执行环境；项目Hook策略另行接入，不宣称标准自动保证执行授权。
8. 开发记录能够说明实际使用的MCP/插件、版本与验证结果，不以配置存在或Skill文件已读代替运行证据。

## 9. 本轮官方依据

设计阶段已通过LangChain Docs MCP读取 `/oss/python/deepagents/skills.mdx` 的Usage、How skills work、Add supporting resources、Add tools、Reload skills、Execute code和Frontmatter fields；通过API Reference MCP读取SkillsMiddleware、FilesystemMiddleware和LocalShellBackend。API引用源码固定提交为`9db018bf1b94c11f06ea4f33d69d133c34097e08`。其“未安装Deep Agents”是历史状态；当前锁定0.7.29，实际组合见 `backend/agents/factory.py`，原生披露/执行证据见 `backend/tests/test_host.py`。

- Skills：`https://docs.langchain.com/oss/python/deepagents/skills`
- SkillsMiddleware：`https://reference.langchain.com/python/deepagents/middleware/skills/SkillsMiddleware`
- SkillToolResolver：`https://reference.langchain.com/python/deepagents/middleware/skills/SkillToolResolver`
- FilesystemMiddleware：`https://reference.langchain.com/python/deepagents/middleware/filesystem/FilesystemMiddleware`
- SandboxBackendProtocol：`https://reference.langchain.com/python/deepagents/backends/protocol/SandboxBackendProtocol`
- LocalShellBackend：`https://reference.langchain.com/python/deepagents/backends/local_shell/LocalShellBackend`
- sandbox集成：`https://docs.langchain.com/oss/python/deepagents/sandboxes`
- 官方现成middleware：`https://docs.langchain.com/oss/python/langchain/middleware/built-in`
- 原生工具调用限制：`https://reference.langchain.com/python/langchain/agents/middleware/tool_call_limit/ToolCallLimitMiddleware`
- 原生工具重试：`https://reference.langchain.com/python/langchain/agents/middleware/tool_retry/ToolRetryMiddleware`
- 标准：`https://agentskills.io/specification`

当前八个业务包与统一Hook已有实现，函数工具路径已有验证，shell/sandbox及未覆盖真实外部场景仍待验收。后续每个智能体操作仍先用Docs/API MCP查证，再编写/调整实现；既有记录只在版本与场景仍适用时复用。
