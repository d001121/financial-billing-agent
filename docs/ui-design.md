**2026-10-24 最新：全站海洋主题与核账布局。** 已按批准的`tide-workbench-v2`实施固定全宽海景页头、浅雾绿侧栏、灰白阅读面、紧凑标题/摘要和桌面左右核账区。各面板按钮集中在自身标题，常驻助手保持480px/手机440px；六字段、待办、原文与修订入口延续。海面位移和光影使用网站生成的独立摄影资产，提供持久化开关，跟随系统减少动效；不让费用和正文循环移动。

打开原文抽屉时发现PDF.js全局`.sidebar`设置239px宽，覆盖应用200px导航并遮挡主体。现将应用导航类和token隔离为`.harbor-sidebar`/`--harbor-sidebar-width`；真实打开/关闭预览后桌面侧栏与主体起点均200px，平板均184px，手机菜单242px且可开合。已提取但有缺项的费用提示也改为如实说明“费用已保存，未提供信息为空”。

验证：14项消息顺序/状态展示定向离线检查通过，最终Vue类型/生产构建通过（2510模块）；使用真实App与合成API的开发专用预览核对1280、1024及390px、导航、搜索、更多信息、金额原文抽屉、修订打开后取消、待办展开、动效关闭/刷新与系统减少动效。无页面横向溢出、error日志为空，临时浏览器覆盖已恢复。未发送真实消息、上传、修订或审批，未跑全量/真实模型/OCR；后端2024监听0。实现、素材和既有构建大包提示见[设计记录](design/ocean-ui-20261024/README.md)，全图与局部并排比较和真实验证边界见[设计核验](../design-qa.md)。

**2026-10-24 最新：会话消息同步与顺序修复。** 账单12的“你好”已由后台在2026-10-24 02:58:54完成，原页面仍只展示旧SDK消息与本地提问。AgentPanel原来只要SDK消息非空就忽略任务接口的最新native_messages；本地提问又可能在答复后才补入，或依旧锚点插进上一轮。现以原生检查点顺序为基准，按真实message.id更新重叠消息、补齐漏到的回复并接上实时新增消息；延迟部分内容不能缩短完整答复。普通聊天优先定位原生chat-user消息，尚未同步时保留发送位置，已有完成回执可通过response_message_id定位。相同用户回复只展示一次。底部跟随改为观察实际展示的消息而非只有SDK增量；用户向上阅读时保持位置，可点击“回到最新消息”。

查证：Docs MCP的frontend/join-rejoin及消息展示示例、Reference MCP的@langchain/vue.useStream，安装版@langchain/vue1.2.5/@langchain/core1.2.19的公开声明确认messages由原生delta与values.messages装配，threadId/disconnect负责接续。继续使用官方订阅、消息类及检查点；本次只补应用native_messages快照和conversation业务回复的显示衔接，不新建订阅、事件存储、状态reducer或后端运行机制。

验证：新增9项消息投影/顺序离线用例（修复前4项顺序用例中3项失败），连同5项已有状态展示检查共14项通过；Vue类型与生产构建通过。真实账单12只读页面已显示“你好”后接对应助手回复，消息体距底部0px；实际AgentPanel合成预览验证提问→部分答复→同ID更新→原生提问回填，提问仅1次、顺序不变且跟随底部（误差小于1px），向上阅读后新增消息保持scrollTop=0并显示回到底部按钮。临时预览已移除。未发送真实聊天、修改/确认账单，未新增模型/OCR调用、未跑全量测试、未重启后端。

**2026-10-23 最新：常驻聊天与待办提醒。** 输入框在处理结束后继续显示，支持提问、补充或自然语言修改字段；运行期间保留可输入草稿，当前轮结束后发送。待回复数和未完成计划固定在助手标题下的紧凑提醒条，展开列出具体事项，“去回复”聚焦输入框；异常/暂停显示相应处理提示。沿用灰绿中性色、面板内滚动及桌面480px/手机440px高度上限。普通聊天不自动确认账单；无关消息或修改其他字段不消除原待办，修改仍生成新revision并校验。覆盖本文历史“结束隐藏输入框”的描述。

Vue类型/生产构建通过。真实账单只读验证输入常显及草稿输入后清空；独立合成Vue预览验证待办展开、聚焦和处理中草稿，390px下面板宽350px/高440px，提醒和输入均在面板内，无页面或面板横向溢出，控制台无error。未发送真实消息、修改或确认账单，未跑全量、真实模型/OCR、未重启后端。后端新聊天路径需进程重载后生效。截图：[实际账单输入框](../backend/tests/reports/persistent-chat-desktop.png)、[合成待办桌面](../backend/tests/reports/persistent-chat-todos-desktop.png)、[合成待办手机](../backend/tests/reports/persistent-chat-todos-mobile.png)。实现与定向离线验证见[记录](research/persistent-chat-20261023.md)。

**2026-10-23 界面微调：账单助手窗口缩短。** AgentPanel桌面高度上限640→480px，手机580→440px，保留360px最小高度及原有内部滚动、标题/输入区布局。Vue类型检查/生产构建通过；浏览器实测桌面480px、390px手机440px，手机面板宽345px且无自身横向溢出。未跑全量或模型/OCR，未启停后端。截图backend/tests/reports/shorter-assistant-desktop.png。

最新交互（2026-10-23，统一面板与操作位置）：覆盖上一轮临时多色分区和浮动操作栏方案。各面板沿用同一白色/浅灰绿表面、灰绿边框及标题层级；账单级操作只在页头右侧成组，费用级修订/拆分/删除只在所选费用标题右侧成组，随页面正常滚动。全局顶部导航仍按此前约定固定。费用表删除重复修订列，页脚删除重复确认入口；更多信息页也保留所选费用复核与操作。参考材料用中性折叠条，置信度继续保持紧凑六列/三列/两列，原文按需展开。

