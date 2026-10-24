**2026-10-24 用户确认：助手与左侧费用面板等高。** 覆盖之前按窗口/文档起点计算高度的约定；桌面两列同一Grid行拉伸，随页面滚动，消息保持内部滚动，手机单列使用独立窗口比例高度。删除AgentPanel的JS高度、ResizeObserver和resize监听。合成页面修复前左右826.01/417.23px，修复后均826.01px，原文展开后均969.14px；1280/1440宽与滚动对齐，390手机无横向溢出，输入区可达，控制台error为空，Vue类型/生产构建通过。详见design-qa.md及assistant-equal-height-desktop.png。

**2026-10-24 文档交付：项目首页与逐项答辩。** 根README已按证据驱动、有界执行和版本化审核重写；docs/project-solution.md逐条回应原题10项验收，采用问题、解决、理由、增强路径结构，解释指定LLM+OCR与按需VLM取舍、长上下文组织、实际源码与历史测量边界。阅读版为output/pdf/Harbor_项目方案与笔试答辩.pdf，生成脚本docs/scripts/build_project_report.py从Markdown排版，使用ReportLab及Windows等线字体（文档工具，不增加后端依赖）。本轮只做文档与PDF检查，未跑全量、未新增真实模型/OCR、未启停后端。已有测试数字保持历史范围，不将2/4开发测量、缓存本地回放或合成UI当作最终准确率/线上性能。

**2026-10-24 最新：Folio界面落地与用户反馈修正。** 采用docs/design/precision-ui-20261024/folio.jpg方案3，横向导航、紧凑字体、灰白/深蓝色与ECharts统计取代前版侧栏布局。海景复用真实摄影并按比例WebGL扰动，现融入页面顶部渐隐背景，随内容滚走；仅导航固定48px/手机50px，覆盖历史“海景也固定”的约定。日期可直接选起止日并联动图表/列表，保留7天/30天/全部。助手列clamp(380px,31vw,560px)，高度按窗口及文档起点适配，正常文档流、滚动不拉长；覆盖历史318px和480/440px上限。六字段、待办、常驻聊天、缺失留空和SDK消息顺序不变。21项定向前端离线检查及最终类型/生产构建通过；合成128条分析/两费用详情核对桌面/手机、日期68条、海景滚动离开、开关冻结。未跑全量或真实账单/模型/OCR，未启停现有后端。核验和迭代见design-qa.md及docs/design/folio-implementation-20261024；代码分阶段推送私人仓库。

**2026-10-24 最新：海洋工作空间改版。** 按用户批准的第一张修订图在原Vue工程实现全宽固定海景页头、连续浅雾绿侧栏及全站灰白/海绿主题。宽桌面费用与证据在左、318px常驻助手在右；默认六字段，置信度并入费用名，标题/摘要收紧，面板操作仍在本面板内。海面缓慢位移与光影、页面进入过渡可关闭并持久化，系统减少动效优先。原文抽屉同步配色；真实浏览器发现PDF.js全局.sidebar覆盖导航，已将应用类名和宽度变量隔离，打开原文后桌面200px、平板184px仍与主体对齐，手机菜单242px可开合。助手高度480/440px、固定页头与六字段实测，无页面横向溢出、error日志为空。14项消息/状态定向离线检查、最终Vue类型/生产构建通过。使用明确合成数据的开发专用真实App预览，不连接后端/模型/OCR；后端2024监听0，未跑全量或业务写入联调。方案与安全素材见docs/design/ocean-ui-20261024，完整并排比较/迭代/验证边界见根design-qa.md（passed）。实现与修复分阶段提交推送私人仓库。

**2026-10-24 最新：前端聊天同步与消息顺序修复。** 账单12的“你好”后台已回复，但非空旧SDK投影挡住了最新检查点；本地提问又可能追加在回复后或依旧锚点跳入上一轮。现按原生检查点顺序与message.id衔接实时投影，补齐漏到的回复；原生chat-user优先，发送锚点和response_message_id用于未同步时定位，同一提问不重复。底部跟随观察实际展示消息，向上阅读不强拉底部。14项相关前端离线检查、Vue类型及生产构建通过；账单12页面已看到提问后接答复，实际AgentPanel合成预览验证增量/回填顺序及底部/历史滚动。临时预览已移除，未跑全量或新增模型/OCR、未提交真实聊天/修订/确认、未重启后端。继续使用官方SDK订阅，不改业务revision或历史消息。查证与验证见[界面记录](docs/ui-design.md)。

**2026-10-24 最新：按用户要求精简常规处理。** 简单提取、多文件对照、问答和局部修改不再强制写计划、委派专家或调用prepare_export。主控save默认完成证据/金额/关联/历史/评分代码核对，读回执即可答复，宿主保存结果；分批显式finalize=false，专家默认暂存。新写入仍使旧核验失效，缺失不补造、冲突不放行，预算/人工锁/证据/revision/审批门禁保留。低分Decimal反馈改为JSON兼容回执，避免无法解析后又回模型；reply_id通过InjectedToolArg隐藏，由ToolRuntime与宿主回合绑定，不让模型抄内部编号。提取Skill2.2.4/config40去掉例行导出要求，历史快照不迁移。103项相关离线检查分批通过；合成两文件批量读→保存核对→答复3次模拟HTTP，已授权删除1次，合法失败提案重试0次；不是线上性能结论。未跑全项目或真实模型/OCR，代码分阶段提交推送。最终单实例PID21192/2024已正常重载，/ok=200、busy=0；账单7的revision/字段/原件/usage等与修改前快照一致。过程见[收敛记录](docs/research/bill7-conversation-convergence-20261024.md)。

**2026-10-24 账单7真实会话闭环与停止/重试收敛。**新问题优先于旧待办；旧业务问题改为非阻塞提醒，模型可自主读取、判断和ask_user确认删除。旧回复ID不能复用为新回合回执；已有账单的聊天/中断回复通过revision修订，不重做提取；合法提案使用官方wrap_model_call短路，直接提交重算，不再支付结束语调用。累计计量不清零，明确人工消息/重试/继续获得有限新回合（当前6模型/16工具/720秒活跃），自动续跑不增额，预算Hook与派发同源。真实同一账单识别空HBL费用→确认删除→停止暴露提案收口缺陷→同一失败请求零模型重试成功，R2→R3、主体及保留费用不变、原件/intake不变、next/interrupt为空，重复成功请求不重复修订。最终completed_with_gaps、approval=null，币种证据仍不足，草稿200/正式导出422；不能当作整单验证通过。联调新增16模型/14工具/81.497秒活跃，含两次在线定位失败轮，新远程OCR0；31项常驻会话及55项既有会话定向离线检查分批通过，未跑全项目或批量真实测试。代码分阶段提交推送，新后端单实例已重载。旧todos/历史info保留的边界及完整回执见[账单7收敛记录](docs/research/bill7-conversation-convergence-20261024.md)。

**2026-10-24 账单6主体回复修复（离线通过，待重载）。** “本次记账主体是TAR。”被ROLE的TAR/SHA规则挡出零模型快路径，ar右边界又误匹配TAR后缀放行未授权交易方修改；模型漏op时list[dict]未作原生子项校验，human-review拒绝后将回复终结。现正确区分公司名称与角色，并用原生TypedDict披露必填set/delete/split枚举，格式错交框架回传纠正，不猜操作/字段。19项定向离线检查通过，未跑全量/真实模型/OCR、未重启后端。原账单6仍incomplete/R1，原生线程已结束，未重放或修改历史记录。详见[账单6排查](docs/research/bill6-reply-fix-20261024.md)。

**2026-10-24 账单4单次真实闭环已结束。** 修复暂存投影将缺省列表写null导致首次保存崩溃，以及人工结构化回复丢失费用ID/不支持数量、拒绝后误标完成两类缺陷。27项定向离线检查通过，未跑全量。唯一新建验证任务a43744d3：首次保存通过，两轮修复后停止进入原生中断；补修后人工回复1次模型生成R2并重算；最终无原生待执行/中断，完成审核但明确completed_with_gaps、validation=false、approval=null。2项费用名引用及1项合计问题暂缓，草稿2条PENDING_REVIEW可导出，正式导出422。全任务14次模型、11次工具、活跃106.796秒；969.261秒墙钟含中途修复/测试/重载/等待，不代表纯耗时。OCR命中缓存，没有新远程OCR HTTP。原账单4完整比较未变化。代码分阶段提交推送，详见[真实修复与验证](docs/research/bill4-runtime-fix-20261023.md)。

**2026-10-24 账单4单次在线联调补修。** 同一验证任务首次保存已通过并在两轮修复后真实停止；人工回复发现旧结构化判定丢失多费用目标/不支持数量，拒绝后又被误标完成。现保留逐项charge_id，支持数量/单价清空，未明确目标回原生handler，可恢复拒绝按既有预算纠正。10项定向离线检查通过；真实同一任务恢复待验证，未新建第二条账单。详见[修复记录](docs/research/bill4-runtime-fix-20261023.md)。

**2026-10-23 账单4首次保存异常修复。** 进度记录读取缺省字段后，Redis暂存mutate_fields误将未修改的空投影合回任务，candidate_digests变null，首次保存TypeError。现与SQL仓库一致仅写实际差异，保留显式清空和嵌套修改。17项定向离线检查通过（含真实暂存+保存工具路径），未跑全量。真实单次生命周期尚待验证，详见[账单4修复与验证](docs/research/bill4-runtime-fix-20261023.md)。

**2026-10-23 最新：私人仓库基线与财务智能体收敛。** 先建立并推送私人GitHub仓库d001121/financial-billing-agent，基线30be1a6；源码、锁文件、配置模板入库，密钥、业务原件、依赖与本机报告留本机。随后分阶段提交：DispatchPolicy通过既有条件事务持久化高成本调用身份/事实摘要，拦截图重建及并发重复派发，未知结果不盲重试，原生有界网络重试/嵌套中断保留；agents v16启用原生task的结构化委派契约，宿主注入真实版本/候选/预算并限制专家工具及保存范围；ExpertHandoff复用原生structured_response，拒绝非法格式、假引用/假保存及无引用修改建议，不额外调用模型修格式。隔离专家独立pin必需document-extraction，修复首轮工具未披露。沿用现有图/待办/共享预算，不新增监督Agent、runner或固定财务DAG，不重写材料。最终45项定向离线检查通过（24.18秒），只用模拟HTTP与隔离存储；未跑全量/真实模型/OCR/正式数据库并发，未启停后端或迁移历史账单/能力，重载后新任务生效，未证明在线提速/总体准确率。详见[智能体收敛记录](docs/research/delegation-convergence-20261023.md)。

**2026-10-23 最新交互：聊天输入框常驻，待办独立提醒。** 覆盖下文历史“仅人工中断显示输入框”的约定。用户可随时提问或明确修改字段，处理中可写草稿、当前运行结束后发送。复用同一原生线程和reply端点：普通消息启动新input回合，待答问题仍按实际interrupt ID恢复；自然语言修改继续经human-review生成新revision并重算，普通问答保持账单状态/审批/导出。助手标题下显示待回复数、未完成原生todos及处理异常，点击待办定位输入；无关聊天或改其他字段后，未解决问题仍保留为原生中断，明确回答/暂缓后才收束。共享预算、暂停、并发和版本检查保留，不新建runner或队列。24项定向离线检查通过（16项新用例与8项既有会话回归，分批执行；包括完整middleware栈普通问答/修订，以及待办恢复后再次暂缓），Vue类型/生产构建通过。真实账单只填写后清空草稿；待办与处理中状态用独立合成Vue预览核对桌面/390px、聚焦、发送禁用及无横向溢出，临时预览已移除。未跑全量、真实模型/OCR，未启停/重启后端；后端会话改动需运行进程重载后使用。详见[常驻聊天记录](docs/research/persistent-chat-20261023.md)。

**2026-10-23 界面微调：账单助手窗口缩短。** AgentPanel桌面高度上限640→480px，手机580→440px，保留360px最小高度及原有内部滚动、标题/输入区布局。Vue类型检查/生产构建通过；浏览器实测桌面480px、390px手机440px，手机面板宽345px且无自身横向溢出。未跑全量或模型/OCR，未启停后端。截图backend/tests/reports/shorter-assistant-desktop.png。

**2026-10-23 界面更新：操作归属各自面板，统一灰绿配色。** 按用户纠正取消临时浮动操作栏及多色分区：账单确认/导出/任务控制/总结纠错集中在账单标题右侧，费用修订/拆分/删除集中在所选费用标题右侧，均为普通文档流。保留全局顶部导航原有固定行为；去除费用行及页脚重复操作。会话、费用清单、参考材料与原文复核使用同一浅灰绿标题/中性边框，通过间距和层级区分；只有主操作、选中项及状态保留语义色。更多信息页同样可访问所选费用操作。使用Product Design插件的现有产品上下文/局部修改准则，并沿用design和stop-that-shit。前端Vue类型/生产构建通过；浏览器核对桌面及390px、费用切换、修订表单打开后取消、更多信息切换，操作组position=static、浮动栏节点为0、手机两组均无自身横向溢出，当前账单3个页头按钮同行；控制台无error。未提交真实账单修订/确认/拆分/删除，未跑全量测试、未调用模型/OCR、未启停后端；临时浏览器尺寸已恢复。截图见backend/tests/reports/sectioned-bill-{header,desktop,mobile}.png。

**2026-10-23 界面更新：费用置信度与原文紧凑排版。** `ConfidencePanel.vue` 将总分/核验状态并入标题栏，六字段按容器宽度自动采用六列/三列/两列，减少重复“有原文依据”文本；低分/歧义提示保留，金额原文取值按需展开。`TaskWorkspace.vue` 将修订/拆分/删除移到所选费用标题旁，原文默认折叠；展开后双列展示，最大320px独立滚动，仍可查看全部引用；核对依据继续折叠。Vue类型检查/生产构建通过（2504 modules，入口index-AAacYX22.js）。在现有账单只读界面核对六字段、9处原文展开、修订表单打开后取消；390px下当前区域345px、两列且无自身横向溢出。截图见backend/tests/reports/compact-confidence-desktop.png和compact-confidence-mobile.png。未提交修订/审核/拆分/删除，未调用真实模型/OCR，未跑后端全量测试，未启停后端；浏览器临时尺寸已恢复。

**2026-10-23 最新：自动历史账单检索已集成，正式服务未启动。** 核对原题验收第5/7项后，常规提交默认 `history_mode=automatic`，不再要求手填已有账单JSON。宿主一次完整投影查询，`billing-reconciliation 1.4.0` 按原有四级顺序筛选同主体、已完成且当前revision校验通过的CREATE/UPDATE历史费用；缺主体等待补充，删除/拒绝/未解决记录不参与。唯一重复为NO_CHANGE，无匹配为CREATE，明确更新指令才UPDATE并继承未改字段；多候选/重复复用/分支更新进入复核。精确父revision lineage避免把已更新父记录当作并列候选，回执绑定主体/revision/候选摘要，批准和正式导出前历史变化或查询失败均阻断。复用既有工具/Hook，不新增模型或OCR请求，不修改历史账单。显式提供旧账单的API及无history_mode旧任务保持原范围。skills v37；59项相关离线检查通过（财务/历史/版本43、宿主15、SQL构造1），Vue类型/生产构建通过。未跑全量、真实模型/OCR/正式历史SQL，未重启后端或迁移历史任务；本地历史提案不代表外部财务记账或跨任务原子提交。详见[自动历史检索记录](docs/research/automatic-history-20261023.md)。

**2026-10-23 界面补充：经验总结表单布局更新。** `ExperienceLibrary.vue` 将来源选择与备注标签分别布局，“选填”保持同行，下拉框固定44px、备注框起始104px，来源版本/主体提示移到选择框下方，新增字数提示及确认入库说明；沿用既有生成与重试行为。类型检查/生产构建通过；独立合成预览验证来源选择、备注计数、未选择时生成禁用、390px单列无横向溢出，并核对既有顶部sticky在滚动后仍为top=0。未跑全量测试，未调用真实模型/OCR，未启动正式后端。

**2026-10-23 最新：置信度按证据强度梯度计分，单号不再因“原文里出现过”就得 100。** a5（Pre-Alert）的单号 `SSZSE26093128` 只由邮件主题 `PRE-ALERT SSZSE26093128` 支持，旧算法对 supported 一律给 100；金额/币种缺失给 0，所以面板只有 0/100。`billing-confidence 3.1.0` 改为梯度：supported 基础 0.85，唯一原文位置 +0.05，结构化字段/表格单元格 +0.10，两个以上独立来源一致 +0.05；全部引用都是邮件主题/头部而字段应来自单据正文时 −0.45。评分不依赖 `B/L NUMBER`、`MBL NO.` 这类固定标签名——不同单据叫法不同，哪个印出的号码是本笔账单的单号仍由模型按具体材料判断。ambiguous 0.40（格式）/0.30（位置），矛盾 0.10，缺失或不可用 0。总分的 `field_support` 组改用梯度值 `70×(0.45A+0.35C+0.20N)`，100 只有三个核心字段都满分且约束、覆盖组通过才可能。`evidence-linking 2.1.3` 把 block 的 `kind`（含 table/cell）带到已校验引用，供评分识别结构化来源。`document-extraction 2.2.2` 删除“从邮件主题 `PRE-ALERT <token>` 自动填 `reference_no`”的固定规则：不同单据的单号叫法和位置不同，取哪个号码仍由模型按具体材料判断，模型未提供则保持 null。a5 离线预览：单号 45 分并进入 `review_items`（原因“仅邮件主题/头部支持，未在单据正文核对”），总分 33→22.6；前端在复核项中优先显示该原因。skills 配置 v36。验证：billing-confidence **60 passed**，evidence+confidence **166 passed**，version/config **42 passed**，skills/host/conversation/codex/version/config **511 passed**；Vue 类型检查与生产构建通过（`index-BsyaD3vl.js`）。历史任务仍按固定能力快照显示，新任务使用 v35；未重跑真实 OCR/Qwen，未改 a5 历史记录。

**2026-10-23 最新：布局财务行金额只取金额列，数量不再拼进“原文”。** 金额详情出现“原文 65.00 1.00”：版式财务行按 `rate 65.00 | quantity 1.00 | amount 65.00` 打印，`evidence-linking` 的数字正则允许数字之间带空格，把 `65.00  1.00` 当成一个数字 run（无法解释），置信度面板原样显示该片段。`evidence-linking 2.1.2` 修复：①同一 run 内的空白只有在构成三位分组（如 `1 234,56`）时才并入一个数字，相邻列拆成独立 token；②`pdf_layout_financial` 引用按列取支持：金额取该行最后三个数字中的最后一个、单价取倒数第三个、数量取倒数第二个，只有本列数字能支持该字段，费率与金额相同时不再算“多个原文位置”；③该字段的观察列表只显示所属列。skills 配置 v34。验证：evidence-linking **103 passed**（新增相邻列拆分、分组数字保持、布局列归属用例），evidence+confidence **165 passed**，skills/host/conversation/codex/version/config **510 passed**。历史任务仍按固定能力快照显示，新任务使用 v34；未重跑真实 OCR/Qwen。

