# 常驻聊天与未完成事项提醒

2026-10-23，按用户要求将账单助手输入区改为常驻。本文覆盖历史“仅人工中断可输入”的交互，不改变财务字段、校验、审批或任务预算规则。

## 行为与接入

- `AgentPanel.vue` 保留固定面板高度，输入区始终存在。运行期间可写草稿，发送等待本轮结束；暂停/取消和线程未就绪时提示并禁止发送。标题下用紧凑提醒展示真实待答问题、未完成原生todos和异常状态，待答项可点击聚焦。没有新增独立待办数据库或轮询链路。
- 复用 `/api/tasks/{id}/reply`：带interrupt ID走原生resume；不带ID时，必须确认没有原生中断、未结束步骤或待打开review_request，然后在同一thread创建带HumanMessage ID的新input。沿用原有REST兼容路径、幂等reply_id、revision、实际运行检查、并发预留与共享预算；派发失败保留消息并允许重试。
- 普通消息直接由现有Agent回答，不经过只会返回“已记录”的额外意图分类调用。普通聊天仅提供只读来源工具、ask_user和record_review_decision，派发层同步限制提取/发布工具。此前已选费用不成为新聊天的默认修改对象。
- 明确修改经原有record_review_decision暂存提案，再用固定human-review Skill生成新revision、清除旧审批并重新核验；未提供的字段不会因聊天自动补值。普通问答不重算或改变业务状态、revision、审批、导出。
- 待答中普通聊天后原问题以新的真实原生中断保留。修改无关字段也保留原问题，并绑定修改后的revision。模型只有在当前回答确实解决问题时才设置工具参数`resolves_pending=true`；确认/暂缓仍须用户明确表达。原有主体/角色精确模板仅在对应范围内可直接处理。后续实际待答恢复已离线核对，不另建执行循环。

## 官方能力与最小适配

本会话已用Docs MCP查询并读取 `/langsmith/use-threads.mdx`，核对同thread多轮messages和原生interrupt/resume。API Reference MCP检索`RunsClient.create`，定位`/python/langgraph-sdk/_async/runs/RunsClient/create`；详细符号get未解析成功，没有当作成功证据。另核对本地安装签名`RunsClient.create(thread_id, assistant_id, *, input=None, command=None, …)`。适用版本：LangChain1.4.6、LangGraph1.2.16、langgraph-sdk0.4.8、DeepAgents0.7.30。

运行、线程、消息、中断和重放全部使用既有原生组件。新增部分仅处理本项目的聊天显示、业务状态保持、reply传输记录及未解问题保留，业务修订仍由现有Skill执行。沿用Agent Server0.16.2显式REST input兼容行为，没有新增runner、队列、摘要模型或OCR路径。

## 实际验证与边界

仅运行定向离线检查，未运行项目全量：新增`test_persistent_chat.py`最终16个用例分批通过；既有`test_conversation.py`选取8项通过。覆盖同thread普通输入、重复请求、内容冲突、旧revision/暂停/预算/运行中/真实待答/待打开问题/在途消息阻断、派发失败保留及重试、强行调用提取/发布工具被拦截。普通问答与自然语言修订还通过完整`base_stack`的真实原生图和离线模型运行；问答仅一轮且审批/导出保持，修改生成revision2和新版校验。小聊天/无关字段修订后原问题仍有原生interrupt，随后按新revision明确暂缓成功且不重复应用修订；实际回答当前问题可正常关闭该待办。

前端`npm run build`通过（Vue/TypeScript与Vite，2504 modules）。浏览器在真实现有账单填写后清空草稿，输入常驻且有内容时发送可用，未发送。待办/处理中使用独立合成Vue预览，验证展开列表、去回复聚焦、处理中草稿及发送禁用；390px下面板350×440px、无面板或页面横向溢出，控制台无error，临时预览已移除、viewport已恢复。截图在`backend/tests/reports/persistent-chat-{desktop,todos-desktop,todos-mobile}.png`；后两张为合成界面。

未调用真实付费模型或OCR，未修改真实账单，未重启/启停后端，也未在线发送新聊天回合。前端已构建；后端进程需重载新增路由/中间件后才能使用新聊天路径。测试不代表在线模型对所有自然语言修改的理解准确率。任务继续使用既有有限共享预算，暂停/取消时只能保留草稿。