已使用Product Design插件现有产品上下文/局部修改规则，以及design、stop-that-shit。Vue类型检查/生产构建通过；独立浏览器现有账单只读核对桌面与390px、切换费用后修订表单内容正确并取消、更多信息操作可达、无浮动操作栏、两组按钮无自身横向溢出。手机当前3个账单按钮同行；未提交修订/确认/拆分/删除，未运行全量/真实模型/OCR测试，未启停后端。临时尺寸已恢复。截图：[页头](../backend/tests/reports/sectioned-bill-header.png)、[费用面板](../backend/tests/reports/sectioned-bill-desktop.png)、[手机](../backend/tests/reports/sectioned-bill-mobile.png)。

**2026-10-22 最新：主体由会话确认，核对与证据合并。** 提交页移除记账主体输入，先读取材料并保存费用，再由账单助手询问公司；候选只取已保存文档/费用中的公司事实，点击填入聊天草稿，发送后才通过既有人审Skill生成新revision并重算AR/AP，可自填或暂缓，不自动指定主体。主动修改主体同样提供候选。缺主体的结束检查复用原生interrupt/Command及固定human-review2.0.2；旧快照不迁移。覆盖旧“缺主体可不问便结束”的交互约定，原件未提供的普通可选字段仍留null。

最新交互（2026-10-23，紧凑复核区）：所选费用标题与修订/拆分/删除在同一工具栏；置信度总分并入标题栏，六字段随容器宽度采用六列、三列或两列。低分与歧义原因继续显示，正常字段不重复展示“有原文依据”；原文取值、引用列表、核对依据按需展开。引用展开区最大320px并独立滚动，桌面双列、窄屏单列，保留全部引用及原件入口。切换所选费用时引用折叠状态重置。

本次Vue类型检查和生产构建通过；现有账单页面只读验证桌面六列、9处引用全部展开、顶部修订表单打开后取消、390px两列且复核区域无横向溢出。未提交业务修改，未运行全量测试或真实模型/OCR；未启停后端。截图：[桌面](../backend/tests/reports/compact-confidence-desktop.png)、[窄屏](../backend/tests/reports/compact-confidence-mobile.png)。

账单核对采用一张卡：费用表、所选费用置信度、原文及原件定位、修订入口；参考材料收在卡内，取消独立证据侧栏。展示合并重复原文，默认两处，其余展开，不改原始引用或评分算法。会话定向20项、Vue类型/最终生产构建通过（2501 modules、Vite1.03秒、index-D0ZuYs_R.js）；隔离真实原生服务+合成模型验证主体选择→回复→revision1到2→AP，未代答真实账单。skills配置v22，能力7f0d339560e7dc403618；正常重启PID35060，33线程ID/状态相同，GaussDB/Redis健康。未做全量测试、打包或真实OCR/Qwen整单重跑。详见docs/research/entity-choice-and-bill-review.md及entity-choice-*回执。以下记录保留历史范围。

2026-10-22 会话布局修正：移除账单详情中残留的“补充记账主体”黄条，待补充问题在账单助手内作为消息展示；仅真实待回复/提交期间显示底部聊天输入框和“发送”按钮，继续使用既有原生中断与回复API。助手面板按视口固定高度（桌面上限640px、窄屏上限580px、最小360px），标题/输入区固定，计划、消息和问题在同一内部区域滚动；展开记录不改变面板尺寸。保留向上阅读和回到最新消息。Vue类型与生产构建通过（2494 modules、Vite1.12秒、index-DRqTUL6_.js），当前真实待回复账单的桌面/390px检查通过，无页面错误；只填写后清空测试文字，未发送、修改或审批账单，未做全量测试。截图与回执见backend/tests/reports/conversation-fixed-{desktop,mobile}.jpg、conversation-fixed-ui.json。前端dist已生效，后端无需重启。

2026-10-22 当前实现：账单处理采用Codex式会话，只有真实人工中断显示内联输入框；原生线程的主体/费用修改、拆分/删除及针对性复核入口转到会话，用户只需自然语言。原生HITL与middleware复用，字段修改交给现有human-review Skill，新revision后重新核验，不能默认批准。32项定向测试通过，Vue类型/生产构建通过（2494 modules，Vite0.961秒，index-BShsDezv.js）；隔离真实Agent Server+合成模型/材料/存储的浏览器验证两轮回复、revision1→3、刷新恢复、结束隐藏输入框及无审核弹窗。未做全量测试或真实OCR/Qwen语义复测。详见[会话审核架构与验证](research/conversation-review.md)、backend/tests/reports/conversation-pytest.xml及conversation-ui.json；当前进程/32线程保留见conversation-restart.json。以下旧表单及进程数字保留历史身份。
# 航账 Harbor：前端实现与联调记录

2026-10-21 实时链路补修：后台统一使用原生v2命令和事件，Vue原生工具/消息投影现在获得真实增量。补充首检查点前误判idle的重新订阅：依据已有任务刷新中的真实run/计量标量推进重新挂载，不新增轮询；终态run_status阻止旧失败检查点造成永久转圈，已在真实失败任务验证。独立真实Agent Server+最终生产Vue验证页面先打开后启动、2次工具执行/返回、回复逐步出现、工具展开中更新、结束收起及刷新恢复，390px无横向溢出、无pageerror。最终入口index-DzfPQr8K.js、AgentPanel-gK4gJAFb.js，2418 modules、1.07秒；正式服务PID19252。见[查证与真实联调](research/agent-activity-streaming.md)，下文仅合成协议验证为历史范围。