**2026-10-23 最新：重复提取不再叠加重复费用行。** 会话a1（`ebd6860a`，Debit Note，3笔费用）在 24 次模型调用后 `budget_exhausted`。轨迹显示模型多次 `save_document_extraction` 修正币种和收付款方，但批次未带稳定 `charge_id`（或带已失效的旧 id），`merge_extraction` 按追加处理，同一来源出现 `ch_001..003` 与 `charge-...` 两套费用；重复行使 `TOTAL_MISMATCH` 反复出现（1410.40 对 6 行合计），模型继续保存，形成循环。另有一个占位 `document_id=doc_debit_note_001` 与真实 `dc-108478` 并存，把金额拆成两个 scope，重复 totals 也无法按键去重。`human-review 2.0.6` 修复三点：①同一来源、费用名、金额、币种唯一匹配时，匿名候选或已失效的旧 `charge_id` 复用已保存行的 id，并保留其 `document_id`/`line_id`；匹配不唯一、或 line/document 身份冲突时不合并；②同一来源只有一个已知 document 时，把占位/缺失的 `document_id` 归一为该 document，重复 totals 按键合并；③`save_document_extraction` 的匿名纠错计数改用证据中的来源，并且只有不新增 chunk 的保存才计入 `repair_rounds`，使“同一来源最多两轮自动纠错”真正生效。skills 配置 v33。验证：human-review 定向 **24 passed**；skills/host/conversation/codex/version/config **508 passed**；会话a1已保存数据离线回放（6行→3笔、document 统一 `dc-108478`、totals 1 行、`TOTAL_MISMATCH` 消失）。未重跑真实 OCR/Qwen，未改 a1 历史记录；历史任务不迁移，新任务使用 v33。

**2026-10-23 补充：进化库使用总开关。** 顶部“使用已确认经验”控制Agent是否检索，默认开启，复用既有runtime配置API持久化/CAS，runtime v7新增严格bool字段use_reviewed_experiences。关闭后新任务快照不带经验，已有工具每次检索前核对实时开关并返回空结果、不记引用；任务上下文同步显示关闭和0条。保留草稿总结、卡片和单条停用，不影响费用映射执行规则。重新开启不向旧快照新增经验，已进入上下文的内容无法撤回。仅12项相关离线检查通过（11+1）、Vue类型/生产构建通过；合成浏览器验证关闭、刷新保留、重新开启，截图experience-usage-switch-ui.png。未跑全量/真实模型/OCR，未启动或重启正式后端。详见docs/research/experience-library-20261023.md补充段。

**2026-10-23 最新：进化库源码完成，在线未验。** 经用户批准，将“经验与规则”改为AI总结纠错卡片：账单详情“总结这次纠错”或控制台选来源，补充说明可选，原生结构化输出预填内容，人工确认后才启用；主体、来源和revision由服务器绑定。后续同主体新任务通过原生工具按需检索最多3条，使用官方BM25Retriever，无额外模型/向量请求；快照固定内容，停用/版本变更阻止后续返回，实际引用回执不冒充采纳或准确率。历史金额、币种、单号、付款方式和AR/AP不能替当前原件补值，缺失仍null。原有费用映射评测/发布/回滚保留在“执行规则”页签。feedback-improvement1.4.0，skills v32/agents v13/runtime v6；每次总结最多1次模型HTTP、无自动付费重试，成功复用，失败需明确重试并记录调用/token。定向离线27 passed（11.65秒）、Vue类型/生产构建通过，独立内存模拟API完成草稿/启用/停用/规则入口界面核对。未跑全量、真实模型/OCR或正式数据库新接口，未修改真实账单和既有发布目录；未证明总结质量或准确率收益。硬终止可能留下running生成回执，未实现自动恢复。详见[进化库记录](docs/research/experience-library-20261023.md)。

**2026-10-23 最新：第4项抽取与第8项Harness修复（源码完成，最终在线未验）。** Codex已配置官方docs-langchain/reference-langchain并实测查询，官方安装器安装22个项目Skills。document-intake1.8.0复用原生RapidOCRBlobParser补图片全文，指定远程OCR仍必需；document-extraction2.2.1修正裸符号币种schema、表头证据、真实费用与条件/Free条款，保持单一提取Skill；human-review2.0.5修同一费用局部修订丢单号（省略保留、显式null清空、换身份不继承）；feedback-improvement1.3.0新增完整行多重集合评分并补关键单据号。skills配置v31/agentsv12/runtimev6。四原件开发标注7笔，未经独立人工批准；修复前真实模型+真实OCR历史回放仅2/4材料包字段全匹配，图片丢编号及EML额外0金额行如实留在回执。用户明确禁止后续全量/批量真实模型测试，随后只做18项小范围离线检查，全部通过；未跑修复后在线回归/全量，未声明总体准确率。评测入口默认离线，真实模型必须显式单case；修复LangSmith异步本地评测意外上传的配置，离线单例验证无LangSmith请求。正式服务只读64线程/0busy、health degraded，按用户指令不处理连接，不重启/发布新能力；历史账单保持原版本。详见[本轮记录](docs/research/extraction-harness-4-8-20261023.md)，下文全量/旧能力/进程记录保留历史范围。

**2026-10-23 最新：远程 OCR 等待、内容缓存与重复工具轮次优化。** 用户授权直接优化；远程服务不在本机，本轮未改远端、未再请求在线 OCR/Qwen。`document-intake 1.7.0` 在既有 Skill 内按文件内容/端点/请求参数/服务契约版本缓存成功原始响应，filelock 跨进程合并相同在途识别，命中跳过上传/签名/HTTP；TTL 默认86400，失败/过期/损坏不复用，任务各自重建来源与原页证据。PDF 本地初读先存只读预览并通过原生 custom 流显示进度，Vue useChannelEffect 接收；未核对内容不作正式账单。`document-extraction 2.2.0` 对已有 PDF 表示短路并保留哈希校验，局部候选不再用默认 null 覆盖未提交字段；evidence-linking 2.1.1 修同一位置全名/子串假歧义；human-review 2.0.4 修过时主体告警和单据头字段合并；billing-confidence 3.0.1 修作用域/info/独立总额支持。无 coverage 也执行两轮/无进展限制，人工新 revision 重置；空 tool_call id 在 ModelResponse 内修复；减少独立 todos 轮次，增加模型/token/OCR/刷库回执，列表对异常/过期 summary 按当前检查点校正问题。skills v30、agents v12、runtime v6，新能力 c16c912c031923ddbb8f。真实三页 PDF+此前真实响应离线回放：缓存完整接入0.877699秒，发布能力独立进程1.752991秒，均无网络请求；这不是在线模型端到端提速，首次远程冷请求此前实测208.739338秒仍可能存在。只回填此前实测且哈希/响应验证一致的一个原始响应，保留原收到时间，历史账单未重算。验证：定向495 passed；全量584 passed/7既有失败（improvement5项旧payment_term断言、streaming2项夹具缺capability）；增补原生图/总额/版本4 passed、最终列表7 passed，Vue类型/生产构建与pip check通过。经现有start.cmd重启PID13952，GaussDB/Redis健康，64线程ID/状态与会话7账单哈希均保持；未做新在线OCR/Qwen与浏览器长任务验收。详见 [本轮报告](docs/research/ocr-latency-optimization-20261023.md)。

**2026-10-23 最新：账单日期交回模型识别，代码只做证据校验和定位提示。** 会话6（PDF1 General Notice）首次提取的 `document_date=10/19/2026` 本身正确，但模型没有给出 `field=document_date` 的正文引用；`BILL_DATE_EVIDENCE_REQUIRED` 报错后模型把日期删成 null。曾尝试由代码按值自动补证据，但同一单据印有 ETA、截止日、生效日、签发日，字符串匹配会把错误日期也补成“有依据”，等于替模型做语义判断，该做法已撤销。`document-extraction 2.1.6` 现在只做两件事：①日期缺正文引用时保留 error，并在 `date_candidates` 返回该值出现的原文行（source/anchor/quote，邮件头和结构块除外），提示模型核对后补引用或改正日期，并明确不要因缺引用删除正确日期；②已有 `document_date` 引用但引用行未印出该日期时记 `BILL_DATE_EVIDENCE_MISMATCH`（warning，不阻断），格式差异和语义判断不交给代码猜测。日期值仍由模型识别；原文找不到该值时 `date_candidates` 为空，只保留原错误。核查 OCR：当前 `orderChange` 响应的 `data.list` 没有任何日期字段（已保存的 99 份响应中日期字段全为空），顶层 `createDate` 是 OCR 处理时间且不会进入材料块，因此本单日期只能来自 PDF 文字层/版式，不能由 OCR 填充。skills 配置 v29。验证：extraction+版本 **59 passed**；会话6真实来源离线回放（读已保存 sources，不重跑 OCR/Qwen）日期保留、未新增证据、返回3条候选行；skills/host/codex/conversation/version/config **476 passed**。未改会话6已保存结果；历史能力不迁移，新任务才使用 v29。


**2026-10-23 最新：Redis 暂存 + GaussDB 阶段末持久化的任务状态。** 新增 `StagedRepository`（`backend/infrastructure/repository.py`）：`task` 读取优先 Redis（未命中回源 GaussDB 并回填），`mutate`/`mutate_fields` 只改 Redis 并加入 `workorder:tasks:dirty`；`flush` 在工具调用结束（`DispatchPolicy.awrap_tool_call`）、Agent 本轮结束（`TaskOutcome`）、人工回复与待答问题（`ConversationReplies`）、API 请求结束（FastAPI `flush_dirty` 中间件）、启动时钟恢复和预算耗尽时一次性写回 GaussDB。非 task 记录与审计事件仍直接入库。刷库使用 `app_objects.revision` CAS 与新增的 `Repository.replace`（不读旧 payload 的全量写）；Redis 不可用时退回直接读写 GaussDB；刷库失败保持 dirty，下一边界重试；版本冲突时删除落后缓存。缓存 TTL 由 `TASK_CACHE_TTL` 控制（默认 3600 秒）。三处 I/O 修复：`check(..., policy_only=True)` 只读 `control/deleted_at/revision` 投影（需要返回任务的调用仍读完整记录）；`save_fields_fast` 用 `mutate_fields` 只改选中字段；`validate_and_store(task_id, task=...)` 复用刚保存的内存任务，`settle_saved`/`reconcile_saved` 不再重复整单读取。验证：新增 `test_repository_staging.py` **7 passed**（缓存读写、字段投影合并、刷库、revision 冲突、Redis 故障回退、批量刷库、policy 投影）；conversation/host/revision_feedback/task_deletion **126 passed**；`backend/tests` 全量 **243 passed、7 failed**，`backend/skills` **322 passed**；失败均与本轮无关（`test_improvement` 5 项使用 MemoryRepository，因 `payment_term` 规则收紧后评测样本仍断言旧值；`test_task_runtime_streaming` 2 项测试任务缺 `capability`，属既有夹具）。未重启后端、未重跑真实 OCR/Qwen；历史任务不迁移。

**2026-10-23 最新：金额合计范围键修复与窗口错误收口。** 会话5（PDF1 General Notice，245 USD）出现 16 次模型调用、5 次 `read_materials`、3 次 save，根因不是模型算术，而是 `validate_amounts` 把 `document_id=None` 的费用行和 `document_id=doc_1` 的总额分到两个 scope，产生假的 `TOTAL_MISMATCH`；模型于是反复读 PDF/grep 找差异，最后删除 totals 才通过。`billing-reconciliation 1.3.2` 在分组前归一 scope：同一来源只有一个 document 时，缺 `document_id` 的行使用该 document；`validate_amounts` 接受可选 `documents`，`reconcile_charges` 传入当前 documents。`document-extraction 2.1.4` 让 `read_materials` 接受 `start_line=0`（按第1行），未知来源错误列出可用 source_id，行号错误带总行数，避免零基行号和 source_id 笔误造成连续无效调用。skills 配置 v27。验证：金额 scope 正反用例、read_materials 窗口用例及完整定向 **420 passed**。未跑全量、未重跑真实 OCR/Qwen；历史任务固定旧能力。

**2026-10-23 最新：intake 清单化与原生 ContextEditing。** `intake_documents` 不再把 `read_materials` 的完整正文放进返回值，只返回来源清单、状态、行数、issues 和“用 read_materials 读取正文”的指令；短材料由 `read_materials` 一次读取，只有 `mode=search` 才走 `/materials/*.md` 的 grep/read_file。四单离线估算：intake 返回块从 9.5k–31.9k 字符降到 260–934 字符。intake 的复用键补上 `OCR_RESPONSE_FORMAT` 与 `ocr_text_pointer`，格式/指针变化会重新解析。`base_stack` 新增原生 `ContextEditingMiddleware` + `ClearToolUsesEdit(trigger=8000, keep=3, exclude_tools=('save_document_extraction','prepare_export','ask_user'))`，清理较早的 intake/read_file 输出、保留最近 3 条与最新校验结果；材料仍在 `/materials` 与任务产物中，可重新读取。runtime 配置升 v6，新增 `context_edit_trigger`/`context_edit_keep`；skills 仍 v26。验证：intake/host/config 定向 **101 passed**（含新增 intake 清单化与 ContextEditing 装配用例），conversation/host/codex/question-policy/version + 六个 Skill 目录 **372 passed**。未跑全量、未重跑真实 OCR/Qwen；后端未重启，历史任务不自动迁移。 `document-extraction 2.1.3` 会从同一来源原文修复缺失/错位的单据头证据（`DOCUMENT_EVIDENCE_REPAIRED`），PDF B/L 若只引用了 embedded 但同一文件版式行印有该值，则补入版式证据而不再报 `PDF_IDENTITY_LAYOUT_REQUIRED`；验证器会重算并丢弃旧的同类 issue，且对 issue 去重。`billing-reconciliation 1.3.1` 补全空格形式的标题归一（`DEBIT NOTE`→`Debit Note`、`GENERAL NOTICE`→`General Notice`、`PRE-ALERT EMAIL`→`Pre-Alert`），从明确的 `A pay B` 原文行补 `debtor=付款方/creditor=收款方`（不覆盖人工确认值），并对 issue 去重；`valid` 只由 error 决定，info 不再把记录强制改为 `PENDING_REVIEW`；`reconcile_saved` 使用本次 evidence-linking 的新 issues，不再沿用旧的顶层校验 issues。`human-review 2.0.3` 在主体已提供后同时清除 extraction 与顶层 `issues` 中的过时主体告警。宿主最终答复在 `validation.ok=false` 时前置“整单校验未通过（N 项错误）”。skills 配置 v26。验证：8 文件定向 **211 passed**（conversation/host/codex/question-policy/version + 三个 Skill），billing-export/billing-confidence/evidence-linking **161 passed**（合计 **372 passed**）；用四单已保存数据离线回放：会话1 `Debit Note`/AR/`CREATE`、会话2 `General Notice`、会话3 `Debit Invoice`、会话44 `Pre-Alert` 且 `creditor=TAR/debtor=SHA`，container 证据不再报错。未跑全量、未重跑真实 OCR/Qwen，历史任务仍固定旧能力，需新建任务才使用本轮版本。

**2026-10-22 最新：签发方水印守卫与角色回复确定性映射。** `document-extraction 2.1.2` 在 `validate_extraction` 中拒绝把页脚/Powered by 平台供应商当作签发方：命中 `湃乐多`、`Pilot Aiship`、`Pai Aiship`、`Powered by` 的 charge/document issuer 置 null，记 `ISSUER_PLATFORM_VENDOR`（warning，原值保留在 issue 中），平台供应商不再进入主体候选。`billing-reconciliation 1.3.0` 允许单边收费关系确定方向：主体等于已知 creditor → AR，等于已知 debtor → AP，未知对侧保持 null；双方都缺失或主体不属于任一方仍记 `POSTING_UNRESOLVED`。`settle_symbol_currency`/`settle_unbacked_parties`/`settle_payment_term` 不再覆盖 `human_confirmed` 字段。`ReplyDecisionMiddleware` 对纯角色回复（“是收款方/付款方/AR/AP”）确定性写入 creditor 或 debtor 与 posting_type，多费用按 `review_request.charge_id` 或全部记录绑定，0 模型调用；`completion_question` 在仅缺对手方时追问具体付款方/收款方，避免重复同一 AR/AP 问题。skills 配置 v25。验证：conversation/version/reconciliation/extraction 定向 **121 passed**，host/codex/question-policy **68 passed**（合计 7 文件 **189 passed**）；未跑全量、未重跑真实 OCR/Qwen，历史任务能力不迁移。

**2026-10-22 最新：主体补充回到聊天内的人工审核。** 缺主体时先保存候选；保存后 `completion_question` 调用 pinned `human-review.entity_question` 打开原生 `conversation_review`，UI 显示聊天输入框和候选公司；用户回复后由既有 human-review Skill 应用 revision。已完成的 `completed_with_gaps` 任务在打开会话时也会自动打开同一 review；移除“补充记账主体”独立按钮。`AskUserPolicy` 仍禁止在保存前用 `ask_user` 阻塞。验证：conversation/codex/question-policy **56 passed**，host/planning/version **62 passed**；Vue 类型与生产构建通过（`AgentPanel-MRC0DFKO.js`）；后端已停止，未浏览器实测。

**2026-10-22 最新：PDF layout 财务行优先与 OCR/layout 冲突校验。** `document-intake 1.6.1` 从 `pdfplumber.extract_text(layout=True)` 解析 `pdf_layout_financial`（保留原始行 + `rows`），Markdown 按财务行→版式→plain→OCR 排序；`document-extraction 2.1.1` 在 `validate_extraction` 比较 OCR `chargeList` 与 layout 行，冲突记 `OCR_LAYOUT_CONFLICT`（候选金额只被 OCR 支持时升级为 error），财务字段只引用 OCR 时记 `PDF_LAYOUT_EVIDENCE_REQUIRED`，以 layout 拆分为准。skills 配置 v24。验证：intake/extraction/version 定向 **105 passed**，排序修正后 extraction/host/codex **113 passed**，conversation **43 passed**，最终版本/新 layout 用例 **4 passed**；未跑全量、未重跑真实 OCR/Qwen。

**2026-10-22 最新：Skill 版本一致性与过期测试修正。** 统一 `skills.yaml` / `SKILL.md` / `scripts/skill.py` 的版本：document-intake 1.6.0、document-extraction 2.1.0、evidence-linking 2.1.0、billing-reconciliation 1.2.0，skills 配置升到 v23。新增 `backend/tests/test_skill_versions.py` 检查三方版本一致；更新 document-extraction CLI 两个过期断言和缺主体集成测试；`human-review/SKILL.md` 同步“缺主体不自动追问，保存 null + PENDING_REVIEW”。验证：版本/CLI/缺主体/document-intake/human-review 定向 **83 passed**（2 warnings、4 subtests），`test_configuration` + `test_host` **95 passed**；未跑全量 pytest。

**2026-10-22 最新：题面标准自检后的四项修复。** 对照题面与样本期望修了四类问题。① EML 裸 `$` 不再被猜成 USD：`billing-reconciliation 1.2.0` 在匹配前执行 `settle_symbol_currency`，`field=currency` 引文只有货币符号且无 ISO 代码时置 null 并加 `CURRENCY_SYMBOL_AMBIGUOUS`；`settle_unbacked_parties` 删除未出现在自身字段引文中的 creditor/debtor 并加 `PARTY_UNSUPPORTED`，再由既有 `POSTING_UNRESOLVED` 进入复核。② 费用映射补 `H/C → Handling Charge`，原始名照旧保留。③ PNG 无主体不再阻塞：`settle_saved` 在已有候选但没有 records 时先调用 `reconcile_saved`，保证 PrepareExport 一定产出账单；新增原生 `AskUserPolicy`（`wrap_tool_call`，查证 Docs MCP）在主体缺失或无候选时短路 `ask_user`；`completion_question` 在调用方未给主体时不再生成实体问题，直接以 null + PENDING_REVIEW 收口。④ `document-extraction 2.1.0` 补回证据位置字段（schema 暴露且 None 不落盘）、负/布尔偏移校验、PDF 单据号需版式层证据（`PDF_IDENTITY_LAYOUT_REQUIRED`），chunk 覆盖测试改为当前 source 级契约。另按版式核对口径补三条确定性规则：`payment_term` 只保留有原文支持的 PP/CC（`C`/`COD`/`PAY IMMEDIATELY` 置空并保留 `raw_payment_term`，不因此强制复核）；`document_type` 用印出标题归一（Pre-Alert / General Notice / Debit Invoice / Debit Note）；Pre-Alert 的 `reference_no` 在缺失时从主题的 `PRE-ALERT <编号>` 确定性提取并生成正文证据；邮件声明的 MBL 与附件印出的 B/L 不一致时记录 `IDENTITY_CONFLICT`（warning，两者都保留）。验证：9 文件定向 **386 passed**；真实新任务 PNG `65786b80…` 产出 2 条 PENDING_REVIEW（5 / 21.9，币种 null，主体/方向 null，无中断），EML `dd2ad064…` 产出 1 条 `Handling Charge` 50、`Pre-Alert`、`reference_no=SSZSE26093128`、币种/付款方式/方向均 null、PENDING_REVIEW。后端重启 PID38236。边界：PNG 的 OCR 响应本身没有币种，不能凭空补 USD；未跑全量 pytest；`delivery` ZIP 仍是 10-21 旧包。

**2026-10-22 最新：人工回复实体句与首轮调用上限。** daca 连续回复“本次记账主体是NEPTUNE SHIPPING LIMITED。”未生效的根因：`with_structured_output` 有时把该句判成 confirm/ask，并返回 `posting_type/payment_term=null` 的占位字段；在 3 条费用下宿主无法绑定 charge_id，`apply_revision` 最终返回 CHARGE_NOT_FOUND。现改为：UI 生成的纯实体句（`本次记账主体是X。`或候选原名）由宿主确定性解析并直接提交既有 human-review Skill，不再调用模型；带收款/付款角色、金额等混合语义仍交模型。模型返回的未提及 `null` 字段直接丢弃（只有用户明确说“没有/留空”才保留），多费用下缺少 charge_id 的操作返回“请指定要修改的费用：…”而不是 CHARGE_NOT_FOUND。runtime v5 新增 `run_model_calls=16`，与 `thread_limit` 合并到同一个原生 `ModelCallLimitMiddleware`（`exit_behavior=end`），单次运行不得耗尽整个任务预算；旧能力无该键时按 `model_calls - turn_model_calls` 兜底。验证：`test_conversation.py` 43 项、conversation+host 97 项、7 文件定向 **168 passed**；新增复现 daca 的多费用实体句图级用例，revision 1→2 且 0 模型调用。后端重启 PID35420，GaussDB/Redis 健康，线程状态不变；真实 daca 尚未重新提交回复。

**2026-10-22 最新：完成审核收口与置信度面板稳定。** 账单在审核后仍有空字段时可显式收口：`POST /api/tasks/{id}/complete-review` 接受 `completed_with_gaps`、`awaiting_review/needs_review/waiting_review/ready_for_review/review_deferred`，写入 `review_confirmation` 并置 `completed`；处理中、待补充、待回答问题与过期 revision 拒绝，重复提交幂等。前端 `完成审核` 在以上状态显示为主按钮。此前该路由只在源码中、运行服务未注册（openapi 缺失），本轮重启后才生效。置信度面板在费用列表短暂为空时曾整块卸载：`TaskWorkspace` 缓存最后一次非空费用并仅在处理中回退使用，`useConfidence` 改为请求序号发布，移除“签名逐字不变才接受”的条件（该条件会在费用频繁变化时丢弃响应，造成分数成批闪现）。验证：`test_host.py` 54 passed（含 3 项完成审核用例）、`test_conversation.py`+`test_workspace_views.py` 42 passed、Vue 类型与生产构建通过（`index-j8OiT12T.js`）；构建产物在 2024 实测任务 1231 按钮为主按钮、面板 6 字段 13 秒 26 次采样未卸载，过期 revision 探测返回 409 未改数据。后端重启 PID 29228，GaussDB/Redis 健康，线程数不变；未点击完成审核、未改真实账单，未做全量测试或真实 OCR/Qwen 重跑。LangChain `docs-langchain`/`reference-langchain` MCP 已配置并实测可用，官方 Skills 安装器已执行。

**2026-10-22 最新：空 tool_call id 归一化。** dada（d4fdc088）三次 `task` 委派报 “Tool call ID is required for subagent invocation”，原因是 qwen 把 tool_call id 输出为空；普通工具可容忍空 id，但 SubAgentMiddleware 强制要求非空。新增 `ToolCallIdNormalization` 中间件：模型返回后给空 id 的 `tool_calls` 补 `call-<uuid>`，保证 AIMessage 与后续 ToolMessage 一致。相关回归 **153 passed**；修复需重启后端生效。dada 当前为 `cancelled`，需恢复/重启任务才能继续。

**2026-10-22 最新：币种符号+上下文推荐与回复收敛。** `document-extraction` 的 currency 描述允许在原文只有符号时，结合航线、交易方国家、同单据其他金额和语言给出推荐 ISO，并在 issues 标注需核对；`evidence-linking` 新增 `recommended_currency` 校验（`$`→USD/CAD/AUD/HKD/SGD 等，`¥/￥`→CNY/JPY，`€`→EUR，`£`→GBP，`kr`/`Rs` 等），匹配时字段 `status=recommended`、`score=40`，不再一律判 ambiguous；符号与推荐 ISO 不符时仍 ambiguous/unsupported（例如 `¥` 不能推荐 USD）。`SKILL.md` 增加“引用被拒只纠正一次、HBL 的 B/L 用该文件自己的号码、不复述试错过程”，主控最终答复只写结果/分数/缺口。Skill 测试 158 passed，后端相关回归 152 passed。现有任务能力固定，需迁移快照后才使用新规则。

**2026-10-22 最新：Skill 驱动流程与执行计划恢复。** `document-extraction/SKILL.md` 写明“接入→阅读→先保存候选→再询问主体/AR-AP→prepare_export”，并说明无候选时先保存候选再重试；`human-review/SKILL.md` 明确无候选的实体回复不应被当作无效 revision，宿主返回可重试错误，由 Agent 保存候选后重试。移除回复轮工具白名单（只保留提案后的终止边界），no-records 拒绝改为 `retryable`；结构化判定在无 records/charges 时回退 agent 循环。`PLANNING_PROMPT` 与 `prompt.md` 恢复 `write_todos` 执行计划语义（按 Skill 流程规划，不以 todo 状态代替产物校验）。新增图级回归：先失败→保存候选→重试→revision 2；相关回归 **152 passed**。后端 PID25496，GaussDB/Redis 健康；1251521512 线程已按原 id 重新注册。

**2026-10-22 最新：P1 通信契约与职责边界。** 两个专家的提示词新增 JSON 结果块（`status/summary/saved/proposals/issues/evidence_refs`），主控按字段验收，config agents 版本 11；`human-review` 与 `feedback-improvement` 无 `include_tools`、由宿主 middleware/HTTP 路由直调，是业务库型 Skill，不参与模型披露；`DispatchPolicy` 的任务级共享计数与原生 `Model/ToolCallLimit(thread_limit)` 分工明确：前者跨父/子 Agent 共享预算及暂停/revision 策略，后者是单线程安全网，二者不是重复计数。另修复原件预览：纯文本来源没有 asset 文件时不再 `KeyError('path')`，直接返回块预览。`test_host` 的 4 个旧用例已按当前 bundle-reading 工具契约更新（`materials/content/reading`、`reads[].added_anchors`，不再断言 `chunks/total_chunks`），相关回归 **151 passed**。

**2026-10-22 最新：P0 标准化整改。** 移除自定义 `SkillResources`：Skill 文件、pin 和 `skills_metadata=None` 改为在 `start_run` 的官方 run input 中传入（`files`/`pinned_skills`/`skills_metadata`），子 Agent 通过原生状态继承 files；回复意图判定从 `ConversationReplies` 拆到独立 `ReplyDecisionMiddleware`，主类只保留 HITL、中断与工具白名单；deepagents 0.7.29→0.7.30（PyPI Python 最新；文档中的 1.15.0 属 JS 版本线），依赖声明同步。验证：run input 含 59 个 Skill 文件、`pins=[document-intake, document-extraction, billing-export]`、`skills_metadata=null`；“我现在不需要主体”回复模型 19→20、工具 14→14、`review_deferred`；相关回归 145 passed，仅 6 个既有失败。后端 PID31444，GaussDB/Redis 健康（首次启动因数据库断连失败，重试成功）。

**2026-10-22 最新：人工回复统一走模型意图识别。** 移除 human-review Skill 的 `interpret_reply`、宿主确定性快路径以及 absence 正则/`clean_value`；候选主体、六字段、确认、暂缓以及“没有/不存在”等语义全部由一次 `with_structured_output(ReplyDecision)` 判定，宿主只做 schema 解析和 human-review 校验/应用，失败或 `ask` 才回退原 agent 循环。直接修订表单和 `/approve` 仍是确定性、零模型。实测 12313213 自由文本“我现在不需要主体”：模型 18→19、工具 14→14、`status=review_deferred`。定向 91 项通过；后端重启 PID25740，GaussDB/Redis 健康。上条 absence 正则与确定性解释路径以此为准。

**2026-10-22 最新：“没有/不存在”语义与字段清空。** 人工回复“单据编号应该是没有的”此前被当作字面值写入 `reference_no`；human-review 的 `interpret_reply` 现在把“没有/无/不存在/暂无/未填写/留空”等识别为该字段的 `null`，宿主在确定性/结构化两条路径再用 `clean_value` 统一兜底，因此已固定能力的历史任务也能正确清空。任务 gafa15 已修正：`reference_no` 从“应该是没有的”变为 null（revision 3→4，模型/工具用量仍 3/2，无模型调用）。定向 45 项通过；后端重启 PID9904，GaussDB/Redis 健康；gafa15 线程因 dev runtime 元数据丢失按原 id 重新注册。

**2026-10-22 最新：人工修订改为纯确定性终态。** `PATCH /api/tasks/{id}/revision` 现在只执行 human-review 的 `apply_revision`、`reconcile_saved` 和 `settle_saved`：直接写入最终字段、生成新 revision、重算校验，不再创建 feedback，也不再调用 `continue_feedback` 启动模型回合。用户提交表单后即得到最终结果；审批路径 `/approve` 同样只做确定性校验与绑定。修订测试改为断言 `post.await_count=0`、`feedback=None`、revision 与状态落定；旧待处理 feedback 的 control/resume 覆盖保留。定向 98 项通过；后端重启 PID20448，GaussDB/Redis 健康。

**2026-10-22 最新：人工修订直达表单与入口精简。** 费用行的铅笔现在直接打开 `RevisionDialog`，不再先进入会话；可编辑费用名称、金额、币种、付款方式、单据编号、单据日期和交易双方，AR/AP 改为可选（待确认/AR/AP）并随修订一起提交。移除“草稿 JSON”和“修改记账主体”两个入口；AR/AP 未确定时的入口改为“补充 AR/AP”并聚焦该字段。已在 12313213 浏览器实测：弹窗直接打开，H/C、50、AR 可见可改，两入口已不存在；Vue 类型与生产构建通过（`index-DfmvgbWl.js`），前端 dist 已生效，后端无需重启。

**2026-10-22 最新：置信度面板字段值与布局修复。** 面板原来只显示分数/依据，不显示字段实际值，并按数据存在的字段过滤，导致费用名称无内容、两列网格留空。现固定六项（AR/AP、单据编号、费用名称、金额、币种、付款方式），从当前 `record` 读取真实值（兼容扁平与分组结构），缺失显示“未提供”，并展示分数、具体原因和原文观测；布局改为单列列表，窄面板（实测约280–460px）不再挤压或留空格。已在 nsfnsf 页面实测：费用名称 H/C、金额 50、币种 USD 均可见，六项齐全、无重复“未提供”。Vue 类型与生产构建通过（`index-61YLJMQV.js`）；前端 dist 已生效，后端无需重启。

**2026-10-22 最新：材料ID注入与工具错误回传。** nsfnsf（94f72a08）失败轨迹显示模型把 asset_id 抄错（`…295a5dfe9b…`，任务为 `…295a46863e34`），`intake_documents` 抛出普通 `ValueError('材料不属于当前任务')`，整个 run 直接 error。修复：`intake_documents` 始终使用当前任务的 `asset_ids`（模型参数仅作提示）、`DispatchPolicy` 把工具 `ValueError` 转成 error `ToolMessage` 交回模型并记录失败调用、`require_idle`/`sync_task`/控制接口容忍重启丢失 run 元数据的 `NotFoundError`。实测重新注册线程后控制重启返回 200，nsfnsf 接入 4 个来源、保存 H/C 50 USD，停在主体提问（5 模型/4 工具），不再报错。定向 48 项通过；后端 PID42688，GaussDB/Redis 健康。

**2026-10-22 最新：自由文本回复改为模型结构化判定。** 精确模板（候选主体、六字段、确认、跳过）仍由 human-review Skill 的 `interpret_reply` 零调用处理；自由文本由宿主发起一次 `with_structured_output(ReplyDecision)`，模型只输出 `{action, fields, accounting_entity, question}`，宿主校验后复用 `record_review_decision` 应用，不进入 agent 工具循环；失败或 `ask` 才回退原循环。实测“我现在不需要主体”：模型调用 17→18、工具 14→14、`status=review_deferred`、回复行无 `decision_error`。定向 45 项通过；后端重启 PID41156，GaussDB/Redis 健康。回执 `backend/tests/reports/deterministic-reply-verification.json`。

**2026-10-22 最新：人工回复的确定性解释下沉到 human-review Skill。** 新增 Skill 入口 `interpret_reply`：候选主体模板（“本次记账主体是X”）、六字段（币种/付款方式/单据编号/金额/费用名称/AR/AP）、确认、暂缓均可确定性解析；歧义、未知值或多记录未指定费用时返回 `deterministic=False`，交回模型。宿主在回复轮先调用该 Skill，命中时直接复用 `record_review_decision` 暂存提案，**不发起模型请求**；记录为空时仍由既有的确定性 reconcile 物化记录。按用户决定保留“缺主体强制追问”，输入框回复“跳过/跳过主体/暂缓/主体留空”由同一 Skill 映射为 `defer`，零模型调用收束为 `review_deferred`；原题要求的 `null`/`PENDING_REVIEW` 输出仍由后续导出保证。定向 44 项通过，既有 6 项失败未变。**实测迁移**：两任务能力 `a1a880d5916fd1359f40` → `56d7a8f78282877161de`（回滚 `backend/tests/reports/capability-migration-before.json`）；dacz 回复“跳过主体”后模型/工具调用 12/9 → 12/9，`status=review_deferred`；12313213 回复“本次记账主体是TAR。”后 17/14 → 17/14，revision 2、H/C→AR，第二条无收付款关系生成定向人工问题（非模型循环），再回复“跳过”后仍 17/14、`status=review_deferred`。回执 `backend/tests/reports/deterministic-reply-verification.json`；后端重启 PID24236，GaussDB/Redis 健康。Skill 从固定 release 加载：新任务自动生效，历史任务需显式迁移能力版本。

**2026-10-22 最新：重建任务实测与新控制流验证。** 新增 `restart` 控制动作（重建线程无检查点时从保留材料起新回合，不伪装 resume；UI 对 `status=incomplete` 显示“重新处理”）；`record_review_decision` 对“payload 是修改但 action 标成非 edit”的情况按 payload 纠正为 edit，不再整轮拒绝。实测：12313213 主体核对无模型调用开中断，回复轮 2–3 次模型调用、无重复、无递归，模型未按 edit 提交时 `decision_error` 正常收束；dacz 重新处理 4 次模型调用停在 ask_user，回复轮 3 次调用后模型反而询问 reply_id，未应用主体。结论：控制流边界已生效，剩余问题是 `qwen3.7-flash` 对 action 语义和内部 ID 的遵从，后续可对“点击候选主体”做确定性应用，不依赖模型解释。

**2026-10-22 最新：完整控制流加固与启动性能。** 新增 `ToolArgNormalization`：模型把 object/array 参数编码成 JSON 字符串时自动解析；`DispatchPolicy` 对“相同工具+相同参数已失败”的调用在派发层直接阻断，不再重复执行；`after_agent` 不再返回 `jump_to='end'`（该值指向第一个 after_agent，会自循环）；计划改为展示型，不参与完成判定；`make_graph` 只读取 `capability` 投影，避免每次请求加载整份任务 JSON（实测约 1.1 秒）。定向 36 项通过，既有 6 项失败未变；前端重建为 `index-B-lW12Fx.js`；后端重启 PID28500，GaussDB/Redis 健康。**重启暴露一个部署问题：本机 Agent Server 的线程/运行元数据不持久**，12:41 与 12:47 创建的两个线程在重启后从线程表消失（检查点仍在 `data/checkpoints.sqlite`）。已用原 thread_id 重新注册恢复 `/threads/{id}/state`；随后按用户确认，为 dacz（4e3d93f1）与 12313213（ea2094dc）分别创建新线程 `01a161ff-a565…`/`01a161ff-aeb4…`，保留材料、charges、records、revision，清空 `run_id`/`run_status`/`conversation`/`review_request`，dacz 同时取消 `deleted_at`；变更前快照见 `backend/tests/reports/thread-rebuild-before.json`。两任务现在 `status=incomplete`、详情 200、可继续核对。后续仍需改用持久线程/运行存储，或在重启前确认运行时分片已刷盘。

**2026-10-22 最新：回复轮派发硬化与 after_agent 自循环修复。** 任务12313213轨迹显示：`record_review_decision` 已提案后，模型仍强行调用未被披露的 `write_todos`、`save_document_extraction`（参数为 JSON 字符串），说明只过滤模型请求的工具集不足，图内工具节点仍会执行。`ConversationReplies` 新增 `awrap_tool_call`：回复轮只允许 `record_review_decision`/`read_task_context`/`ask_user`，已有提案或 `decision_error` 时全部阻断，不产生副作用。`decision_error` 分支不再返回 `jump_to='end'`（该值指向第一个 after_agent，即节点自身，导致 512 递归），改为标记回复 `failed`、任务 `incomplete`，由 `TaskOutcome` 直接收束。定向 33 项通过；后端重启后生效。

**2026-10-22 最新：非法工具调用恢复与前端加载死锁修复。** dacz 轨迹显示模型输出的 `save_document_extraction` 参数 JSON 括号错误且工具调用无 id，已安装框架的 invalid_tool_call 补丁因缺 id 跳过，模型没有重试机会，运行 91 秒后任务落为 `incomplete`。新增 `InvalidToolCallRecovery` 中间件（`after_model`，最多 2 次）：把解析错误与字符位置作为纠正消息回传模型，并要求先保存 `charges`、`documents`/`source_links` 分次提交。前端 `AgentPanel` 在 `isLoading` 期间每 10 秒同步任务详情，解除 `streamLoading` 死锁；`status=incomplete` 且 `run_status=success` 时显示“处理未完成”。后端定向 31 项通过；Vue 类型与生产构建通过（index-B8OFFIBK.js）。后端已重启 PID31244，GaussDB/Redis 健康。dacz 历史任务仍为 `incomplete`，未自动重跑。

**2026-10-22 最新：主体由会话确认，核对与证据合并。** 提交页移除记账主体输入，先读取材料并保存费用，再由账单助手询问公司；候选只取已保存文档/费用中的公司事实，点击填入聊天草稿，发送后才通过既有人审Skill生成新revision并重算AR/AP，可自填或暂缓，不自动指定主体。主动修改主体同样提供候选。缺主体的结束检查复用原生interrupt/Command及固定human-review2.0.2；旧快照不迁移。覆盖旧“缺主体可不问便结束”的交互约定，原件未提供的普通可选字段仍留null。