最新交互（2026-10-21，执行时间线）：用户账单详情直接展示“智能体处理过程”，运行时展开、结束后收起，可重开查看检查点记录。按顺序显示模型可见回复、工具名称/上下文/状态，工具参数与结果默认折叠；长文本折叠，默认最近12条记录并可看之前记录，靠近底部时跟随更新，向上阅读时保留滚动位置。子智能体独立卡片展示任务及其消息/工具，结束后自动收起。原生计划默认折叠，人工补充表单始终在过程折叠区外。以下“计划/工具只在Trace中展开”是历史版本；本次用户明确要求在详情中查看执行过程。

使用官方@langchain/vue1.2.5的useStream、useMessages、useToolCalls与SubagentDiscoverySnapshot，状态、工具装配、检查点恢复和命名空间订阅交由SDK；项目只补Vue展示、中文标签与显示顺序。AgentActivityFeed.vue复用主控/专家呈现，AgentExpertActivity.vue持有官方作用域selector，agentActivity.ts只做显示投影。模型只展示AIMessage.text，排除reasoning内容。工具“已返回”表示调用有返回，不代表财务校验通过；没有返回时不冒充完成。命令区域只对已有命令工具参数显示，没有因此为后端新增命令执行权限。

官方查证：Docs MCP读取`/oss/javascript/langchain/frontend/tool-calling.mdx`与`/oss/python/deepagents/frontend/subagent-streaming.mdx`；API Reference MCP核对上述Vue入口及发现快照。官方提供流、消息、工具及子智能体投影，不包含本项目的账单时间线布局，因此只补最小展示组件。未修改后端Agent、Skill、Hook、模型配置或人工提交契约。

本轮构建及浏览器12项定向检查通过，报告见[agent-activity-ui.json](../backend/tests/reports/agent-activity-ui.json)，截图见[桌面过程](../backend/tests/reports/agent-activity-live-desktop.png)与[390px界面](../backend/tests/reports/agent-activity-mobile.png)。浏览器数据及v2事件均为本地合成，未触发真实提取、审批或回复；未跑全量测试。生产构建2418 modules、Vite1.10秒，入口index-CQrGcB1Q.js，服务无须重启。下面的旧构建号及截图保留历史身份。

最新交互（2026-10-21）：正常账单自动核验完成，直接查看六字段结果、已有字段置信度、提取原文及原文件预览定位；仅低于阈值的已有字段显示针对性人工复核中断。未提供的信息不作为低分待办。用户可随时修改提交，已中断任务修改后在原生表单继续。更多信息按每项费用纵向分组，不再使用1900px宽表；修订窗口内容独立滚动，页脚保持可达。主体提交区分运行中和版本冲突，保留输入并在窗口内对照，不再要求复制重填。下文常规逐单确认及旧截图是历史阶段；最新规则和验证见[条件复核说明](research/conditional-confidence-review.md)。

日期：2026-10-21。本文记录当前面向业务用户的Vue工作空间、接口约定与分阶段联调结果，不替代根目录AGENT.md、业务Skill规则或后端运行结果。页面重构与此前Office、置信度联调分别记录，历史截图不能充当新导航的验收。

最新验收：六字段核对调整后的生产构建为2411 modules、Vite 1.15秒，入口 `index-Pjg7CCsV.js`。本轮记录见 [bill-review-ui.json](../backend/tests/reports/bill-review-ui.json)。用户核对页已取消内部问题收件箱、核对计数与评分扣分列表，默认六字段表格；处理中无提前核对或确认入口，真实中断表单仍可见。用户/管理端分离及Trace的上一轮记录为 `bill-workspace-ui.json`，其中问题收件箱截图仅保留历史身份。账号与RBAC、完整异常矩阵和独立真实金标仍未新增。

![六字段账单核对](../backend/tests/reports/bill-review-six-fields.jpg)

用户只需查看 AR/AP、单据编号、费用名称、金额、币种和付款方式。置信度作为辅助信息；点击金额等字段可打开原件，修改入口保留。无模板原件未提供的单据编号和付款方式显示“未提供”，不自动生成待办或零分警告。修订窗口默认展示这六项；AR/AP由记账主体与交易关系重算，窗口保留只读方向，交易双方与日期折叠供必要时修正。没有在前端新增财务方向算法。

处理中可显示部分费用，分值显示“提取中”，不展示置信度扣分及内部阻断；确认仅在已有正式费用且业务进入复核状态时显示。暂停、预算终止、待补充和候选结果不能冒充处理完成。审批与正式导出的服务端必需校验保持原样；真实原生中断独立展示，未代答历史请求。

![当前账单业务中心](../backend/tests/reports/bill-workspace-center.png)

## 1. 界面方向

2026-10-21 用户端与右上角管理员控制台已分导航壳；新增 `#/management/traces`。用户端列表改读 `/api/bills` 的账单摘要，原生线程中断批量投影为具体待办。详情保留正文/全部附件参考材料区，六字段核对为默认表格，其余字段在“更多信息”；计划、工具、专家日志只在管理员 Trace 中展开。原生 Vue 中断组件在用户详情保持挂载。实现与统计边界见 [材料包与工作空间说明](research/bill-bundle-workspace.md)。下文上一轮截图和交互结果保留历史身份，本轮验证另记。

工作空间以“提交材料 → 查看结果 → 处理问题 → 确认导出”为主要使用路径。首页帮助用户判断下一步，业务中心负责查找账单，账单详情负责费用与原件核对，管理中心维护共享能力和规则。日常核账不要求先理解Agent、MCP或执行日志。

视觉方向采用深海军蓝侧栏、青绿主操作和暖白画布。总览使用留白与清晰待办，独立大屏采用深蓝背景；琥珀色表示待处理，红色表示失败或阻断。金额、币种及方向分列，operation保留在“更多信息”。