账单核对采用一张卡：费用表、所选费用置信度、原文及原件定位、修订入口；参考材料收在卡内，取消独立证据侧栏。展示合并重复原文，默认两处，其余展开，不改原始引用或评分算法。会话定向20项、Vue类型/最终生产构建通过（2501 modules、Vite1.03秒、index-D0ZuYs_R.js）；隔离真实原生服务+合成模型验证主体选择→回复→revision1到2→AP，未代答真实账单。skills配置v22，能力7f0d339560e7dc403618；正常重启PID35060，33线程ID/状态相同，GaussDB/Redis健康。未做全量测试、打包或真实OCR/Qwen整单重跑。详见docs/research/entity-choice-and-bill-review.md及entity-choice-*回执。以下记录保留历史范围。

**2026-10-22 最新：题面逐项核对与真实管理能力。** 已补齐Skill ZIP导入/注册/资源查看/启停/移除、MCP配置/真实发现与试调用、Hook管理及新增专家原生委派；禁用进入实际执行检查，必需Hook仍禁止绕过。新增纯说明Skill无需无用skill.py；配置冲突撤回本次安装，不覆盖历史release。经验loop支持主体作用域的费用映射：人工标注数据集导入/选用/启停→原生LangSmith本地对照评测→审核发布→新任务生效→审核回滚；禁用feedback-improvement阻止新候选/评测/发布，历史读取和恢复回滚保留。其他prompt/rule/Skill候选仍draft-only，不宣称已具备代码或模型自进化。

本轮修复EML邮件日期冒充账单日期、明确不同invoice间借用财务字段、未绑定include_tools、缺省工具name及FastMCP httpx2/close故障诊断。新任务skills配置v21，document-extraction2.0.1、evidence-linking2.0.1、feedback-improvement1.2.0，能力c8279edbf4bf6046429c；历史任务不迁移。本轮按功能定向验证，最后管理/改进21通过，提取/证据17通过，其他分批结果及初始失败闭合见[题面逐项报告](docs/research/functional-audit.md)。Vue类型/最终构建通过（2501 modules、1.13秒、index-qOZNjC0L.js）；隔离页面真实Skill/MCP/费用映射发布回滚通过，合成任务不冒充真实账单。正式2024服务正常重启为PID39940，33线程ID/状态相同，GaussDB/Redis健康；隔离2025已停止。真实独立金标准确率/误漏识率、长材料规模性能及20秒目标仍未验收，不能把5/7→7/7合成映射实验当提取准确率。未做全量测试、打包、真实OCR/Qwen整单重跑或真实账单回复/审批。以下旧版本/页面/进程记录保留历史范围。

2026-10-22 会话布局修正：移除账单详情中残留的“补充记账主体”黄条，待补充问题在账单助手内作为消息展示；仅真实待回复/提交期间显示底部聊天输入框和“发送”按钮，继续使用既有原生中断与回复API。助手面板按视口固定高度（桌面上限640px、窄屏上限580px、最小360px），标题/输入区固定，计划、消息和问题在同一内部区域滚动；展开记录不改变面板尺寸。保留向上阅读和回到最新消息。Vue类型与生产构建通过（2494 modules、Vite1.12秒、index-DRqTUL6_.js），当前真实待回复账单的桌面/390px检查通过，无页面错误；只填写后清空测试文字，未发送、修改或审批账单，未做全量测试。截图与回执见backend/tests/reports/conversation-fixed-{desktop,mobile}.jpg、conversation-fixed-ui.json。前端dist已生效，后端无需重启。

2026-10-22 主控动态闭环：按本机 Codex 源码职责对齐。主控使用原生 TodoListMiddleware/write_todos 按轮规划与阶段更新，工具/子Agent结果交回主控验收，再决定补读、修正、委派、询问或结束；不增加自定义runner、强制工具选择或独立反思模型。codex风格的prepare_export不再return_direct，保存/最终工具返回实际verification评分与缺口；漏调最终工具时，既有TaskOutcome通过原生after_agent/jump_to=model回传未见核验，同revision再写入不能沿用旧回执。规则支持分不是统计正确率，缺信息不强制复核。40项定向测试通过（1 warning、12.29秒），未做全量测试、真实OCR/Qwen重跑或20秒性能验证。见docs/research/supervisor-dynamic-planning.md及backend/tests/reports/supervisor-loop-pytest.xml；服务状态见backend/tests/reports/supervisor-loop-restart.json。以下旧交互/进程记录保留历史范围。

**2026-10-22 最新用户交互约定：会话式人工审核。** 智能体处理区采用Codex式问答、Markdown和可折叠工具记录。仅检查点确有人工审核/补充中断时显示一个输入框，用户用一句话补充、修改、确认或暂缓；对原生线程账单，主体/费用修改及复核入口进入会话，不再打开审核弹窗或填写中断JSON。前端仍用官方useStream消息/工具投影，实际中断结合原生tasks[].interrupts与已受理回复确认，不能因run success或SDK旧缓存而误判。后端用原生HITL respond/Command resume、AgentMiddleware.tools/ModelRequest.override/after_agent；自然语言修改经现有human-review Skill生成新revision并重新核验，修改不等于批准。普通轮隐藏输入框和回复修订工具，模型仍关闭思考。新增适配只读会话小投影，不重复传输完整OCR材料；共享预算、暂停、人工锁与不可变能力保持生效。本轮32项定向测试、Vue类型/生产构建及隔离原生服务浏览器合成对话通过，没有全量测试或真实OCR/Qwen重跑。细节和当前进程以docs/research/conversation-review.md、docs/acceptance.md及conversation-restart.json为准；下文旧表单、弹窗及折叠整个处理区为历史交互。
**2026-10-22 最新：人工中断历史与二次回复修复。** 人工审核页面现在从官方线程检查点投影保留 `native_messages` 作为 Vue SDK 重连期间的只读回退，因此新中断不会把已有会话渲染成空记录；实时消息仍由 `@langchain/vue` 管理。修复同一线程先完成主体回复、随后产生新的 AR/AP 中断时旧 `conversation` 行仍为 `starting` 导致新回复被拒绝的问题：仅当旧回复的 interrupt 已被新中断替代且已有模型消费迹象/运行已成功时，将其收束为已完成并允许当前 interrupt 继续使用原生 `Command(resume=...)`。同一 interrupt 的真实在途回复仍保持并发保护。定向 `test_conversation.py` 20 项通过，新增消费旧回复回归 1 项通过，Vue `npm run build` 通过；未发送真实人工回复、未重跑 OCR/Qwen、未做全量测试。正式服务已重启并健康，当前任务只读确认检查点含 19 条 native messages。

**2026-10-22 最新：回复轮闭环与费用ID空间修复。** 针对线程01a16127（任务11dc8ecd、ACX222）24次模型调用耗尽的实测轨迹修复四点：人工回复发生在首次finalize前、records为空时，`record_review_decision`先用既有候选做确定性reconcile再应用，`CHARGE_NOT_FOUND`返回可用费用ID并允许一次纠正重试；`conversation_review`轮只暴露`read_task_context`/`record_review_decision`/`ask_user`，提案或拒绝后不再给工具；回复轮模型调用上限`turn_model_calls=6`（runtime v4），到限写`decision_error`并收束；已完成人工修订不再从`TaskOutcome`回弹模型，原生Model/Tool调用增加线程上限。计划提示收窄为仅在开始、路线变化或阶段目标改变时更新。定向30项通过（`test_conversation`、`test_supervisor_planning`）。`test_host`/`test_codex_reading`另有6项既有失败（预览`path`、邮件上下文、实体询问），不在本次改动路径上，未修复。未重启服务、未重跑真实OCR/Qwen或历史任务。

# 航运智能账单助手：开发约定

**2026-10-22 最新：会话发送与主体目标闭环。** 覆盖旧“所有缺口均可直接结束”的收束描述：可选信息缺失仍留null、不逐单审批；但调用方已提供主体，既有posting Hook仍返回POSTING_UNRESOLVED/POSTING_CONFLICT时，主控应补读真实证据或询问收付款角色/关系。结束边界消费已绑定版本的财务校验事实，使用原生interrupt/Command等待真实回答；不能用100分已有字段置信度替代AR/AP目标完成，明确暂缓可退出。人工关系修订仍走原human-review Skill、revision和确认锁，不自写财务判断或Agent循环。新任务human-review2.0.1（skills配置v20），历史不可变Skill/财务规则不迁移。

发送时保持账单助手组件及本地提交状态，仅用Vue SDK公开的响应式threadId重接订阅；重接期间保留最后一份SDK展示投影。用户原话立即显示“正在发送”，受理后按同一reply_id与服务端记录合并；失败保留输入可重试，旧中断不得重新打开输入框，新中断才重新聚焦。主控新轮使用官方REST runs的显式input，真实回答继续原生resume，修复0.16.2的run.start被旧thread interrupt map误转成空resume而永久禁用人工修订。当前版本REST不接受tools/lifecycle为stream_mode；v2标记保留实时事件，刷新以官方检查点恢复工具消息，不承诺这两个通道完整事件回放。31项定向测试、Vue类型/生产构建通过（2495 modules，Vite1.08秒，index-BYNGcjdS.js），未做全量测试。隔离原生Agent Server+合成模型/存储通过三秒延迟发送、自动关系追问、再次回答后AP、revision1→3和刷新恢复；真实121d只恢复既有待修订会话，仍revision2、245.0000，未代答、修改或审批。最终服务/截图与范围见docs/research/conversation-review.md、docs/acceptance.md及conversation-goal-*报告；上方旧宽松终止和进程号为历史记录。

2026-10-22 金额展示精度修复：121d 原文 raw_amount=245.0000、数值 amount=245，旧前端最少两位小数格式化显示245.00。费用表与预览标题现复用 amountPresentation：已有原文为普通十进制且与当前值一致时保留原文位数，否则展示当前金额；不重新解释国际数字格式，不改变服务端金额或账单revision。默认格式不再截到六位小数。9项定向展示检查及Vue类型/生产构建通过（2495 modules，Vite969ms，index-Bv6FmwlO.js），真实121d页面与预览已验证245.0000。未重跑提取、提交人工回复或全量测试。截图见backend/tests/reports/amount-source-precision-table.jpg及amount-source-precision.jpg，前端dist已生效，无需重启后端。历史模型会话原文不回写。

**2026-10-22 Harness人工反馈闭环修复**：人工修订不再止于确定性重算。先事务保存revision/确认字段/修订依据，再检查官方线程；已结束的图使用同线程普通messages input进入下一轮，真实interrupt继续等待实际回答，暂停或预算不足保留修改。原生ModelRequest middleware向主控和专家提供当前人工反馈；after_agent绑定revision并核对反馈是否实际被模型读取，不能凭旧records或Server success宣称处理完成。成功接入的材料与补读结果从任务产物复用，确认字段/删除/拆分由原human-review Skill保护，共享预算不清零。启动失败保留修改并提供“继续处理”；明确继续历史修订时可恢复其反馈上下文，不迁移Skill/能力、不增加业务revision、不批量启动历史任务。27项定向测试通过（1 warning、10.01秒），Vue类型与生产构建通过（2418 modules、1.06秒）；没有全量测试。正常重启PID42500，32个既有线程ID/状态一致，GaussDB/Redis健康。架构及实际在线结果见docs/research/harness-revision-feedback.md和docs/acceptance.md最新记录。

**2026-10-21 最新执行约定：以用户“先抛弃之前规则、按Codex做法对齐”为准。** 新任务采用runtime.agent_style=codex：主控自主阅读、提取、解决具体疑点并输出，不强制九块/逐块coverage、固定plan、全量头字段、跨来源双侧关联证明或每字段重复回读。短材料整包批量返回；长材料使用官方StateBackend/grep/read_file或批量窗口，明确截断和续读位置。PDF/图片查看通过指定OCR转文本实现，模型关闭思考。原文引用直接采用工具生成ref_id，服务端还原原文和定位。document/billing专家按需委派；检验Agent接收具体候选与疑点，不重做整单。保存时仍核对真实引用、金额类型、当前版本与真实服务失败；缺信息留null，低分/歧义以结果和缺口结束，不因评分强制中断，用户可随后查看修改。它覆盖下文旧的固定覆盖、强制复核、布局证明及流程规则。旧任务和不可变Skill快照不自动迁移。本次针对性验证与发布状态以docs/research/codex-style-extraction.md及acceptance.md首段为准；下文版本、进程和测试数字均为历史记录。

**2026-10-21 实时执行过程修复（覆盖下段仅模拟验证状态）**：旧后台runs.create与Vue v2订阅协议不匹配，现改为官方commands/run.start，实际输出模型消息增量及工具生命周期；HTTP200协议错误不可误标为启动成功。保留reject和sync检查点（当前API命令缺durability参数，使用安装版LangGraph内部CONFIG_KEY_DURABILITY默认值，升级必核）。首检查点尚未生成时，依据已有任务刷新中的真实运行推进重新挂载原生订阅，不另建轮询/事件装配；旧失败检查点不得盖过权威run_status终态而持续转圈。定向19 passed、Vue类型/最终生产构建通过（2418 modules，1.07秒，index-DzfPQr8K.js）；独立真实Agent Server+生产Vue合成模型/材料验证47条消息、2次工具开始/完成、29次界面变化、自动订阅、逐步回复、结束收起、刷新恢复及窄屏。真实历史失败任务已验证停止转圈。正式服务正常重启为PID19252，28线程ID/状态保留，GaussDB/Redis健康。没有全量测试或真实OCR/模型重跑，不重启/迁移既有运行。详见docs/research/agent-activity-streaming.md与agent-activity-native.json回执；下文PID908和仅模拟验收为历史记录。

**2026-10-21 智能体执行过程展示更新**：账单详情以时间线展示模型可见回复、原生工具调用/参数/返回结果及子智能体过程，替换固定进度说明；运行时展开、结束后收起，保留可重新展开的检查点记录。工具默认折叠，展开才渲染详情；长回复与较早记录折叠，人工补充表单独立保持可见。只显示真实调用中已有的命令，不增加shell能力；不展示reasoning块，模型仍关闭思考。复用@langchain/vue1.2.5的useStream/useMessages/useToolCalls，查询过Docs/API MCP，未改Agent运行或业务Skill。Vue类型/生产构建通过（2418 modules、Vite1.10秒）；浏览器本地模拟检查点及v2事件的12项定向检查通过，390px无横向溢出、无页面异常。没有全量测试或真实OCR/模型重跑，没有创建/修改/审批账单。服务继续使用PID908，无需后端重启。见docs/ui-design.md、docs/acceptance.md和backend/tests/reports/agent-activity-ui.json；以下进程/构建为历史记录。

**2026-10-21 工作台管理更新**：账单列表与待办支持单选、全选当前页、跨页全选当前筛选结果、单条/批量删除及确认窗口。删除是工作台逻辑移除，原始材料、业务revision/结果/审批及管理员Trace保留；原生运行未停止时禁止删除，过期选择返回409。用户列表在数据库LIMIT前排除deleted_at，已删任务不得打开、恢复或重新派发。定向20项通过、Vue类型/生产构建通过，模拟浏览器验证及GaussDB回滚合成检查通过；没有删除真实账单。当前服务PID908，数据库/Redis健康，26个既有线程状态不变。详见docs/acceptance.md及docs/ui-design.md；本次没有发布新Skill或改变下述OCR能力。

**2026-10-21 当前发布（覆盖下文历史视觉路径）：Markdown定位 + 文本OCR。** 用户明确本项目没有多模态，模型只读文本；新能力不暴露原图/PDF图片查看工具。PDF缺口按原页切成单页PDF调用指定OCR，图片按原帧OCR，再更新干净Markdown；可用文字层/版式仍作辅助。成功补读复用，空OCR不判无费用，失败范围保留。保持单个document-extraction Skill及全部来源比较。skills v18/agents v9，document-intake1.5.0/document-extraction1.7.0，能力7cd94124068b95ff201e；服务PID24616，数据库/Redis健康，正常重启前后25个线程ID及状态一致。相关定向16 passed（2 warnings、7.26秒），另2项配置快照/附件并发检查通过；未做全量测试、未完整重跑新版指定EML，20秒端到端目标尚未证实。主控简单任务直接提取，原生grep/read_file/StateBackend定位回读，减少重复schema/全文/证据与模型总结。详见docs/research/markdown-text-only-extraction.md、docs/acceptance.md及text-only-ocr-*.json/XML回执。下文发布、进程、视觉及全量成绩均为历史记录，不代表当前路径。

## 1. 文档用途与当前阶段

**2026-10-21 当前发布：单个提取Skill递进执行。** skills v17/agents v8，document-extraction1.6.4、human-review1.1.3，能力7e98a1650f2a80341eee，服务PID42484；未新增格式Skill。BILL_DATE_EVIDENCE_REQUIRED阻止仅凭邮件Date填写账单日期；缺失留null，模型自报人工确认无效。最新另修复schema把warning/info也判为失败的问题：只error硬阻断，未知severity仍按error，信息缺失说明不强迫复核。156项相关回归通过（2 warnings、29.87秒），见single-skill-warning-pytest.xml。最新完整原件任务746914ee-4775-414e-acc4-68300058cba3在1.6.3下用尽24模型/24工具，budget_exhausted，活跃732.93秒、观察墙钟815.56秒；虽覆盖4来源/9块、1笔50、日期/邮件双方null和原图/PDF补读/预览正确，仍将HBL出口参考号误作明确主单号，证据最终投影及币种中断未完成，完整断言不通过。1.6.4只修复已复现的warning语义并发布，未再重跑整单，不能宣称解决语义误填、预算/时延或全部验收。历史任务/已发布能力不改、不代答或审批。完整状态见docs/acceptance.md；以下发布与成绩为历史范围。

**2026-10-21 当前发布：提取保持单个 Skill，增加原生原图查看。** skills v15/agents v7，document-extraction1.6.2，能力9bf7eb03b9aafc32824d，服务PID28076。view_source_image在本Skill内按任务source_id/帧读取原件，通过LangChain标准多模态ToolMessage传图，content_and_artifact分开保存哈希/传输回执；不新增格式Skill、视觉Agent或模型循环。官方Docs/API MCP已核对渐进披露、include_tools、多模态及tool签名；Qwen真实用户图片/工具图片探测各1次、均关闭思考，成功看出嵌入宣传图且无可见费用。140项相关回归通过（2 warnings、56.15秒），见single-skill-vision-pytest.xml。正常Ctrl+C重启后23个既有线程状态相同，数据库/Redis健康。指定EML新任务1f202de0-825c-4561-87cd-ad677234f311的完整结果以docs/acceptance.md为准；上轮5682145c最终仍有图片覆盖与2处引文错误，不算通过。图片传输不代表识别成功，视觉费用候选不得冒充逐字OCR证据；扫描PDF页原图渲染尚未接入本工具。下文旧版本号/测试与进程均保留历史范围。

**2026-10-21 最新实现：单个提取 Skill 递进读取。** document-extraction1.6.1保留一个提取入口，按需读references并选择PDF正文/版式补读；不新增格式Skill。全部文件及补读块均须覆盖，不同真实账单保持独立身份。PDF普通文字提取运输编号须有对应版式字段证据，缺失返回PDF_IDENTITY_LAYOUT_REQUIRED；human-review1.1.2重新计算该错误，避免修复后残留。document-intake1.4.0宿主用ocr_only，独立接口默认full兼容；evidence-linking1.4.2对唯一逐字引文重新定位，重复引文仍需真实位置。宿主补读工具使用原生ToolException/handle_tool_error反馈可纠正参数错误。配置skills v14、agents v6，能力e371ce97eb6401be6056，服务PID41596。完整回归399 passed、44 warnings、4 subtests passed（232.15秒）；最后的修复合并改动再通过100项相关测试，未宣称新增后400项全量已执行。pip check通过。指定EML新验证任务5682145c-538b-48c5-ba10-09ebc36f56b2的最终结果以docs/acceptance.md为准。首轮d0a1b46e-8b96-4d05-9e24-240c4c9c22f8保留真实失败/恢复记录，运输编号断言未通过，不算最终成功。以下旧版本状态为历史范围。

**本轮实际状态（2026-10-21，条件复核已应用）**：主体提交的409分流/并发字段对照、纵向更多字段、缺信息不触发低分复核、正常自动完成和原生定向中断均已实现。skills配置v8、runtime配置v2，当前能力 `3d1f75d53d4d20188672`；billing-confidence3.0.0、human-review1.1.0、evidence-linking1.3.0。全量回归374 passed、43 warnings、4 subtests passed（126.21秒）；Vue类型检查及生产构建通过，2411 modules、Vite1.10秒，入口index-bXBaz-K0.js。后端通过独立控制台Ctrl+C正常关闭后启动新版，重启前后18个线程ID及状态一致，数据库/Redis健康。浏览器对明确合成账单实际提交主体，revision1→2、AP、completed、auto_review=automatic且approval=null，模型调用24→24；真实历史账单只读查看。报告为backend/tests/reports/conditional-review-*.json/PNG/TXT/XML；完整记录见docs/research/conditional-confidence-review.md和docs/acceptance.md。下文上一轮成绩保留历史范围，不能用它代替本轮验收。历史能力不静默迁移，真实OCR/LLM、独立金标和长材料性能未在本轮重跑。

**2026-10-21 最新审核规则（覆盖下文历史“每单显式确认”描述）**：提取后按已有字段置信度分流，默认低于80分才生成人工复核中断，阈值由runtime.confidence_review_threshold配置并固定到任务能力。原件未提供的值、缺数量/单价/总额等可选检查不计为低置信度；原文有值但解释不明确仍需定向复核。正常结果自动完成核验，用户随时可看结果、置信度、提取原文和原文件定位，直接修改提交。必需财务数据缺失或硬校验失败时保存可编辑结果，不伪造可执行账单；不把技术失败转成人工字段清单。自动核验写auto_review，与人工approval分开，正式导出仍核对当前完整参数/revision/版本及全部必需Hook。修改后失效旧核验并重算，不重复OCR。业务分流算法属于billing-confidence及human-review Skill；宿主只持久化、组合原生interrupt/Command和官方Vue恢复。已发布快照及历史任务不静默迁移。

主体表单提交前读取最新版本，仅在所改字段未被他人修改时安全使用新revision；真正冲突在窗口内并排显示当前内容和用户输入，可明确选择保留输入提交。AGENT_RUNNING与REVISION_CONFLICT分开处理，不能把所有409都锁成永久不可提交。更多业务字段按费用纵向分组，禁止1900px宽表和无限扩大的首列；弹窗可滚动，操作按钮保持可达。

本文件供后续开发 Agent 阅读，作为本项目的需求基线、实现约束和验收依据。开始开发或恢复上下文时，先阅读本文件，再检查代码和实际运行状态。

- 用户目标：完成一个基于 **Python + LangChain** 的多格式文档解析航运智能账单助手。
- 工作目录：`C:\Users\dzx\Desktop\笔试1`。
- 环境要求：使用项目内 **`backend/bishi1/`** 便携式 Python 运行环境，与项目一起打包；不使用 conda。
- 当前阶段（2026-10-21）：用户端与右上角管理员控制台已分离导航，管理端包含Skill/工具、经验规则和Trace。最新用户核对页已收敛为AR/AP、单据编号、费用名称、金额、币种、付款方式六项；取消内部问题清单/计数和扣分列表，处理中及部分结果不提前要求最终确认，真实原生补充仍可见。最终Vue/TypeScript及生产构建通过（2411 modules，Vite 1.15秒，入口 `index-Pjg7CCsV.js`），本次桌面浏览器记录见 `backend/tests/reports/bill-review-ui.json`。此前材料包与移动端记录保留在 `bill-workspace-ui.json`、`user-workspace-ui.json`，不算本次重跑。完整键盘、长表、移动端及断线矩阵仍待验。本轮未新建任务、修订、审批、回复中断、迁移历史能力或修改后端Skill；暂不处理交付包。
- 后端与评分基线：Office费用表格、原文定位与八个业务Skill已实现，无模板海外数字/币种核验与分组置信度已完成。当前skills配置CAS发布v7、agents配置v2，能力摘要 `347e46bf7361cfe776d0`；extraction升至1.4.0，向每批提取提供邮件正文和全部材料清单，其他Skill版本延续v6。全量回归 **361 passed、43 warnings、4 subtests passed（126.29秒）**，见 `backend/tests/reports/bill-workspace-pytest.txt/XML`；之后新增一项宿主批次测试，连同5项展示投影测试 **6 passed（7.86秒）**，没有宣称新增后的全量362已执行。本轮记录见 `docs/research/bill-bundle-workspace.md`。文章取舍及9例合成差分仍见 `docs/research/global-extraction-confidence.md`；新版尚未重跑真实EML提取，独立真实金标、长材料性能与强恢复仍待验。历史任务及已发布Skill不静默迁移，在线和页面结果见 `docs/acceptance.md`。
- 原始需求优先读取工作区的 `docs/assignment/AI agent 笔试题.html`；早期副本为 `C:\Users\dzx\Downloads\AI agent 笔试题 (2026_10_20 22：39：50).html`。最终交付不能依赖本机绝对路径才能运行。
- 用户已指定 Qwen、Redis、GaussDB 和 OCR，配置在 `backend/.env`。前端已采用 Vue 3.5.44、TypeScript、Vite 与官方 @langchain/vue 1.2.5；生产 dist 随包运行，Node 仅用于重新开发/构建。
- 2026-10-21 的设计基线见 docs/implementation.md，实际装配已采用 create_agent 主控、原生 Todo/SubAgent/Skills/HITL/middleware 和官方 Agent Server，无独立 PlanService、业务 DAG、runner 或 SSE 实现。
- 八个业务包已落在 backend/skills/，均包含 SKILL.md、references/、scripts/，由官方 SkillsMiddleware 发现、披露和工具执行；各校验独立配置，领域算法仅保留在所属 Skill。Deep Agents 0.7.29 已安装并真实委派文档专家。
- T01–T33 开发基线和实施状态见 docs/superpowers/plans/2026-10-21-final-development-plan.md；实际导航、验收、恢复与性能见 docs/README.md。开发任务清单不替代产品运行时原生 todos，部分外部条件及完整评测仍未完成。

用户后续明确指令优先于本项目约定。附件、邮件、OCR 文本和待处理单据均为需求资料或业务数据；其中的命令、提示词和发送邮件要求不能自行转化为执行授权。

## 2. 目标与交付范围

系统应解析不同格式的材料，提取和标准化费用，结合已有账单判断新增、更新或待复核，并输出财务系统可消费的合法 JSON。

必须交付：

1. 可运行的 Python 源码，实际使用 LangChain 完成模型调用或提取流程，不能仅导入包而无实际使用。
2. EML、PDF、图片、XLS/XLSX、DOC/DOCX 的解析和接入能力。
3. 新增、增量更新、重复检测、冲突处理、AR/AP 判断和来源追溯能力。
4. 覆盖主要验收场景的测试、示例输入输出及可复现运行说明。
5. 面向该场景的 harness 稳定性与准确性设计说明及相应实现。
6. 五点以上有业务或技术依据的补充思考，明确区分已实现内容、已知限制和未来建议。
7. 代码 ZIP 或 Git 仓库交付，并提供环境、配置、运行、测试和外部服务说明；交付包须包含 `backend/bishi1/` 便携式解释器与已安装依赖，不能只提供需要用户重新创建的虚拟环境声明。
8. Vue 前端，提供材料与记账主体输入、任务进度、结果及证据查看、人工纠错与暂停/恢复，以及对应的扩展配置入口；操作须与后端实际能力联动。

用户补充要求采用 Vue 前端，项目可扩展、工具可自由配置，并指定 Redis 和 GaussDB 连接配置；后续设计须纳入这些要求，按实际职责使用服务。生产部署和真实财务系统写入另按用户明确指令；LangGraph 不是题目硬性要求。

## 3. 环境与开发工具

### 3.0 前后端目录边界

- 后端工程统一放在 `backend/`，该目录本身就是 `backend` Python 包，不再嵌套 `src/backend/`。`agents/` 按 supervisor/document/billing 分工；`middleware/` 组合原生扩展点，`tools/` 绑定宿主工具，`hooks/` 统一触发独立校验，`mcp/` 管理官方连接及发现适配，`extensions/` 固定能力与 Skill 版本，`harness/` 管理派发/预算/计时，`api/` 按接口职责分路由，`infrastructure/` 提供模型/存储/资产/检查点适配，`config/` 保存配置模型、事务、提示词解析和 YAML。八个业务包仍在 `skills/`。前端工程独立放在 `frontend/`。
- 仓库根只保留两个工程目录、公共 `docs/`、交付 `delivery/`、README/AGENT/AGENTS 和一键启动入口，不能再把后端资源散放根目录。题面在 `docs/assignment/`，原题数据在 `backend/data/samples/`。
- 根 `start.cmd` 转调后端入口；官方 Agent Server 的工作目录固定为 `backend/`，其 `langgraph.json`、`.env`、`.langgraph_api/` 与数据按这一边界定位。根目录命令使用 `./backend/python.cmd`；在后端目录内才使用 `./python.cmd`。
- 目录调整不改历史 task/revision、检查点、原始响应或已发布 Skill 内容；历史报告保留原路径和哈希。官方入口保持 `backend.agents:make_graph` 与 `backend.api:app`，checkpointer 改由 `backend/infrastructure/checkpoints.py:checkpointer` 提供。内部调用使用实际职责模块，`__init__.py` 只显式导出公共入口，不通过兼容别名保留旧平铺模块。本轮163项全量回归、后续40项定向回归和接口/历史状态核验已完成；1166个skills/releases文件及.env哈希不变，未新建或恢复Agent运行。原有GET导出核验会更新last_export及审计回执，已在本轮报告注明，未改变task revision。旧ZIP迁移结果仍只覆盖旧版本。

### 3.1 项目内便携式 Python 环境

- 用户已将原 conda 要求改为随项目打包的便携式环境，不创建或依赖任何 conda 环境。
- 环境目录保留名称 `bishi1/`，位置为 `backend/bishi1/`，使用项目自带解释器和项目内依赖，不复用其他项目、系统 Python 或 Codex 私有解释器。
- Windows x64 初始运行时采用 Python 官方 NuGet `python` 包的 Python 3.13.16，解出其 `tools/` 作为项目内运行时；版本属于实现选择，不是原题硬性要求。
- 不把普通 `venv` 文件夹直接复制打包并宣称可迁移。交付采用自带解释器的私有运行时，并用相对 `python313._pth` 隔离搜索路径。
- `backend/python.cmd` 通过自身位置定位同目录的 `bishi1/python.exe`；所有项目 Python、安装依赖、测试和运行命令均使用 `./backend/python.cmd ...` 或项目内解释器的明确路径。
- 依赖通过 `./backend/python.cmd -m pip ...` 安装到运行时；避免依赖 `Scripts/` 内可能记录旧绝对路径的命令入口，优先使用 `python -m 模块`。
- 提供运行时重建脚本 `backend/scripts/bootstrap-runtime.ps1` 和环境说明 `docs/portable-environment.md`。依赖确定后补充锁定声明，并随交付包包含实际安装结果。
- `backend/bishi1/` 必须随项目 ZIP 一起交付，`backend/.build/` 下载缓存及构建临时文件不打包。
- 在移动或复制后的目录、项目外工作目录中验证解释器、pip 和项目运行；依赖中有二进制扩展或外部命令时验证它们的实际可迁移性。
- 当前便携式运行时针对 Windows x64；不得声称同一二进制环境可直接运行于 Linux、macOS 或不同 CPU 架构。
- API 密钥、模型地址等通过后端目录 `backend/.env` 或环境变量读取。用户明确要求将其提供的实际配置直接写入 `backend/.env`，无需再次询问；连接值不要复制到源码或开发约定正文中。

### 3.2 用户指定的服务与模型

- Redis 使用 `backend/.env` 中的 `REDIS_URL`；该地址指向运行项目的本机，实际服务可用性需要核验。
- GaussDB 使用 `GAUSSDB_HOST`、`GAUSSDB_PORT`、`GAUSSDB_USER`、`GAUSSDB_PASSWORD`、`GAUSSDB_DATABASE` 和 `GAUSSDB_SCHEMA`；驱动、认证及 SQL 兼容性应通过实际连接验证，不能仅凭名称假设与某数据库完全兼容。
- 用户已确认数据库密码末尾的三个点是密码本身的一部分，按 `backend/.env` 中完整字面值使用，不再将其视为省略或占位符。
- OCR 使用题目指定的接口，服务地址和超时已写入 `backend/.env`。用户已明确授权 `OBS_ENABLE=true` 自动上传至指定华为OBS桶并调用OCR；连接值仅在 `backend/.env`，不再询问是否启用。优先调用方URL，否则由document-intake通过华为官方SDK生成临时签名下载地址，不修改ACL。
- 文本模型使用 `LLM_PROVIDER=qwen`、用户指定的 DashScope OpenAI 兼容地址和 `qwen3.8-max`；模型、地址和密钥均从 `LLM_*` 配置读取。
- 用户同时提供的 `VLM_*` 配置按原值保留。用户最新明确当前项目没有多模态，当前提取模型只读文本；PDF/图片统一使用指定OCR及Markdown，不向模型传原图或PDF页图片。历史视觉探测及历史能力不构成当前使用视觉输入的依据。
- **文本模型和视觉模型调用均不得开启思考模式。** `backend/.env` 的 `LLM_ENABLE_THINKING=false`、`VLM_ENABLE_THINKING=false` 是本项目配置项；后续适配代码必须读取，并在兼容接口请求体中实际传递 `enable_thinking: false`。采用 Python OpenAI 兼容客户端时通过 `extra_body={"enable_thinking": False}` 传入，不能只在提示词中要求不思考。
- 已核对阿里云官方文档，`qwen3.8-max` 为可关闭思考的混合思考模型；文档核实不等于当前账号权限、余额及真实调用已验证。参考：`https://help.aliyun.com/zh/model-studio/deep-thinking/`。
- 用户已确认记账主体由调用方逐次指定，不设置默认公司，`ACCOUNTING_ENTITY` 保持为空。智能体在规划阶段检查每次请求中的主体，必要时向调用方询问或请求确认，再执行依赖主体的判断；不得自行猜测。
- 真实验证：psycopg已连接openGauss 5.0.0并通过本项目表事务，Redis PING/解析缓存可用，Qwen实际调用成功并关闭思考。原题PNG、两份PDF的OBS上传/签名下载均200且哈希一致，指定OCR返回200。PNG首次响应未映射的partial保留在backend/tests/reports/obs-ocr-real.json；后续结构化映射与PDF在线结果见backend/tests/reports/obs-originals-ocr.json，其中PNG映射为真实原响应回放，不重复算在线调用。

### 3.3 插件、MCP 与 Skills

工具状态以当前会话实际暴露的能力为准，配置存在不等于服务已连接。每个开发任务开始时，先核对本文件与相关插件、MCP、Skill 的当前可用能力，优先使用适合该任务的已连接工具；工具不可用或不适合时再采用终端或官方网页等路径，不以配置文件存在冒充连接成功。

**从现在开始，对智能体的每一个操作都必须先查 LangChain MCP。** 包括创建/调用 Agent、规划、Skill 发现/读取/执行/刷新、工具与 MCP 调用、委派、Hook、人工中断/恢复、检查点、上下文、预算与反馈改进；不只在初次选框架时查询。实施或调整该操作前，先用 Docs MCP 读取对应官方用法，再用 API Reference MCP 核对符号/参数/包与实际安装版本，必要时用 GitHub MCP 读取固定提交源码与测试。该要求约束本项目开发时的查证，不是在产品每次处理单据时额外调用文档 MCP。

在相关实现/研究记录中保留“操作 → 官方入口/符号 → 适用版本 → 原生组合 → 实际验证/缺口”。同一操作可复用当前会话已经读过、且版本与组合仍适用的依据；新增操作或依赖/组合变化须重新查证，不能仅引用旧的框架总览。优先原生配置/组合，再补业务代码和必要薄适配；不得先凭记忆写自有框架再补引用。若所需 MCP 暂不可用，先恢复连接并继续不依赖它的工作，不将终端或网页回退当成已经满足用户的 MCP 要求。非 LangChain 库和构建工具另核对其官方资料；MCP 不作为交付程序运行前提。

| 工具 | 使用原则 |
| --- | --- |
| 本地终端与文件工具 | 创建环境、开发、测试和打包的主要工具 |
| LangChain 相关 Skills | 开发前按需读取 `ecosystem-primer`、`langchain-fundamentals`、`langchain-dependencies`；采用其他组件时再读取对应指导 |
| `langchain-docs` / `langchain-reference` MCP | 2026-10-21 已修复旧启动配置并补充 API reference 服务。用户重启 Codex 后，两个服务的 5 个工具均已原生暴露；文档搜索、正文读取、Python API 搜索和符号详情 4 个只读工具均实际调用成功。后续优先使用，具体状态见 `docs/development-tools.md` |
| `pdf`、`documents`、`spreadsheets` | 检查样本及人工核对提取结果；交付程序必须具备独立的解析能力 |
| 浏览器工具 | 按需访问样本下载页、查阅官方文档或验证界面 |
| GitHub MCP | 优先用于官方仓库检索、固定 commit、读取真实源码与测试；已用于本次架构研究。按需完成用户要求的仓库交付，不默认创建远程仓库或发布业务样本 |
| `stop-that-shit` | **代码编写/修改与运行代码、脚本、测试、构建、依赖验证前必须调用并应用**当前可用 Skill；授权修改使用 change，只读审查使用 review；不伪造 Guard 已启用或拦截回执 |
| `design` | **前端编写/修改前必须调用并应用**当前可用 Skill，按需路由至设计 tokens、布局及组件指导；保持 Vue 技术栈，代码/构建同时遵守 stop-that-shit |

Codex 插件、MCP 服务和本地 Skills 是开发辅助工具，不应成为交付程序运行的隐式前提。

插件使用的具体入口和边界见 `docs/skills-and-hooks.md` §6。读取已暴露的 `SKILL.md` 并按其工作流执行是当前 Skill 调用方式；宿主支持时使用其 Codex 原生指令，不把 `$stop-that-shit` 当作 PowerShell 程序，不虚构插件 MCP 方法。插件不可用时先查找并恢复，不绕过明确要求继续编写或运行相关代码；子 Agent 同样遵守。

### 3.4 Vue 前端与本地工具链

- 2026-10-23 用户要求不让人整理已有账单JSON：已移除 `TaskComposer` 手填入口，常规新建提交 `history_mode=automatic`，主体明确后自动检索同主体已完成且当前revision校验通过的历史记录。后端保留调用方指定旧账单范围；人工只处理歧义、明确更新意图和业务确认。历史变化/查询失败阻止批准及正式导出；无匹配仍不填造缺失字段。Vue类型检查/生产构建及59项相关离线检查通过，未跑全量或真实模型/OCR/正式历史SQL；服务未启动，旧任务不自动迁移。