`src/styles/tokens.css`集中维护颜色、字体、圆角和阴影；组件使用语义变量。图标统一为`@lucide/vue`。桌面双列、较窄屏幕单列，宽表格局部横向滚动。界面只显示可核验的短业务依据，不展示模型内部思维链。

当前页面与入口：

| 页面 | Hash入口 | 用户主要操作 |
| --- | --- | --- |
| 工作总览 | `#/overview`，默认首页 | 开始新处理、查看待办和真实任务分布、进入业务中心或大屏 |
| 大屏总控 | `#/screen` | 独立展示状态分布、待办、主体分布、近期动态；可直接打开任务或返回工作空间 |
| 账单业务中心 | `#/tasks` | 按账单查看单号、交易方、各条金额、材料数及具体待办，支持搜索、筛选和分页 |
| 待办复核 | `#/review` | 集中处理待补充、原生人工请求和待复核任务，区分补充信息与确认结果 |
| 提交新材料 | `#/new` | 独立页面上传材料/导入样本/添加URL，补充处理要求；主体在会话中选择后自动检索同主体已完成且校验通过的历史账单，用户无需填写旧账单JSON；候选歧义交由复核 |
| 账单详情 | `#/tasks/{task_id}` | 原生人工补充、六字段核对表与更多信息、置信度、参考材料、原文定位、修订、确认和导出 |
| 管理员控制台 | `#/management` | 右上角进入，独立管理导航，进入能力、经验和Trace |
| 能力与连接 | `#/management/capabilities` | 配置Agent、Skill、MCP、Hook和运行参数 |
| 经验与规则 | `#/management/improvements` | 明确选择反馈、评测候选、人工发布与回滚 |
| Trace追踪 | `#/management/traces` | 真实活跃耗时、调用路径、工具回执、人工修订口径与未评测质量指标 |

Hash导航支持页面刷新、浏览器前进/后退，不要求静态服务为每个业务地址增加路径回退。业务中心的状态入口可使用 `#/tasks?status=review` 等链接；`KeepAlive`按业务中心/待办页面key分别缓存组件，在同次页面会话内保留搜索文本、主体、排序和分页，从详情返回继续原列表位置，整页重新加载不承诺恢复这些局部输入。

统计只读取服务端任务摘要：不把框架run的success当成业务审批通过，不合并不同币种金额。七天图表明确统计任务创建量；主体图表统计任务数量。空态、加载、服务不可用、校验失败、版本冲突均有明确提示；无首次数据时显示“—”，失联后保留旧快照并标注上次更新时间，没有随机任务、假进度或仅供演示的成功按钮。大屏是独立展示布局，无需浏览器全屏权限。

## 2. 实际目录与职责

```text
frontend/
├─ src/
│  ├─ api/client.ts                 # 业务HTTP、下载及错误归一
│  ├─ types/contracts.ts            # UI消费的服务端契约
│  ├─ styles/{tokens,base}.css       # 设计token与基础布局
│  ├─ utils/taskPresentation.ts      # 任务状态分组、行动文案与摘要计数
│  ├─ pages/
│  │  ├─ OverviewPage.vue           # 业务总览、待办与真实统计
│  │  ├─ ControlScreenPage.vue      # 独立大屏总控
│  │  ├─ TaskCenterPage.vue         # 业务列表/待办，搜索、筛选与分页
│  │  ├─ ManagementPage.vue         # 管理入口及能力/经验/Trace子页面
│  │  └─ TracePage.vue              # 官方路径、耗时回执与有口径的统计
│  ├─ components/
│  │  ├─ TaskComposer.vue           # 新材料表单，支持独立页内嵌
│  │  ├─ TaskWorkspace.vue          # 六字段核对、更多信息与参考材料
│  │  ├─ AgentPanel.vue             # 官方Vue流、todos、工具、子Agent、中断
│  │  ├─ RevisionDialog.vue         # 字段修订/拆分/删除/主体修改
│  │  ├─ ApprovalDialog.vue         # Revision审核
│  │  ├─ CapabilityPanel.vue        # agents/skills/mcp/hooks/runtime配置
│  │  └─ ImprovementPanel.vue       # 候选、评测、人工发布与回滚
│  ├─ App.vue                      # Hash导航、列表缓存及摘要/详情同步
│  └─ main.ts
├─ package.json / package-lock.json
├─ vite.config.ts
├─ dist/                           # 可由后端/app/直接提供
└─ README.md
```

没有在前端复制金额计算、AR/AP、去重、字段依赖、规则发布或文档解析算法。浏览器只做表单格式检查、JSON编辑和结果展示；业务权限、版本、校验与执行仍由后端与Skill负责。

## 3. 原生SDK查证与组合

本轮实际使用已暴露的LangChain Docs MCP与API Reference MCP查证以下操作。`@langchain/vue 1.2.5`、`@langchain/core 1.2.19`、Vue `3.5.44`已经本地安装并经类型检查和构建验证；Vue SDK解析到的`@langchain/langgraph-sdk`为`1.12.5`。不混入旧版FetchStreamTransport，不另写Agent SSE状态机。

| 操作               | 官方入口/符号                                              | 本项目组合与边界                                                                                 |
| ------------------ | ---------------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| 订阅已有任务       | `@langchain/vue/useStream`、frontend overview、join-rejoin | 后端创建thread/run；前端传`assistantId: workorder-agent`与已有`threadId`，不再发起第二个初始任务 |
| 原生计划           | `useStream.values`                                         | 展示`values.todos`的`content/status`，不建立第二套可写Plan                                       |
| 调用/委派显示      | `useStream.toolCalls/subagents`                            | 展示原生回执、失败及子Agent，不由聊天文本猜测完成状态                                            |
| 中断发现           | `UseStreamReturn.getThread`                                | 读取`getThread().interrupts`中的id、payload、namespace，兼容root ref；覆盖嵌套中断，不只取第一项 |
| 单项回复           | `UseStreamReturn.respond`                                  | 明确`interruptId`，附`config.configurable.task_id`与`recursion_limit:120`，由官方协议恢复原线程  |
| 同checkpoint多中断 | `UseStreamReturn.respondAll`                               | 所有回复先做输入检查，再一次映射提交；失败后刷新真实中断，禁止整批盲重发                         |
| 人工问答           | Python `RespondDecision`、HITL response_schema             | `ask_user`展示中文回复/拒绝表单，提交`{type:'respond'\|'reject',message}`；其他未知中断提供高级JSON入口 |
| 断开与重连         | `useStream.disconnect`、join-rejoin                        | 断开只停止订阅；重连重挂载官方hook，不调用会取消run的`stop()`                                    |
| 反馈与评测范围     | LangSmith evaluation-types、feedback-data-format           | UI使用项目业务候选API；不宣称本地版本发布API是LangSmith功能，也不伪装已接入LangSmith托管评测     |

官方依据：

- https://docs.langchain.com/oss/python/langchain/frontend/overview
- https://docs.langchain.com/oss/python/langchain/frontend/join-rejoin
- https://docs.langchain.com/oss/python/langchain/human-in-the-loop#read-the-response-schema
- https://reference.langchain.com/javascript/langchain-vue/useStream
- https://reference.langchain.com/javascript/langchain-vue/UseStreamReturn/getThread
- https://reference.langchain.com/javascript/langchain-vue/UseStreamReturn/respond
- https://reference.langchain.com/javascript/langchain-vue/UseStreamReturn/respondAll
- https://reference.langchain.com/python/langchain/agents/middleware/human_in_the_loop/RespondDecision
- https://docs.langchain.com/langsmith/evaluation-types
- https://docs.langchain.com/langsmith/feedback-data-format

API MCP提供的Vue源码依据固定在`langgraphjs cc29753d529caa5eed97a65e765ba26c0f88c631 / libs/sdk-vue/src/use-stream.ts`；Python人工响应定义为`langchain 84ba23c414eca6bf6f6ebd1394a3006378113540 / libs/langchain_v1/langchain/agents/middleware/human_in_the_loop.py`。最终适用性以安装包类型及真实联调为准，不把网页引用当运行验证。

`respond`仅在ask_user场景合成人工提供的信息，不伪造其他工具已执行成功。财务字段修订走业务Revision API，与原生工具中断回复分开。

### 本次页面重构的SDK边界

本次通过LangChain Docs MCP重新读取frontend join-rejoin的 `threadId`、disconnect和同线程重挂载说明，并用API Reference MCP核对 `@langchain/vue.useStream` 与 `UseStreamReturn.disconnect()`。官方Vue接口是Composition API的ref投影；`disconnect()`签名为 `Promise<void>`，只断开客户端，等同 `stop({cancel:false})`。源码依据仍为上述固定提交，安装SDK版本未调整。

本次只调整展现层：有thread的账单详情中，`AgentPanel`持续挂载；折叠的是面板内原生`details`中的计划、工具和专家执行记录，中断表单在折叠区域外持续可见。隐藏技术记录不会阻止官方hook水合，也不会隐藏用户需要回答的问题。详情退出后的订阅与重新进入仍沿用现有官方disconnect/rejoin实现，没有新增SSE、Agent执行器或恢复协议。

## 4. 实际业务API

业务前缀默认`/api`。列表为裸数组，配置读取为YAML解析后的对象；client会归一为组件需要的形状。

| 接口                                          | 交互                                                                                                 |
| --------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| `GET /health`                                 | 连接状态；不等同于所有外部业务请求成功                                                               |
| `GET /tasks`                                | 任务摘要投影：标题、状态、Revision、thread/run、summary、usage及`record_count`/`issue_count`；不返回费用、提取与校验详细数组 |
| `GET /tasks/{id}`                           | 当前任务完整详情，包括sources、todos、events、records与校验产物 |
| `GET /tasks/{id}/confidence`                | 当前任务固定能力版本的只读评分；前端展示服务端字段支持、核验信号与阻断原因 |
| `GET /tasks/{id}/sources/{source_id}/preview` | 按证据字段查询可用的原文结构、真实定位与派生预览；缺坐标不编造高亮 |
| `GET /assets`、`GET /samples`                 | 上传材料与题目样本                                                                                   |
| `POST /assets`                                | multipart字段`file`为单文件；或JSON`{sample_path}`/`{url}`；多文件逐项处理，已成功项不因其他失败丢失 |
| `POST /tasks`                                 | `{title,accounting_entity,asset_ids,instructions,existing_records}`；主体可为空，由Agent原生询问     |
| `GET /assets/{id}/content`                    | 已上传原件                                                                                           |
| `GET /tasks/{id}/sources/{source_id}/content` | EML附件与任务内来源原件                                                                              |
| `PATCH /tasks/{id}/revision`                  | `{expected_revision,reason,operations,accounting_entity?}`，operation为set/delete/split              |
| `POST /tasks/{id}/control`                    | `{action:'pause'\|'resume'\|'cancel'}` |
| `POST /tasks/{id}/approve`                    | `{expected_revision,decision:'approve'\|'reject',reason}` |
| `GET /tasks/{id}/export`                      | 正式导出，由当前Revision校验与审批决定                                                               |
| `GET /tasks/{id}/export?draft=true`           | 草稿JSON，文件名显式带DRAFT                                                                          |
| `GET /tasks/{id}/artifacts`                   | 实际intake/charges/coverage/validation/events，下载已返回payload；不存在另一个通用artifact内容接口   |
| `GET/PUT /config/{agents\|skills\|mcp\|hooks\|runtime}` | 保存`{expected_version,config}`，编辑与启停先暂存再显式保存 |
| `GET/POST /improvements/candidates`           | 候选与registry；提出时携带来源task、expected_revision、opt_in、scope、before/after与提出人           |
| `POST /improvements/candidates/{id}/evaluate` | 服务端实际固定样例评测，UI展示comparison                                                             |
| `POST /improvements/candidates/{id}/publish`  | 审核人、原因、`approved:true`、`expected_active_version`                                             |
| `POST /improvements/rollback`                 | 目标历史版本、审核人、原因及当前有效版本                                                             |