- 用户最新核对要求（2026-10-21）：默认只核对 **AR/AP、单据编号、费用名称、金额、币种、付款方式**，一行一项费用；保留置信度、原件定位和修改入口。不得把内部校验、覆盖、评分阻断或“尚无费用”合并成用户核对清单/数量。处理中显示真实进度和部分结果，不提前要求最终确认；真实原生人工补充继续直接显示。更多业务字段、交易双方和日期收起为可选信息；缺少非必填编号/付款方式显示“未提供”，不按模板新增错误。未完成、暂停及等待补充的任务不展示最终确认入口，服务端校验和审批/导出门禁保持生效。
- 本次六字段调整只改前端展示与交互，最终生产构建为2411 modules、Vite 1.15秒、入口 `index-Pjg7CCsV.js`，浏览器记录见 `backend/tests/reports/bill-review-ui.json`。核验100分、24分历史合成账单、真实在途部分提取及历史原生补充请求；未提交修订、审批或回复，不把前轮后端全量测试当作本次重跑。
- 用户最新界面要求：用户工作空间与管理员控制台分开，右上角“控制台”进入管理，管理端覆盖 Skill/工具、经验规则与 Trace；用户按一次提交的账单材料包查看单号、交易方、费用及具体待办，不能按内部步骤组织。业务结构化结果以表格展示，JSON保留为下载契约。人工补充问题和费用修订/原件定位入口在账单详情直接可见。
- 用户列表使用只读 `/api/bills`，调用官方 `threads.search(ids,select)` 批量核对真实中断，不能让数据库旧processing掩盖等待人工的线程。Trace复用官方检查点和已有耗时回执；人工修订比例、常规确认和当前待补充分别统计，口径与分母可见。没有独立金标时准确率/误识率/漏识率为null并明确未评测，不能拿置信度替代。细节见 `docs/research/bill-bundle-workspace.md`。

- 前端采用用户指定的 Vue。优先核对并复用本地已有的 Node.js、包管理器及适合本项目的 Vue 资源；不擅自升级或修改其他项目的环境。
- 前端采用 Vue 3/TypeScript/Vite，官方 @langchain/vue useStream 管理 Agent 流、todos、工具、子 Agent 与中断。已锁定并完成生产构建和真实联调；不混用旧 FetchStreamTransport，不自写完整 Agent 流状态层。
- 前端工程在 frontend/，package-lock.json 固定版本；已用本机 Node 22.22.3/npm 10.9.8 完成类型检查和生产构建。
- 前端面向业务用户，按工作总览/大屏、业务中心/待办、独立提交页、账单详情和管理中心分层。`src/pages/`承载页面，`components/`承载业务交互，`utils/taskPresentation.ts`统一摘要展示；管理配置不挤进日常核账流程。Hash导航支持刷新与前进/后退，KeepAlive按业务中心/待办key保留同次页面会话内的搜索、筛选和分页，不承诺整页刷新恢复局部输入。
- 总览、列表和管理页仅轮询摘要与health；进入详情才读取当前task和资产，摘要不能覆盖完整费用与来源。有thread的详情保持AgentPanel挂载，只折叠计划/工具/专家日志，中断表单持续可见。正式导出前提示当前revision须已确认，服务端仍重新执行完整校验。统计不得虚构趋势、进度或跨币种总金额。
- 开始前端实现时核对 Vue 与构建工具的兼容版本，确定项目使用的包管理器并提交对应锁文件；前端源码和依赖声明放在本项目中，避免仅依赖全局包或其他项目的 `node_modules`。
- 前端负责材料、字段、来源证据、差异和任务控制的交互；Agent 编排、MCP/Skill 生命周期、Hook 执行、业务校验与版本裁决由后端完成。前端编辑、审批和暂停/恢复遵守 §7.3–7.5 的接口与版本要求。
- 前端 dist 由官方 Server 内的 FastAPI /app/ 提供；此前旧工作台的费用修订、校验拦截、并发冲突、原生中断/重连及反馈发布回滚已有浏览器记录。新版已实际验证页面导航、列表详情往返保留筛选、EUR金额到邮件内容块定位、100分确认入口/未审批正式导出禁用、日志折叠时历史中断可见、390×844布局与移动菜单操作，以及测试标签临时阻断API后的旧快照保留和重试恢复。原文定位为真实内容块，不冒充数值坐标高亮；未点击确认或回复中断，未关闭后端。完整交互与异常矩阵仍待验，报告见 `backend/tests/reports/user-workspace-ui.json`，页面说明见 docs/ui-design.md。

### 3.5 铁律：智能体相关自写代码必须先查官方能力

**凡是与智能体相关的代码、脚本、Hook 或执行机制，在决定自写、编写、修改或运行前，必须先查询 LangChain MCP。只有查证 LangChain / LangGraph / Deep Agents 及其官方集成确实没有满足该项具体职责的能力时，才允许编写最小缺口实现。Hook 不例外，业务 Skill 的 scripts 也不例外。** 同时对照本机 Codex 源码（`C:/Users/dzx/Downloads/codex`）的回合循环、计划工具和工具错误返回逻辑，以及当前成熟框架的既有实现；不得用提示词约束代替确定性的派发与终止控制。

- 适用范围：Agent 创建/调用/循环、Plan、子 Agent 协作、Skill 加载/执行/热更新、MCP/工具发现与调用、Hook/校验触发、HITL、暂停/恢复、检查点、上下文/记忆、重试、计量和反馈改进；也包括接入这些路径的领域脚本与适配代码。不能通过改名为工具、业务 Skill、薄桥接或 middleware 绕过此规则。
- 普通 Python 环境准备、便携解释器入口、纯前端构建及 ZIP 打包等不属于 LangChain 智能体能力，不要求证明框架具有或缺少这些通用工程功能；其中若包含 Agent 编排/加载逻辑，该部分仍遵守本铁律。代码编写/运行使用 stop-that-shit、前端编写使用 design 的要求不变。
- 查证顺序为 Docs MCP 用法与现成组件 → API Reference MCP 参数/版本 → 必要时 GitHub MCP 固定源码/测试 → 本项目最小兼容验证。先检查官方可配置能力及现成集成是否满足完整职责；满足时直接配置或组合，不重写。只有明确具体缺口后才补该缺口，通用执行部分仍交给框架。
- 在对应设计/实现记录中说明拟自写的职责、查过的官方入口/符号、适用与安装版本、为什么现成实现不能满足、允许补充的最小范围和验证结果。沿用已有文档记录，不为形式另外建设证明系统。仅“搜索没命中”“包未安装”“不熟悉用法”或“一次调用失败”不能证明官方没有此能力。
- 已有官方能力即使需要补可选依赖、正确配置或版本适配，也应先解决这些条件，不能直接以此为由自写替代。确有平台/版本限制时记录实际限制，不把“当前组合未验证”写成“LangChain没有”。
- Hook 是独立校验配置项，不意味着每项都必须有自写 Python 文件。原生 HITL、retry、call-limit、filesystem/skills 等能力直接由统一配置装配；只有官方不能表达的具体领域判定才允许增加校验函数或薄 Hook。不得复制现成重试、审批、中断、工具执行或事件派发机制。
- 后文列出的 Skill scripts、Hook 处理器和目标目录是职责设计，**不是默认获准自写的清单**；实现前逐项执行本铁律。Skill 的目录格式要求也不能成为复制官方实现或生成无用包装脚本的理由。

当前实际盘点：`backend/agents/`、`middleware/` 与 `mcp/` 装配官方主控、专家、Skill 资源和 MCP；`tools/` 只绑定宿主上下文、人工输入及包内函数；`extensions/` 固定配置和 Skill 内容；`harness/` 负责共享派发/预算/计时；`hooks/registry.py`、`validation.py` 与 `config/hooks.yaml` 统一管理独立校验。八包领域算法完整保留在 `backend/skills/`。`api/` 按材料/任务/审核/导出/扩展/改进接口分路由，`infrastructure/` 适配模型、事务存储、资产和官方检查点。执行仍采用官方工具绑定，没有本机 shell 或通用 Skill runner。`backend/scripts/` 的环境、迁移和只读 HTTP 测量属于通用工程；交付制作按用户最新指令暂缓。后续相关变更仍先查官方能力。

## 4. 输入与文档解析要求

| 输入 | 必须处理的内容 |
| --- | --- |
| EML | 邮件主题、发件人、收件人、正文和附件；处理字符编码；附件按实际格式递归解析并保留邮件关联 |
| PDF | 文本或扫描账单均接入题目指定 OCR API，保留服务返回内容和来源信息 |
| 图片 | 支持 JPG、PNG、TIFF 等题目所列格式，接入同一 OCR API |
| XLS/XLSX | 工作表、表头、费用明细行及合计信息；保留工作表与行定位 |
| DOC/DOCX | 正文和表格；旧版 DOC 需要真实可用的读取或转换路径，并说明外部工具要求 |
| 已有账单 JSON | 校验输入结构，为匹配、保留原值及增量更新提供依据 |

同时需要明确当前记账主体；用户确认由调用方在每次处理中指定。智能体规划时负责识别该参数是否齐全，在缺失或不明确时向调用方补充询问；未取得明确主体的财务结果保留相关字段为 `null` 并进入复核，不能猜测。

解析失败、附件损坏、格式不支持等必须返回可定位的错误或处理状态，不得伪装成成功且没有费用。无法确定的字段保留 `null`，不能为了填满输出而生成数据。

原题样本下载信息：

- 链接：`https://pan.baidu.com/s/1ihoJqkhlJdrqec86Pf4_2Q`
- 提取码：`pltp`
- 初始盘点尚未下载样本是历史状态。2026-10-21 当前只读清点确认 `backend/data/samples/` 已有1个EML、2个PDF、1个PNG；EML内还有2个PDF附件与1个嵌入JPG。文件存在不等于内容已验证，后续按开发计划T02建立标准答案和来源清单。
- 当前未发现XLS/XLSX、DOC/DOCX、TIFF、已有账单JSON、明确更新指令及长文档/跨页标准答案。用获准材料或明确标注的合成样例补齐，报告区分原题材料与合成覆盖，不能继续把全部样本写成未取得。

### 4.1 指定 OCR 接口

- 方法与地址：`POST http://36.103.199.11:5002/process`
- 请求 JSON：`{"file": "<服务端可访问的文件下载地址>", "task": "orderChange", "callBack": "", "taskType": ""}`。
- 题目示例超时：连接 10 秒、读取 300 秒。
- `file` 是 OCR 服务端可访问的下载 URL，不能将本地文件路径直接作为该字段。
- 已复核用户指定的工作区 HTML，其中明确给出了上述 JSON 请求方式和 URL 可访问要求，没有另行说明本地文件上传接口。后续实现应据此落实文件 URL 获取路径，不能将题目给出调用示例说成缺少 OCR 接入文档。
- 本地文件、邮件附件及PDF切片已通过获准的OBS自动发布。document-intake 1.1.0组合 `esdk-obs-python==3.26.6` 的putFile/createSignedUrl；签名在临派发前生成、默认3600秒，不保存签名URL到上传回执。成功回执保留对象key、哈希、大小、ETag/request_id和原页/帧；不更改ACL，不把localhost或本地路径提交给远端OCR。
- 实际响应为 `success/data.list` 结构化单据。`OCR_RESPONSE_FORMAT=orderChange` 校验成功状态与非空单据字典，逐项保留原键值为 `ocr_structured` 块和 `/data/list/<index>` 引用；默认text兼容模式和显式文本pointer仍支持。服务返回的是结构化内容，不能冒充原件逐字全文；page_index/pages_split语义未核实，不当作物理页或坐标，仅单页传输片能据实际映射设置page。币种、交易方等缺失仍进入复核。
- 当前skills配置为v7，版本及能力摘要见§1；v5能力 `3eb8bfbc62c9d4f41004` 及v6能力保留历史任务。每次intake使用新的UUID产物目录，避免跨任务或重试覆盖原响应；缓存身份包含响应格式、pointer、能力版本和非秘密OBS身份。内部上传/OCR前guard检查暂停、revision和启停，不把SDK内部HTTP独立增加为工具调用数。所有在途故障、断电及长材料容量仍按验收记录保留待验。
- 新EML真实任务 `edfd9e4f-a0a7-4aa5-9349-07eb29169cc1` 的业务状态是awaiting_input，原生ask_user请求确认正文 `SHA pay TAR：H/C $50` 的币种和收费双方；currency/creditor/debtor保留null。历史将该正文记为USD50的描述不构成币种证据。附件OCR的chargeList为空只代表服务此次返回空列表，不能保证原件没有费用。框架run_status=success不等于业务通过；原始报告见backend/tests/reports/obs-agent-task.json，未代答或审批。
- 保留原始 OCR 响应与后续清洗结果，区分请求失败、响应解析失败和业务提取失败。
- 本地 OCR 可以作为明确说明的辅助方式，不能替代“能够调用指定 OCR API”这一验收要求。

### 4.2 长文档、跨页与处理完整性

- **2026-10-21 用户最新约束：文档提取只保留现有 document-extraction 一个 Skill，禁止按 PDF/图片/Office 拆分格式 Skill。** 在其 SKILL.md 内规划递进步骤，由 Agent 判断文件类型、选择读取或补读方式，按需加载 references/reading-strategies.md、cross-file-review.md、output-contract.md；scripts/提供必要能力，加载与工具执行仍复用官方机制。这不合并既有接入、证据、财务等不同职责包，也不新建格式包。第一份材料提齐字段后也必须检查其余全部文件；缺口、冲突均回到原文核对，全部可用材料查过仍未提供才留null。失败、未读范围和预算耗尽不得冒充缺失。

- 一次提交是一份账单材料包。EML正文、全部附件及嵌入材料共同参考，最终综合输出；一个费用项目仍对应一条记录，不能按附件数量重复生成账单。跨材料补充须有明确业务关系与真实来源引用；不同真实单据的身份、币种和总额作用域保持独立。共享邮件上下文截断必须标明完整chunk引用，所有来源覆盖后才宣称完成，空OCR费用列表不能证明原件没有费用。

- PDF 的 OCR 传输切片与模型语义分块分别建模；保存原页映射、逻辑单据/表格/行身份和所有计划范围。结合单据身份、表头、列含义和续接证据处理跨页，不能单凭固定页数或字符数切分后独立合并。
- 跨页费用行保留前后片段来源；重复表头、页小计、承前转后与总计分别标记，防止漏行和重复计费。跨单据、表格列变化或身份冲突时重新判断边界；依据不足进入复核。
- Word 按段落与表格的原始内容顺序读取，覆盖合并/嵌套表格和跨页长行。证据以内容锚点为主；物理页码若来自渲染，须绑定具体转换与预览版本，不能假定 DOCX 有稳定自动页码。
- 为页面、内容块、候选费用行和分块保存处理去向：已提取、非费用并附依据、重复并指向保留项、待复核或失败。覆盖闭合不等于语义正确，仍需原件证据、金额校验和独立样例验证。
- 同一逻辑单据的未处理范围、边界歧义或关键核对失败所影响的费用须为 `PENDING_REVIEW`；影响无法可靠限定时整张逻辑单据复核，不能只在界面提示部分完成仍输出可执行操作。
- 模型分块同时预留输入和输出容量，公共身份限定作用域，重叠上下文不重复拥有费用行输出权；截断、缺行、无效引用和未完成范围必须可见。
- 长材料的子调用与重试继续计入共享预算。预计或实际超限时保存已完成范围，明确请求预算或范围调整，不能静默截取前若干页，也不能用分批或重启子 Agent 重置同次运行计数。
- OCR 响应实际具备哪些页码、表格和坐标信息必须验证；缺少的信息不能编造。具体方案见 `docs/implementation.md` §4–6。

## 5. 提取、标准化与财务规则

### 5.1 提取字段

至少识别单据类型、单据编号、日期、签发方、接收方、费用名称、数量、单价、金额、币种、付款方式、小计、税额和总计。匹配需要时，提取提单号、订舱号和箱号；不存在的值为 `null`。

- 一个费用项目对应一条输出记录；多份文件可能描述同一费用，不应直接按文件数生成多条账单。
- 保存原始名称和标准名称，允许通过有来源的映射进行标准化。
- 初始费用映射：Handling Fee / H/D Fee → Handling Charge；Doc Fee → Documentation Fee；THC → Terminal Handling Charge；Trucking Fee → Trucking Charge；Customs Fee → Customs Clearance Fee；Storage Fee → Storage Charge。
- 币种输出三位 ISO 4217 代码；歧义货币符号不能凭空推定币种。
- 付款方式规范化为 PP、CC 等明确约定值，同时保留原始依据。
- 金额计算采用适合货币的精度处理，避免二进制浮点误差影响判断；最终 JSON 中金额必须是数字，不能输出数字字符串、NaN 或 Infinity。
- 无法确定费用名称或映射时保留原始信息并标记问题，不强行归入相似费用。

### 5.2 匹配与增量更新

按题目给出的顺序评估以下匹配依据，记录命中证据：

1. 单据编号与费用名称。
2. 提单号、费用名称与币种。
3. 订舱号、费用名称与币种。
4. 箱号、交易双方、日期与金额。

标准化名称可以用于匹配，但不能因此误合并同一单据中真实存在的同名多行费用。多个候选同样成立、关键字段矛盾或匹配依据不足时，进入复核，不能随意选第一个候选。

| operation | 使用条件 |
| --- | --- |
| `CREATE` | 有效费用通过必要校验，未匹配已有账单，且不存在阻止新增的冲突或歧义 |
| `UPDATE` | 唯一匹配已有账单，且输入材料明确要求修改至少一个字段 |
| `NO_CHANGE` | 已确认是重复材料或已有账单的相同内容，没有需要执行的变更 |
| `PENDING_REVIEW` | 低置信度、校验失败、匹配歧义、字段冲突或财务方向不明，无法可靠决定操作 |

- 更新必须基于已有记录，只修改输入中有明确变更依据的字段，并保留变更前后值和来源。
- “未提供”“明确清空”“提供新值”是不同语义。缺失字段或模型返回的 `null` 不能直接覆盖已有有效值。
- 新材料与已有账单值不同，不自动等同于明确更新指令；先判断上下文是否支持变更，否则进入复核。
- 更新金额不能顺带覆盖币种、付款方式或交易方。没有明确要求修改的字段继承原账单。
- 相同输入重复执行不能生成重复新增操作；区分重复文件、重复提取和真实重复账单。

### 5.3 AR/AP 判断

- 从当前记账主体视角判断：AR 为应收，AP 为应付。
- 结合签发方、接收方、当前记账主体和收费方向，不能仅凭 Debit Note、Credit Note、金额正负或 PP/CC 判断。
- Credit Note、冲销和负数金额应结合被冲减的业务关系处理，不能机械反转 AR/AP。
- 主体身份或收费方向不足以确定时，`posting_type` 为 `null`，记录原因并进入复核。

### 5.4 校验

校验金额有效性、币种合法性、数量/单价/金额关系、明细与合计关系、重复费用、跨材料冲突和 OCR 的 `0/O`、`1/I` 等混淆。合计核对应按币种及单据范围处理，避免跨币种求和；容差规则需要明确并可测试。

金额角色与是否已计入明细须明确，依据来源选择含税/未税及折扣已净入/另列的核对公式，避免重复加税或扣减；公式依据不明时进入复核。

OCR 纠错必须保留原值及依据。无法由上下文验证的修改不能静默生效。模型自报置信度不能作为唯一入账依据；未通过关键校验的结果只能供复核。

### 5.5 置信度与原文复核