费用映射首期作用域严格为`accounting_entity`，前端不提供后端未支持的交易方/单据类别选项。评测明确标注合成回归样例；未覆盖别名由后端拒绝发布，不以“评测通过”宣称真实OCR准确率或整体财务提取效果。

## 5. 状态、纠错与体验

业务任务每5秒同步，页面隐藏时暂停轮询。总览、大屏、业务列表和管理页默认只请求任务摘要与health；进入账单详情才读取该task及资产列表，详情页轮询期间另外刷新当前task。摘要和详情保留独立状态，不能用列表投影清空费用、sources和产物。异步详情返回需匹配当前任务，较旧Revision不能覆盖较新人工修订。费用统计优先读取`record_count`，兼容完整详情的`records.length`；`issue_count`保留为服务端问题计数契约。Agent状态由官方SDK独立订阅；不拿业务轮询重造原生线程。

账单详情先展示状态、下一步提示、费用表和原件入口；计划、工具、专家和产物等技术明细按需展开。原生人工中断独立呈现且保持可回答，不能为了折叠日志而卸载订阅或把补充信息表单藏起来。材料新建是独立页面，说明“提交后可离开、稍后查看”的后台处理方式。

修订表单打开时捕获Revision，提交只含修改字段和依据；409时保留输入、禁用再次盲提交，并提示对照最新结果。配置与共享规则发布也携带版本，由后端处理冲突。费用拆分提供高级JSON入口，不在前端自行生成财务拆分算法。

来源保留原始文本和附件关联；图片/PDF可内嵌查看，Excel提供真实工作表/行/单元格结构，Word提供内容结构及可用的派生PDF版式；所有格式均保留原件入口。`waiting_url`明确表示等待OCR下载地址；`partial`表示部分解析。DOCX物理预览页绑定渲染hash，内容锚点不冒充稳定页码。证据引用、修改前后差异和校验预期/实际值可核对，完整原始JSON折叠展示。

暂停按钮仅表示服务端的暂停控制请求；断开进度订阅与取消任务分开。人工审核绑定当前Revision，修改后需重新审核。前端仅在当前版本已批准、有正式费用且未运行时启用正式导出，未确认时提示先确认或下载草稿；这只是交互提示，服务端导出仍重新执行完整业务校验，前端标签、已有审批或高分均不能绕过门禁。

## 6. 面向业务用户的页面重构记录

本次已实现上述页面分层、Hash导航、列表缓存、摘要按页读取、独立材料提交页及管理入口。使用 `design` 与 `stop-that-shit change`；最终 `npm.cmd run build` 退出0，包含Vue/TypeScript与Vite检查，2408 modules，Vite构建段1.71秒。原生流与中断沿用第3节经MCP核对的官方接口。

本轮实际生产页面浏览器记录为 [user-workspace-ui.json](../backend/tests/reports/user-workspace-ui.json)。总览、大屏、业务中心、复核、提交和管理两子页已打开；搜索european进入详情后返回保留筛选，复核清除筛选不跳页。100分EUR任务可直接进入确认，未审批正式导出禁用；1234.56点击打开邮件mail/body原文块，未宣称数值坐标高亮。历史原生中断的回复表单在执行记录折叠时仍可见，未填写或提交。

390×844下总览、列表、详情无页面横向溢出；移动菜单支持Esc关闭并回归按钮焦点，导航后收起。仅在测试标签临时阻断业务API，验证断连提示与旧任务保留，解除后重试恢复；viewport和网络阻断均已恢复。首次加载先显示“正在连接”。最终构建没有新增应用错误，构建切换时旧标签请求旧hash文件的历史错误另记。完整键盘、长表及全部订阅/断线矩阵仍待验；本轮未新建、修订、审批账单或代答历史中断。

![新版工作总览](../backend/tests/reports/user-workspace-overview.png)

![独立大屏总控](../backend/tests/reports/user-workspace-screen.png)

下列记录保留历史页面与业务版本身份，不自动算作本次新验收。

## 工作台清理：全选与删除（2026-10-21）

列表沿用Vue组件和现有样式，首列增加独立勾选，工具栏区分全选当前页和全选当前筛选结果；选择在翻页时保留，搜索、筛选或排序变化时清空，避免删除不可见旧选择。每行右侧可单删，工具栏可批量删除。原生dialog提供确认、取消焦点、键盘关闭及移动端滚动；不同KeepAlive页面使用唯一可访问名称。批量每组最多4个请求，成功项移除，失败项保留并提示；刷新与较早在途响应不会复活同次会话已删条目。

DELETE `/api/tasks/{id}?expected_revision=n`只移除工作台条目，原始材料和管理员Trace保留；不是磁盘清理功能。服务端用已有repository条件写入deleted_at，在LIMIT前过滤用户列表。用户详情/恢复及现有派发检查拒绝已删任务；不改业务revision/审批，不删除官方线程。运行中先暂停，版本或运行状态冲突要求刷新后重选，批量部分失败可以单独处理。