- 置信度算法属于独立 `billing-confidence` Skill；宿主 `assess_task_confidence` 工具只注入当前任务与实时统一校验，禁止模型传入自造的校验结果。只读 `/api/tasks/{id}/confidence` 不改写 task/revision；历史能力没有该 Skill 时显示不可用，不用新规则重新评分。
- 当前v2默认公式为 `70×(0.45A+0.35C+0.20N)+20×max(0.5L,T)+10V`。A/C/N为金额/明确币种/原始费用名称的来源支持，L为原文不同token支持的数量×单价核验，T为同单据同币种独立原文总额核验，V为覆盖。来源回读和字段支持合并计分，算术与总额取max，同源重复引用不加分。高分门槛90，中分65，缺检查不重归一化，任务取最低费用分；未经独立金标校准，该分数不是统计正确率。v1六项配置与结果仍随历史能力保留，不静默转换。
- 国际数字/币种解释只在evidence-linking，支持合法欧洲/印度分组、Unicode数字与括号负数；`1,234`等歧义保留候选，裸`$`/`¥`等不按地域语言猜ISO币种。原文raw数值/币种/数量/单价保留；金额/币种/费用名无支持或位置/数字歧义由evidence硬错误进入统一审批及导出门禁。没有单号、数量或单价不按固定模板判错。
- 算术交给财务Skill的Decimal唯一实现，折扣规范金额也只消费同revision的既有normalized事实，不增加模型调用。无数量单价/总额的来源完整费用可得80分并建议核对；真实原文算术可90分，独立总额可100分。缺总额不造硬错误，明确所引总额与原文矛盾仍硬阻断；所有schema、主体方向、覆盖、冲突等硬错误均不能由高分抵消。评分合同见 `backend/skills/billing-confidence/references/scoring.md`。
- 用户页面展示任务/费用置信度及上述六字段的来源支持，不展开内部组件扣分和原始阻断清单，也不把非必填缺失字段的零分当作待办。用户可选择是否打开原文；高分且处理完成时可直接显式确认当前版本，不强制逐项打开预览。原始评分、校验与审计数据继续保留在服务端；人工修订仍生成新 revision、重算派生结果并使旧审批失效，不自动记账。
- 金额定位由 `evidence-linking.build_preview` 投影保存的原文结构：Excel优先实际sheet/row/cell；数值多义只定位行，不把50匹配到150。Word使用内容锚点，版式PDF页码绑定转换器与文件hash；无真实位置时仅展示材料或结构，不伪造坐标。

## 6. 输出契约与审计

顶层为 JSON 数组，保留题目规定的字段层级：

```json
[
  {
    "operation": "PENDING_REVIEW",
    "document_info": {
      "document_type": null,
      "reference_no": null,
      "document_date": null
    },
    "transaction_party": {
      "issuer": null,
      "recipient": null
    },
    "charge_details": {
      "charge_item": null,
      "amount": null,
      "currency": null,
      "payment_term": null
    },
    "financial_attributes": {
      "accounting_entity": null,
      "posting_type": null
    },
    "audit_trail": {
      "ai_reasoning": ["示例结构：信息不足，需人工复核"]
    }
  }
]
```

此示例仅说明结构，不是实际业务结果。原题示例中的尾逗号需要修正，所有实际输出均须通过 JSON 解析和结构校验。

- 使用明确的 schema 约束类型、枚举、可空字段和嵌套结构。
- 为保存原始费用名称、文件来源、原始文本、页码/表格行、匹配记录、变更依据、校验问题等要求，可在不破坏核心字段层级的前提下扩展字段，或提供关联的审计产物；具体契约需写入说明并测试。
- `ai_reasoning` 保存简短、可核验的业务依据，例如来源定位、规则命中及修改原因；不要求模型输出内部思维链。
- 处理状态和运行日志不得混入机器可读 JSON。若提供 CLI，业务 JSON 与日志使用清晰分离的输出通道。
- 原始单据、完整 OCR 文本和密钥不默认进入公开仓库；交付样例使用可公开数据或脱敏材料。

## 7. 实现原则与 harness

让模型承担语义提取和上下文理解，让代码承担 schema 校验、金额核对、匹配规则及增量合并等可确定行为。根据真实需求组织模块，不为尚未出现的扩展预建复杂框架。

**经 §3.5 查证仍有必要的业务代码必须全部做成 Skill。** 文档清点/解析与 OCR、长文档切分和跨页重建、字段提取、证据关联、标准化/金额/匹配/增量/AR/AP、人工修订影响、题目 JSON 导出和反馈改进，分别归入 `backend/skills/` 下的业务包；规则说明在 `references/`，必要实现与可独立调用的校验函数在 `scripts/`，schema/映射可按需放 `assets/`。每包必须有有效 `SKILL.md` 和实际使用的 `references/`、`scripts/`，遵循官方 Agent Skills 格式，不只包一层提示词而把算法留在 backend；官方能提供的能力直接引用/组合，不为满足目录形式复制其实现。

通用 backend 只承载官方 Agent/middleware 装配、模型/MCP、文件与记录存取、配置/版本、HTTP 等宿主能力；不隐藏财务算法、解析分支或领域 SQL。Skill 不反向导入 backend/hooks，不绑定默认记账主体、数据库表或开发机路径，跨包依赖显式声明；前端复用包提供的字段/契约，避免复制财务判断。新增业务通过发布、挂载 Skill 及工具配置接入，不向主控追加固定业务 DAG。完整八包职责和移植合同见 `docs/skills-and-hooks.md`。

### 7.1 主编排与工具扩展

- **主编排必须使用 LangChain。** 采用 LangChain `create_agent` 作为主控，通过配置选择模型和工具。LangGraph 可作为其底层运行时或工具封装的局部子流程，不能直接照搬案例的顶层 `StateGraph` 替代主控。
- 规划必须覆盖任务所需信息的检查与补齐，包括当前记账主体、输入文件、已有账单和可用工具；不要把规划仅实现为固定步骤列表。
- 主控通过官方 `TodoListMiddleware/write_todos` 维护运行时计划，显式启用并复用 `content/status` 和原生状态/检查点，Vue直接展示todos。不要自建PlanService、submit_plan/revise_plan、步骤DAG或第二套可写计划事实。
- 支持依据新材料、失败、人工修订及能力变化调整todos，保留可复用产物并重算受影响业务结果。材料范围、revision、问题与执行回执作为业务引用保存；todo完成不代表财务完成，只有覆盖、证据、金额和当前revision校验通过才能形成相应正式结果。重规划不重置预算/纠错轮数或重复副作用。见 `docs/implementation.md` §3。
- 用户允许集成 OpenAI Codex 或 LangChain Deep Agents 作为可选大脑，但它们只能作为 LangChain 主编排调用的子 Agent 或工具，不能接管或替换主编排。
- 这些选项是用户允许的集成方式，不代表必须同时接入；只有具体任务需要时才增加相应适配器，并核对其模型、认证和工具执行方式。
- 工具优先直接使用LangChain工具、`langchain.mcp`和官方middleware装配；配置保存标识、描述、启用状态、参数和必要服务信息。只补配置加载及必要动态解析，不构建独立工具调度框架或工作流语言。
- 服务连接、模型和密钥放在 `backend/.env`；工具清单及非敏感的结构化选项可以使用单独配置文件，实际格式在实现时确定并提供示例。
- 工具启停及参数配置必须实际影响 Agent 可调用的工具集合；不能只提供配置文件而仍在代码中写死全部工具。
- 用户进一步要求支持按需子 Agent、MCP 和 Skill 的热插拔及实际调用、Hook 拦截，以及人工修改、暂停和续跑。以下小节为后续开发与验收要求，不代表当前已经实现。
- 文档解析、OCR、模型调用和账单业务规则保持清晰边界，以便独立替换和测试。不要为了扩展能力先建设与任务无关的插件市场或管理平台。
- GaussDB/Redis 中的命名、表结构、键用途和生命周期须在实现中明确；不擅自清空既有数据或修改无关业务表。

### 7.2 主控与专职子 Agent

- 主控始终为 LangChain Agent，负责规划、任务分解、信息补齐、子任务调度和最终汇总。
- 使用Deep Agents官方 `SubAgentMiddleware` 委派。文档专家优先 `create_deep_agent`，账单专家可用 `create_agent`；预编译专家通过 `CompiledSubAgent` 注册，显式配置模型/工具/Skill/middleware并采用隔离上下文。当前已安装并验证 Deep Agents 0.7.29；更改组合仍需重新查证和验证。
- 初始专职角色包括文档提取 Agent 和账单核对 Agent：前者使用文档与证据 Skills 提取字段及来源，后者使用财务 Skill 分析跨材料关联、修改意图和财务方向，返回候选结果；业务实现不放在 Agent 装配文件中。
- 复核首先由独立 Hook 调用 Skill 中的确定性校验完成；按风险或具体语义问题启用独立上下文的审查子流程，不要求简单账单都增加模型评审。另一轮相同模型的意见不能替代来源证据或金额校验。
- 子 Agent 的名称、描述、模型适配器、可用工具及 Skill 集合通过注册配置定义。按任务调用所需角色，不要求每个任务都运行全部角色，也不为每个普通函数增加一个 Agent。
- 独立附件可以并行提取；同一账单的最终合并与变更裁决调用所属Skill的唯一规则实现，宿主提供条件写入与回执，不能由多个子Agent分别直接覆盖，也不能把领域算法放回宿主业务服务。
- 传递给子 Agent 的上下文包括任务标识与目标、输入材料引用、记账主体、当前 revision、人工确认字段、规则/能力版本和输出结构；子 Agent 返回标注输入版本的结构化提案、问题及证据，不依赖隐式共享聊天历史或只返回最后一句自然语言。
- 首期选择Deep Agents官方子Agent；Codex仅在后续确有需要时评估。外部Agent不天然受全部内部Hook管理，接入时限定提案或显式适配其实际工具路径，不声称能拦截任意内部动作。

### 7.3 MCP 与 Skill 热插拔

热插拔优先复用官方MCPAdapter、动态工具middleware与Deep Agents SkillsMiddleware，项目只保存配置版本并补薄刷新/派发检查，不自建插件运行时或Skill引擎；安装SDK不代表热更新已经验收。

- 当前已安装 `langchain[mcp]==1.4.6`，优先采用内置 `langchain.mcp` 接口；旧 `langchain-mcp-adapters` 仓库已声明停止主动维护并迁入该接口，不新增旧包作为默认方案。2026-10-21 已按用户要求补齐可选依赖，包含 FastMCP 4.1.2、MCP 2.3.0；依赖冲突检查、导入和真实本地 stdio 工具发现及发现上下文退出后调用已通过。`backend/requirements.lock.txt` 保存完整依赖，验证入口见 `docs/portable-environment.md`；外部 MCP 服务、业务网关与热插拔仍需后续集成验收。API 与连接生命周期研究见 `docs/research/langchain-extensions-crosscheck.md`，其中未安装描述属于补齐前快照。
- MCP 注册管理覆盖连接配置、连接测试、工具发现、schema 校验、启用、禁用、刷新和连接释放；远程 HTTP 和本地 stdio 使用对应适配器。
- MCP工具直接通过官方适配进入LangChain工具集合；动态发现同时配置模型可见工具与实际执行resolver，并记录服务、工具版本及结果。调用仍经过原生middleware和必要业务检查。
- 工具来源保存项目自身的服务标识、配置版本和适用调用主体；MCP 服务自报的名称与实现信息不能代替配置身份或授权依据。模型可见工具集与执行时 resolver 都受同一能力版本约束。
- Skill 是版本化指令、脚本和配套资源。复用官方 `SkillsMiddleware` 发现、渐进披露、pin 和工具关联；`sources` 指向包含 Skill 目录的父目录。配套 `FilesystemMiddleware` 读取正文/资源；在run之间或after_agent将 `skills_metadata` 置None，下一run重载，分别处理父子Agent状态，不在当前运行中途重载。发布固定版本目录，记录实际使用版本，工具调用仍经过业务策略。
- **官方已有 Skill 执行能力，不自建通用执行器。** `FilesystemMiddleware` 在 backend 实现 `SandboxBackendProtocol` 时提供原生 `execute`，通过现成执行 backend 运行包内脚本；`StateBackend` 本身没有执行能力。Skill 也可经官方 `tools`/`SkillToolResolver` 绑定包内函数或现成工具，由 LangChain 原生工具调用执行。`metadata.include_tools` 是 Deep Agents 扩展（文档要求 `deepagents>=0.7.22`），为空格分隔字符串，不是 YAML 列表；它不自动注册任意脚本。
- `pinned_skills`另要求 `deepagents>=0.7.23`，本方案使用pin，依赖组合须满足该门槛。pin在下一模型调用前插入内容快照，未知/不可读项会跳过，输入键消费后清空；须验证实际内容与工具披露，不能只凭请求带该字段判定成功。以上是官方能力下限；当前已安装0.7.29，实际pin/读取/工具披露测试另见验收，不能仅凭版本推导其他组合兼容。
- pin输入键消费不删除已插入的消息，再pin会追加当前快照；元数据刷新也不会替换历史指令。版本迁移须明确处理旧快照及审计，不能把同时存在的两版都当当前有效规则。Skill工具隐藏只针对交给SkillsMiddleware的工具，Agent全局同名工具本就可用；摘要移除对应消息后也须验证披露状态。
- 先查 MCP 再选择实际执行 backend，验证 Windows/便携/Web 服务兼容性、文件同步、依赖与回执。官方 `LocalShellBackend` 无操作系统隔离，文档不将 Web/API 和不可信输入列为适用场景，不能默认用它替代隔离 backend。远端 sandbox 的账号/运行条件未落实时不能写成已可用；`CompositeBackend.execute` 走默认 backend，资源路由不自动同步执行环境。具体选择见 `docs/skills-and-hooks.md` §4。
- 支持从前端或配置添加、启停和更新 MCP/Skill，无需重启整个服务。配置经过校验后发布新的能力版本；加载失败时保留上一有效版本并显示错误。
- 下一次规划或安全步骤边界可读取新能力版本；一次已经发出的调用固定其实现与参数，不能执行到一半混用新旧版本。
- 对远端 MCP，固定本地包装对象不能阻止服务器原地升级；须核实服务是否支持不可变版本或版本校验。无法保证时明确记录限制，副作用工具按策略重新规划或审批，不宣称已固定远端实现。
- 禁用应在实际派发工具前再次检查，并立即禁止尚未派发的新调用。对已经发出的请求记录真实结果，不能声称配置禁用能够撤回远端已执行的操作。
- 旧 MCP 连接等在途调用结束后释放。恢复任务所需版本不可用时，明确提示重新规划或迁移，并使受影响的审批失效，不静默替换实现。
- Skill 文本不能提升其可执行权限。项目中配置的工具调用和脚本入口要经过同样的参数校验、Hook 和审计。
- 本地 stdio MCP 所需的额外可执行程序应纳入便携交付或明确运行条件；不能因为开发机装有 Node 等程序就假设交付机器也具备。

### 7.4 Hook 拦截与执行事实

- 模型调用和工具调用优先复用 LangChain 现成 middleware。**每种校验是独立 Hook**，包括 schema、覆盖、证据、金额、匹配、增量更新、AR/AP、revision、审批、能力启用和预算；在 `backend/hooks/` 独立维护，通过 `backend/config/hooks.yaml` 和薄装配入口统一管理，不建设另一套事件运行时，也不冒充内置 before_commit API。
- 领域校验的唯一算法留在对应 Skill 的 `scripts/`；Hook 负责触发、引用固定版本入口、解释结果与裁决，不能复制金额或证据规则。Agent 主动校验和正式产物/导出使用同一份函数，后者依据最新 revision 强制执行，不由模型决定是否跳过。业务 profile 声明必需 Hook，缺失/禁用/异常时不能放行正式输出。
- Hook 覆盖规划/模型调用前后、工具调用前后、产物提交/导出、异常、暂停和恢复；框架事件映射到官方 middleware，业务事件在通用产物入口显式接入。本地工具、MCP 工具及受控子 Agent 工具按实际调用路径装配；FastAPI 的人工编辑/导出不天然经过工具 middleware，必须进入同一校验入口。
- Skill 元数据发现/pin 和脚本内部 HTTP/SQL/子进程不自动逐项生成工具 Hook 事件；需要逐请求控制时在实际客户端/工具边界处理。原生 `execute` 的工具消息成功不等于进程退出码为 0 或业务通过，须分别检查 `ToolMessage.artifact` 执行结果、schema 与业务校验。校验入口不得再次触发自身 Hook 链造成递归。
- 配置 Hook 的触发事件、匹配条件、优先级、启用状态和处理器。前置 Hook 可允许、拒绝、要求人工介入，或提交受约束的参数修改；修改后的参数必须重新校验，既有审批不能直接套用。
- 拦截结果必须改变执行行为：拒绝后不发生外部调用，暂停后不继续提交，不能只写一条日志仍执行原动作。
- 通过原生middleware wrapper在每次实际派发前检查暂停、启用状态、revision/配置、审批参数和预算。采用动态resolver → HITL → 原生ToolRetry → 薄检查/计量 → handler，使内部重试重新经过检查；策略拒绝不当作网络故障重试。参数变化后重新校验，动态工具不得绕过handler。
- 审批等待后在取得派发许可时原子重验相关业务版本、参数和预算；运行所有权及调度优先交给官方服务，不另建带计划步骤和分布式租约的执行系统。已发生的外部操作靠幂等/回执核对，旧运行不能覆盖新revision；不能假设本地暂停可以撤回远端动作。
- 金额/币种无效、账单版本过期、明确冲突、工具已禁用等情况在对应调用或提交前拦截。哪些操作必须人工确认由项目策略明确配置，不将所有只读步骤都变成审批。
- 工具执行状态与 Hook 执行状态分别保存。工具成功而后置日志/Hook 失败时，保留真实回执，修复或重试后处理，不能重新执行已成功的账单变更。
- 必须执行的业务校验 Hook 失败或超时时不能继续提交；只负责观察和日志的 Hook 失败不能把已发生的业务事实改写为未发生。

### 7.5 人工介入、纠错与恢复

- 前端支持主动请求暂停，以及系统因缺失信息、冲突或校验失败而进入待输入/待复核；这些任务状态与账单操作 `PENDING_REVIEW` 分别建模。
- 人可以补充记账主体、修改提取字段、拆分或删除误提取费用、选择正确候选账单、补充证据，以及批准、修改或拒绝待执行动作。
- 锁定版本的 LangChain HITL 已支持 `approve`、`edit`、`reject`、`respond`，以及批量和逐调用中断；按实际接口适配前端。`edit` 后仍须通过业务校验，不能把框架恢复视为财务审核通过。`respond` 是跳过真实工具并合成人工结果，框架中的成功工具消息不是执行回执；不能用它表示拒绝或伪造已完成的账单变更。
- HITL 的 `edited_action.args` 是完整替换，不是字段补丁。前端只修改一个字段时，后端基于审批绑定的调用版本组装完整参数并重新校验，不能丢失未编辑字段；逐调用模式还须保持原工具名。字段编辑与工具审批使用不同的请求契约。
- `per_call`一次提交多项回答时，其中一项无效不代表其他工具尚未执行，即使界面仍显示pending。提交前逐项验证response_schema，优先逐项回答；出错后刷新中断状态并核对真实回执，只处理未完成项，禁止整批重发。HITL外层middleware在恢复时可能重放，调用handler前不得执行不可重复副作用。
- 前端展示原始材料、来源定位、旧值、新值、校验问题和修改影响；人工编辑生成新版本，不覆盖原始 OCR 或历史提取结果。
- 人工修改提交携带期望版本，过期编辑返回冲突及最新差异；不能静默覆盖其他人的修改。
- 纠错后重算受影响的派生字段、匹配结果和 AR/AP，并使依赖旧内容的校验、审批及导出失效。例如修改币种需重做金额汇总和匹配，修改记账主体需重做财务方向判断；未受影响的原件解析/OCR 可以复用。
- 人工确认的字段在当前版本中作为明确输入保留，后续模型重新提取不能无提示覆盖。人工修改本身也需通过类型及业务校验，不能因人工输入就绕过金额合计等检查。
- 审批绑定具体账单版本、动作及参数、工具版本和规则版本；批准后内容发生变化必须重新校验，并按策略重新审批。
- 暂停首先阻止新操作派发，在途调用结束后记录结果，在下一可控边界停下；不能把“暂停按钮已点击”说成已撤销外部操作。
- 恢复绑定同一任务、检查点和人工请求，保留业务revision、人工修改、配置版本与回执。由官方 Agent Server 生命周期配置现成 AsyncSqliteSaver，不在 Agent 工厂重复注入 saver；本地 dev 元数据仍周期刷盘，重启与硬崩溃分验，不能承诺跨存储零丢失。更强持久化采用官方部署条件，不默认自写GaussDB检查点。
- 子 Agent 的人工介入与工具拦截显式配置；嵌套中断由顶层运行边界收集并按实际中断标识恢复。业务人工修改另存 revision 并重算依赖，不能仅用 `Command(resume=...)` 或直接改聊天历史代替。存在并发或嵌套中断时，不能只取第一项决策或用模糊的同一问题文本定位。
- 检查点更新不会实时修改在途函数的局部状态；人工编辑在可控暂停边界生效，恢复时读取新 revision。MCP elicitation 的补充输入与工具审批分别建模；嵌套恢复或 elicitation 恢复可能重跑节点、重新发出工具请求，重放前核对幂等记录与真实回执。
- 恢复和重试不能重复执行已经完成的外部副作用；结果未知的操作先核对状态。已完成的外部提交如需更正，应执行明确的更正动作，不通过修改本地状态伪装回滚。
- 默认人工纠错只作用于当前任务；是否沉淀为费用映射、规则或共享 Skill 由用户另行明确选择，不自动修改全局知识。

### 7.6 稳定性与准确性

必须围绕实际失败场景实现并说明：

1. **结构化输出约束**：验证模型输出，区分模型调用失败和业务信息不足；无法修复时给出明确错误或复核状态。
2. **来源证据**：提取字段关联文件及原文位置，保留 OCR、提取、标准化和最终决策之间的依据。
3. **确定性处理**：金额、匹配、更新和重复处理规则可以脱离在线模型单独测试。
4. **可复现样例与评测**：为关键场景维护输入、预期结果和断言，分别观察提取、匹配、AR/AP 和误更新等问题。
5. **外部服务隔离**：离线测试使用固定 OCR/模型响应，在线集成测试单独运行；真实响应若用于回放应脱敏并标明来源。
6. **有限失败恢复**：对真实可恢复的服务错误设置超时及有界重试，重试不造成重复账单；不以无限重试掩盖问题。
7. **复核与诊断**：冲突、歧义及关键校验失败能够定位原因，不能被宽泛异常捕获吞掉并转换为成功。

具体模型、提示词、依赖版本和必要参数应可配置、可追溯。不要把正则匹配或硬编码示例伪装成模型智能体，也不要依赖 Codex 会话才能完成业务流程。

### 7.7 Harness 的职责与框架边界

- Harness以LangChain/Deep Agents及官方服务的原生执行、上下文、middleware、中断、检查点和流式能力为基础，只补题目需要的覆盖/证据/金额/版本/回执/共享计量与评测；不另写Agent runner或通用执行网关。提示词或日志不能单独证明harness完成。
- 原始材料和证据存档独立于模型聊天上下文；传入子 Agent 的是显式任务、引用和版本。摘要不能成为财务证据的唯一副本，也不能丢弃人工修订或尚未解决的问题。
- 主控和所有子 Agent 共用任务级模型/工具调用及活跃执行时间预算；子调用与重试均计入，不能在每次委派时重置。首期起始配置为每个受影响产物自动纠错最多 2 轮、独立文档并发最多 3 个、每次运行模型调用最多 24 次、工具派发最多 64 次、活跃执行时间最多 1200 秒；人工等待与排队时间单独记录。以上为实现初值，不是样本评测结论，调整时记录版本与依据。
- 评分器、上下文摘要、结构化输出修复和优化器等附加模型请求也经过统一模型工厂，实际关闭思考并计入对应运行的共享预算；不能仅统计主控外层调用。局部评分器重新启动可以重置自身迭代数，但不能重置任务预算。框架回调或私有状态需按锁定版本适配，明确区分评分通过、失败、异常和上限终止。
- 预算与并发必须由计数器、执行器和实际派发检查约束，不能只写在提示词里。到限后停止新派发、保存真实在途结果并返回明确状态；模型停止调用工具或图结束不等于账单已通过验证。
- GaussDB保存业务revision、人工修改、执行事实与恢复依据；Agent Server管理运行队列和框架状态，Redis按需要用于缓存、限流或通知，避免重复建队列。GaussDB不能未经验证替代官方服务内部PostgreSQL；内存saver不能证明跨重启持久化。
- 首期设计采用Deep Agents官方子Agent与middleware，不再自研相同能力。其内部工具及摘要/修复模型显式接入业务策略、关闭思考与共享计量，不假定父Hook继承或wrap_model_call覆盖所有内部请求。新增包兼容性与API先经MCP和实际运行核实。

### 7.8 有界纠错与双向反馈

- 本项目采用可以回退修订的任务循环：主控规划 → 提取/核对提案 → 代码校验与按需语义复核 → 通过、定向修复或人工介入。不是只允许向前执行一次的流水线，也不采用无限自我评议。
- 校验问题使用结构化契约，包括问题代码、受影响字段、来源、期望约束、可修复性和影响范围。反馈指向具体子任务，只重做必要部分；修复后重新运行相关校验，保留每轮候选、差异和依据。
- 相同候选与相同问题重复出现、没有新增证据、需要调用方判断或达到纠错/任务预算时，提前停止自动修复，进入待补充、待复核或明确失败；不能生成一个未经验证的成功结果。
- 人工输入以新 revision 进入同一反馈回路，按 §7.5 处理字段约束、依赖失效、重新校验和恢复。当前 revision 已人工确认的字段不得被下一轮模型静默覆盖。
- 应用层反思指对照原始材料、规则和差异复核候选；所有规划、提取、评审和优化模型调用仍实际传递 `enable_thinking=false`，只记录可核验的短业务依据，不输出内部思维链。

### 7.9 跨任务改进与版本发布

- 区分当前任务的行动循环、当前任务的纠错循环、跨任务的改进循环。一次纠错默认只改变当前任务，不能直接覆盖全局规则、共享 Skill 或提示词。
- 用户明确选择沉淀后，可根据反馈生成候选费用映射、规则、提示词或 Skill。保留来源、提出者、旧新差异、适用记账主体/交易方/单据类型及候选版本，候选与当前有效版本分别存储。
- 发布前用固定样例比较 baseline 与候选；区分用于反馈/生成候选的样本、用于多轮候选选择的回归或验证样本，以及不参与本轮生成和选择的最终独立评测样本。反复参与接受/拒绝候选的 holdout 已属于选择过程，不能同时充当最终独立测量；如将最终评测反馈用于下一轮改进，记录用途变化。按业务与单据家族去重划分，避免同邮件或近重复附件跨组泄漏。模型生成标签不能直接当真实答案。
- 金额、币种、主体、AR/AP、误新增/误更新、同名多行误合并、来源丢失及重复副作用分别设确定性断言。已覆盖的关键错误不得新增；不能以平均分上升掩盖关键场景退步。报告展示收益、退步、失败样本与覆盖范围。
- 评测通过后经明确审核才发布新版本，可回滚到上一有效版本。运行中任务固定版本；热更新及迁移遵守 §7.3，不能把评测中的候选直接注入在途任务。
- 此能力是规则、提示词和 Skill 的可评测改进，不宣称进行了模型权重训练，也不允许线上 Agent 自行改写业务代码或静默发布全局财务规则。离线评测器可以按需使用 OpenEvals/LangMem 等组件，但组件存在不等于本项目已经验证改进收益。

### 7.10 时延、前端体验与性能验证

- API快速受理，长任务优先使用官方Agent Server后台运行，前端显示真实阶段、已处理范围、在途调用、复核项和部分结果；不另建Agent runner。
- 刷新和断线重连优先复用官方Vue SDK与Agent Server快照/订阅/回放合同，业务产物按revision查询；不自行再造事件序列与重放服务器。实际缓存保留和重启恢复边界必须验证，Redis通知不是唯一事实。
- 恢复测试覆盖运行启动/订阅交错、嵌套中断、重连与版本冲突。时间区间按任务互斥统计，任一分支仍执行时计活跃；单个人工请求等待可重叠但不能重复加到端到端时间或扣减活跃预算。
- 首次反馈、首次可验证结果、最终完成、排队及人工等待分别计量，按材料规模、格式、并发与缓存命中记录 P50/P95；架构中的数值属于待实测设计目标。
- 复用不变原件的解析/OCR，人工修改只重算受影响结果；并行、限流、队列背压与上下文容量由代码约束。界面草稿不能冒充通过校验的正式账单。
- 目标目录、业务API、官方服务/协议组合、Vue工作台和性能设计见 `docs/implementation.md`；开发后以实际压测和业务结果更新状态。

## 8. 验收场景

开发时以以下场景逐项验证；测试输入和实际结果应有据可查：

| 场景 | 验收重点 |
| --- | --- |
| 含正文和多种附件的 EML | 邮件头、正文、附件递归解析及来源关联正确 |
| PDF 与图片调用 OCR | 请求符合指定接口，真实服务返回可处理；失败可诊断 |
| XLS/XLSX 与 DOC/DOCX | 正文/表格/费用行可提取，旧格式有实际支持路径 |
| 长 PDF、多单据与跨页续表 | 单据边界、原页映射和费用行完整，重复表头/承前转后不重复计费；失败范围与预算超限可见 |
| 跨页 Word、合并与嵌套表格 | 按内容顺序完整读取，来源锚点可靠，预览页码绑定渲染版本，不误用稳定物理页假设 |
| 新账单包含多个费用 | 每个有效费用单独输出，金额与币种正确 |
| 已有账单只更新金额 | `UPDATE` 仅修改金额，其余字段完整继承 |
| 重复执行及多文件重复描述 | 不重复新增；确认无变更时输出 `NO_CHANGE` |
| 同名费用多行、多候选账单 | 不误合并；不明确时进入复核 |
| 当前主体变化或收费方向不同 | AR/AP 随业务关系正确判断，不能只按单据类型分类 |
| 缺失字段、冲突、OCR 混淆及合计异常 | 不虚构字段，不静默纠错，不未经校验输出可执行账单 |
| 无效模型输出、OCR 超时和损坏附件 | 错误可见且可定位，不伪装成空成功 |
| JSON 交付 | 数字类型、`null`、枚举和结构合法；审计依据可追溯 |
| 专职子 Agent | 原生委派与结构化提案可见；子Agent显式装配工具策略，不能假定继承主控Hook |
| 智能体运行时 Plan | 原生todos可见并由检查点保存，新证据/人工修改更新计划；实际业务完成依真实产物/校验，不绕过预算或幂等，不另建Plan/DAG |
| MCP 热插拔 | 服务无须整体重启即可新增工具；已规划但尚未派发的工具被禁用后，实际调用被阻止 |
| Skill 更新与调用 | 可看到使用的 Skill 版本；更新在边界生效，单次执行不混用版本，实际资源和工具调用可追溯 |
| 业务 Skill 与原生执行 | 每包有有效 SKILL.md/references/scripts，解析/财务/证据实现随包迁移；加载、工具披露和 execute 使用官方机制，实际 backend 与依赖验证通过，不把可读当可执行 |
| 独立 Hook 统一管理 | 各校验独立配置/处理器，复用 Skill 唯一算法；人工 API 和正式导出同样经过校验，禁用必需 Hook 不能绕过 |
| Hook 实际拦截 | 拒绝和暂停会阻止对应操作；参数修改后重新校验，不能仅记录日志 |
| 重试及动态工具派发 | 每次真实重试均经过原生handler内层的暂停/禁用/版本/预算检查；动态resolver不能自行执行绕过检查 |
| 后置 Hook 失败 | 工具成功事实和回执保留；恢复后只重试必要的后处理，不重复提交账单 |
| 人工纠错 | 修改金额、币种或记账主体后重算相关结果，旧校验与审批失效；无关 OCR 不必重复运行 |
| 人工暂停后重启 | 实测正常重启和硬崩溃的不同恢复边界，能按已保存状态续跑；不重复成功动作，未刷盘损失/未知结果明确可见 |
| 并发人工编辑 | 旧版本编辑不能覆盖新版本，前端可看到冲突与差异 |
| 有界纠错与无进展 | 可定位错误能回到对应提取/核对步骤；重复候选或两轮未修复进入复核，不能把预算耗尽当通过 |
| 共享任务预算 | 子 Agent、MCP 与重试共同消耗调用预算；达到上限后不再派发，人工等待单独计时 |
| 反馈沉淀与评测门禁 | 当前任务修改不自动更新共享规则；明确选择沉淀后生成候选，关键场景退步不能发布 |
| 最终独立评测 | 多轮选择集不冒充最终评测集；关键财务错误单独判定，隐含模型请求计入预算 |
| 能力发布与回滚 | 候选与有效版本分开，审核后发布，可回滚；在途任务不混用规则/Skill 版本 |
| 长任务体验与性能 | 实际进度、局部结果、SSE 重连、暂停与刷新可用；按规模报告首反馈、最终时延与资源，不能把设计目标写成实测结果 |

文档变更进行内容核对即可。业务代码需运行与改动相称的测试；未实际执行或被外部条件阻塞的检查必须如实说明。模拟测试通过不能声称真实 OCR 或在线模型集成通过。

## 9. 后续开发与交付纪律

1. 进入实现阶段后，先读取真实样本并核实已有项目状态，再确定最小可交付实现和必要依赖。
   每个智能体操作先完成 Docs/API MCP 查证和安装版本核对，严格执行 §3.5：只有官方无对应具体能力才允许自写，Hook与业务脚本均不例外。代码编写及运行必须使用 stop-that-shit，前端编写必须同时使用 design。必要业务实现只进入 Skill，校验分别注册为 Hook；不自建已有的 Skill 加载/执行层。按 [最终开发计划](docs/superpowers/plans/2026-10-21-final-development-plan.md) 的依赖、步骤与完成条件执行，查证方式见 `docs/implementation.md` §14 与 `docs/skills-and-hooks.md`。
2. 核对模型接入方式、记账主体输入、已有账单结构、OCR 可访问 URL 获取方式及旧版 DOC 转换条件。能从材料或环境解决的问题自行检查；缺少的信息只询问必要部分，同时推进独立工作。
3. 通过项目内 `backend/python.cmd` 在 `backend/bishi1/` 便携式运行时中完成开发和验证，按需要补充 README、依赖声明、配置示例、测试和示例输出。
4. README 中的命令须与最终实现一致，不能把计划中的入口或未安装的依赖写成已可运行。
5. 使用本项目要求和真实运行结果说明完成程度，明确已实现、未验证及已知限制。
6. 打包时包含 `backend/bishi1/` 便携式运行时及其依赖、启动入口和项目文件，排除 `backend/.build/`、本机缓存和不应公开的业务原件；`backend/.env` 按用户明确要求随本地交付保留，是否公开发布另按用户指令。验证解包并更换目录后的运行说明及必要文件齐全。
7. 原题要求向指定邮箱发送交付物，但发送邮件属于后续独立操作，必须由用户明确授权；本文件不授权发送、发布或真实财务记账。

用户已授权实际构建并提供数据；本轮按批准的后端职责结构实施重构，优先完成需求与代码，暂不处理交付包。继续工作以当前代码、本轮实际报告和未完成验收项为准，不把旧目录或 ZIP 的通过记录作为本轮结论，也不把早期“仅设计”表述作为禁止继续实现的依据。
**2026-10-22 最新：原件定位与双视图证据。** 证据抽屉默认打开“原件定位”，另有“提取原文”页签。PDF文字层按实际字符几何定位，避免布局引文与PDF文本顺序不同导致无高亮；金额/币种复用证据Skill解析，重复位置保留候选。无文字层的PDF/图片使用便携环境RapidOCR生成只读定位框，不能改变提取事实。Office按原件哈希复用LibreOffice转PDF作为展示产物，Excel/Word结构视图仍保留。定向证据测试86通过，前端类型/生产构建通过；详见docs/research/original-location-and-evidence-tabs.md。未重跑真实OCR/Qwen账单或提交人工修改。
**2026-10-22 最新：主控 plan/replan 与中断恢复修复。** 复用原生 `TodoListMiddleware/write_todos`，将 todos 作为当前轮执行契约：首次或恢复时检查计划，只保留一个 in_progress，工具成功后只局部更新受影响项，仅在目标变化、人工补充事实、可纠正错误或阻塞时 replan。人工回复恢复时携带当前 todos、reply_id 与 revision，复用既有材料/OCR/提取产物，并禁用手工唤醒后的 intake、source-read、task-context 和 extraction 工具；已有成功提案或失败事实后不再向模型开放工具。主控提示同时规定相同 `(tool,args,revision)` 无进展不得重试、任务已完成不得追加“再检查一次”调用。当前 DeepSeek 工具运行时仍不执行自由文本 shell，已做静态补丁但本轮未运行 pytest；服务、真实 OCR/Qwen 和历史任务均未重启或重跑。

**更正：** 人工恢复阶段只硬阻断 `intake_documents`、`read_document_sources` 和 `save_document_extraction`；只读的 `read_task_context` 仍可使用，以免多费用场景缺少当前 id。

**2026-10-23 界面微调：助手标题栏与输入区压紧。** AgentPanel标题上下内边距17→8px、图标28→24px；输入框文本区76→44px，收紧发送栏、外边距和底部留白。桌面实测标题约41px、输入框约83px，聊天记录区域约337px；总面板仍480px，手机440px。Vue类型/生产构建通过；真实账单只填多行草稿后清空、未发送，桌面/390px无横向溢出且控制台无error。未运行后端测试/全量/模型/OCR，未启停后端。截图backend/tests/reports/compact-chat-bars-{desktop,mobile}.png。

**2026-10-23 修复：已批准/已完成仍显示“正在处理材料”。** 实际列表账单1为approved/R2、账单2为completed/R2，原生thread_status均idle，但存储run_status残留pending。前端taskIsProcessing此前直接把run_status=pending/running当成材料处理，优先于完成提示；现与taskCategory共用业务状态/当前revision审批判断，聊天run也不再让已结束账单变成材料处理中，等待/暂停/失败提示保留。已批准行明确显示“当前版本已批准，可查看或导出账单”。新增frontend/tests/taskPresentation.test.mjs共5项定向离线检查通过（修复前4项失败），Vue类型/生产构建通过；实际浏览器已确认账单1/2提示正确、控制台无error。仅修改前端展示，未改账单、审批或后端运行状态，未跑全量、模型/OCR或重启后端。截图backend/tests/reports/bill-status-attention-fixed.png。

**2026-10-23 最新：四项 Harness 收尾源码完成。** 用户放弃材料自然语言重写，要求实际退出、保护证据、收紧专家职责、统一预算。重复候选/纠错到限/证据退化保存 revision/运行绑定停止事实，原生 before_model 跳 end，专家返回 blocked，主控不再重抄整单；确定性保留候选并进入现有待办，停止不能冒充核验完成或人工批准。evidence-linking2.1.4 保存前回读两侧引用，拒绝非空字段从 supported 退化；缺失不填造、显式 null 可清空、有支持的新值可修改。document-extraction2.2.3 对错层 result.replace 等根参数报错，human-review2.0.7 提供停止待办。billing-specialist 工具清单限制只读，文档专家保留必要保存。HTTP 派发前主控/专家/重试/摘要/结构化回复共享单轮16、任务24次，每类专家每轮4次，给主控预留2次；重复委派不重置，真实回复新轮保留任务累计计量，续跑被拒绝保留停止事实。skills v39/agents v15/runtime v8。最终34项定向离线检查通过（20新+14既有，16.87秒），账单3已存材料回放拒绝第26条退化引用、允许第28条有支持修复。未跑全量/真实模型/OCR/正式数据库并发，未启停后端或迁移历史账单/能力，重载后新任务使用新配置；不据此声称线上提速或总体准确率。详见[四项收尾](docs/research/loop-controls-20261023.md)。