本次使用design、ui-styling和stop-that-shit。相关智能体状态读取先查LangChain Docs MCP的`/langsmith/use-threads`、`/langsmith/background-run`和Agent Server执行生命周期，API Reference MCP检索`ThreadsClient.get`/`RunsClient`；Reference详细get符号未成功解析，另核对已安装SDK的实际签名`threads.get(thread_id, *, include, headers, params)`。运行保护复用官方threads.get/runs.get及既有require_idle，不自建队列、取消机制或Agent runner。工作台软删除是应用记录展示职责，只增加宿主API和存储过滤，不涉及提取业务Skill或新能力发布。

定向20项、最终Vue类型/生产构建、模拟浏览器7组交互及真实GaussDB回滚合成查询通过，实际范围见[验收](acceptance.md#工作台全选与删除2026-10-21)。手机390px确认窗口完全在可视区域内；没有删除真实账单。

## 7. 历史验证：此前工作台与后端联调（2026-10-21）

- `npm run build`通过，包含TypeScript与Vue模板检查；使用Node22.22.3、npm10.9.8。构建版本锁在package-lock。
- 生产`/app/`与Vite代理开发页均已实际打开。空态、服务不可用、真实任务、能力卡片、原件证据与合成费用表经过浏览器核对。
- 真实EML样本导入并创建任务，服务端给出邮件正文与3个附件来源，附件等待可下载OCR URL。首次运行经官方Vue SDK显示原生todos、6次工具调用及`ask_user`中断，问题为补充附件URL或确认部分处理；没有伪造OCR成功。
- 旧合成任务`651c878c-43c7-48ac-bcc8-74cd1abd4c1a`经浏览器修改金额50→51，Revision1→2，服务端报告`LINE_ARITHMETIC`与`TOTAL_MISMATCH`；界面两项费用转为待复核，正式导出被服务端拒绝。该任务为合成材料，不是原题真实账单。
- 随后依据同一合成原件将金额恢复50，形成Revision3且校验通过。另一个仍绑定Revision2的浏览器编辑52提交后返回409，输入与理由保留、禁止盲重试，没有覆盖Revision3。
- 早期Agent Server dev重启后的旧线程水合曾出现计划/中断缺失；后端改用官方AsyncSqliteSaver并完成下述新任务重启验证后，该问题已有明确修复证据。这不构成硬崩溃零丢失承诺。
- 后端切换到官方AsyncSqliteSaver后，新建原始EML任务`29c0ae9b-f792-4b53-b1f8-2423e72d852f`的原生计划、3次主线程工具调用、1个子Agent及嵌套`ask_user`已在Vue SDK中实际显示。当前待处理ID为`30832cf381a3f0f54da6b58e9a2db950`，问题明确说明邮件正文已有证据、3个附件仍缺OCR下载URL；按协作约定保留中断，未提交回复。
- 后端正常停止并重启整服务，`backend/tests/reports/restart-before.json`与`backend/tests/reports/restart-after.json`记录同检查点恢复。合成Excel任务`abab67c9-2fe2-44fe-a416-6dbd92058b26`保留19条消息、3项已完成原生todos及2条已审核记录；上述EML任务保留9条消息、2项原生todos与完全相同的中断ID。消息和检查点比对标记均为true，未自动回复或新建初始任务；该项为后端保存的实际恢复记录。
- 对上述新EML点击断开订阅再重新连接后，相同中断ID、原生计划0/2、主线程3次工具与1个子Agent恢复显示，没有提交回复或新建初始任务。原件栏实际显示邮件部分解析、3附件等待OCR链接；最终页面浏览器错误日志为空。

2026-10-21补充OBS联调：`edfd9e4f-a0a7-4aa5-9349-07eb29169cc1` 使用document-intake 1.1.0新快照。浏览器真实显示邮件与3附件接入后的计划1/3、文档专家协作及调用数，随后显示计划2/3和“待补充”。中断 `3676a55e09e11d5d196a6bb08e5b0e48` 明确询问原文 `SHA pay TAR：H/C $50` 的币种和收费双方，提供补充回复/拒绝入口；未提交任何回复。正式导出按钮禁用，独立API验证正式导出HTTP422。材料接入与覆盖JSON可从产物入口下载，三个附件均有实际OBS上传回执和结构化OCR响应。报告为 `backend/tests/reports/obs-agent-task.json`。

该任务用Demo Trading Ltd作开发演示主体，不能代表真实记账公司。正文1条是候选费用，尚无正式records，因而费用表展示“暂无费用记录”；候选与缺失字段在原生问题和产物中可见。服务的空chargeList未被当作“已证明附件没有费用”，仍保留复核问题。早期正文记录称“USD50”并不构成已确认币种，本轮保留null并请求确认。
- 反馈候选`candidate-5c5293d634e844452840`已由浏览器明确opt_in创建，映射`Document Charge → Documentation Fee`、主体`Demo Trading Ltd`。实际服务端固定合成评测由基线5/7变为候选7/7，engine为`langsmith-local`，含独立最终样例用途记录；该结果不表示真实材料或OCR准确率。浏览器通过填写明确标注合成验收的审核人、理由与确认框，将其发布为`v-7b94d50f56172a55`。
- 同一浏览器随后选择历史`builtin-v1`，填写合成回滚原因与确认框，服务端恢复当前有效版本为`builtin-v1`。候选、评测、发布和回滚记录均保留，已有任务不被改写。

前端不包含业务单元测试副本。本轮使用类型/生产构建与真实API浏览器交互验证；文档与测试结果需要随实际运行更新。


## 历史验证：Office原文与置信度复核

费用表增加分值列，侧栏展示编号、费用名、金额和币种的原文支持、评分组件及blockers。当前v2为字段来源、一致性、覆盖三组；历史v1六项结果仍按后端原契约展示，不在前端换算。分数注明是证据与规则支持度，不是统计正确率。原文总额、数量×单价和币种校验来自后端唯一业务实现。高分且无硬错误时显示“确认当前版本”，不强制先打开来源；确认仍调用真实审批API。

金额、字段分或来源引用打开材料抽屉。Excel精确值唯一时定位单元格，金额相同或无列证据时只定位行；Word可切换派生PDF与内容结构，PDF仅在真实页映射和唯一上下文中高亮金额。缺坐标或没有对应金额时明确显示仅原页/内容，不在别的行猜一个相同数值。

抽屉可进入原有修订弹窗并预选字段。修订生成新revision、重新计算分数与财务结果、清除旧审批；候选投影保持只读。固定答案合成UI样例与实际Qwen提取分开记录，最终闭环报告为 `backend/tests/reports/office-confidence-ui-final.json`；早期 `office-confidence-ui.json` 保留旧schema错误复现。

此前浏览器任务 `bcc84dbf-6915-4faf-baa7-d216804a9426` 固定v5能力和合成答案，无模型/OCR调用。R1的100分结果未打开预览即可直接确认；点击金额50定位Word原件后从窗口修订为60，生成R2、评分60、旧审批失效，金额/总额Hook拒绝批准（HTTP422）。原件仍为50，PDF不高亮当前错误值60。改回50生成R3，校验通过、恢复100分且保持未审批，显式重新确认后审批绑定R3。该记录属于旧v1评分，不作为本轮v2浏览器联调证据。

为保持阅读位置，置信度仅在真实业务内容、模型/工具计数或预算超限状态变化时刷新；列表和详情的run_status投影不同不会每5秒清空分数。抽屉使用稳定内容签名，同revision的来源或费用实际变化会清除旧定位再请求；相同轮询快照不会销毁PDF或重置用户所选视图。

### 无模板海外材料的v2呈现

置信度v2联调阶段沿用当时的tokens和面板层次，新增“数量与单价核验”“原文总额核验”两行，直接呈现服务端 `signals` 的通过、暂无依据、未通过及原因；缺少操作数或总额不会被界面描述成已通过。`review_route`显示直接确认、建议查看原文或先处理阻断问题的建议，不代替真实审批条件。本次页面重构保留该数据契约，视觉方向以本文第1节为准。

字段解释支持后端 `observations` 的原文、候选取值和原因，字符串及对象候选均可呈现；界面不猜金额、币种或规范值。`signals/observations/review_route/fusion`为可选类型，旧v1结果可继续显示；内部融合实现术语不直接展示给业务用户。原文歧义或缺来源的硬拦截仍由服务端统一evidence Hook处理，批准/正式导出422，不能仅凭页面高分放行。

本轮已使用 `design`、`ui-styling` 和 `stop-that-shit change`。`npm.cmd run build`退出0，包含Vue/TypeScript检查和Vite生产构建；Vue SSR固定数据验证通过，覆盖旧v1、新核验状态、不可用原因及字符串/对象候选，无 `[object Object]` 呈现。后端策略与合成差分见[海外融合研究](research/global-extraction-confidence.md)。

后端skills已通过CAS发布v6，快照 `0dd7d9b036a29571747e`；最终离线全量为353 passed、43 warnings、4 subtests passed（220.45秒），报告为 `backend/tests/reports/global-confidence-publication.json`、`global-confidence-pytest.txt`及同名XML。该结果不替代本轮新增浏览器或在线模型交互的实际回执。

v2真实浏览器记录为 `backend/tests/reports/global-confidence-ui.json`：欧洲邮件两条1234.56/65.44 EUR、100分，面板展示没有单号/操作数、独立原文总额通过、70/20/10评分，点击金额打开mail/body原文内容块。`$1,234`样例显示空金额、待确认币种、PENDING_REVIEW与24分，并保留原始引用。前端错误日志为空；未提交人工确认、修订或历史中断回复。对应评分/原文/复核截图为同目录 `global-confidence-score.jpg`、`global-confidence-source.jpg`、`global-confidence-review.jpg`。此EML预览为块级定位，不宣称数值坐标高亮；原文数字解释仍在后端唯一实现。实际Qwen和门禁结果见[验收](acceptance.md#无模板海外提取与融合v22026-10-21)，不作独立真实金标或阈值校准证据。

浏览器已查看Excel的Charges第3行D3=50及Word版式中的金额50：

![Excel金额定位](screenshots/office-confidence-excel.jpg)

![Word版式定位](screenshots/office-confidence-word.jpg)

最终R3的实际Word金额定位（原文50，唯一上下文高亮）：

![Word最终原文定位](screenshots/office-confidence-word-final.png)
**2026-10-23 助手上下栏压紧。** 标题栏内边距8px、图标24px，输入文本区44px；发送栏及外围留白同步收紧。桌面实测标题约41px、输入框约83px，比此前两区合计减少约75px，加上外侧留白收紧，中间聊天记录增加约80px。总面板高度沿用桌面480px/手机440px，常驻输入、待办与发送行为保留。Vue类型/生产构建通过；现有账单多行草稿输入后清空，未发送，390px无横向溢出、控制台无error。未跑后端测试、全量或模型/OCR，未启停后端。截图：[桌面](../backend/tests/reports/compact-chat-bars-desktop.png)、[手机](../backend/tests/reports/compact-chat-bars-mobile.png)。

**2026-10-23 状态提示修复。** 已批准/完成账单的列表run_status可能仍保留pending，而原生线程已idle。taskIsProcessing改为沿用taskCategory的业务状态和当前revision审批优先级，不把普通聊天run或旧pending标记当作材料处理；已批准行显示“当前版本已批准，可查看或导出账单”，已完成行显示核验完成说明。共用该判断的详情处理态/操作可用状态同步一致。5项定向离线检查与Vue类型/生产构建通过，实际账单列表只读核对正确且控制台无error；未改后端/账单/审批，未跑全量或真实模型/OCR。截图：[修正后的实际列表](../backend/tests/reports/bill-status-attention-fixed.png)。

