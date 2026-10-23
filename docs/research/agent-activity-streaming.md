# 实时执行过程修复（2026-10-21）

用户报告过程区持续转圈，没有新增工具或消息。上轮12项浏览器检查注入了合成v2事件，验证了展示，却没有验证生产后台运行的实际事件格式。

## 原因与修复

`backend/api/task_runtime.py`原先通过`runs.create`启动旧协议运行；Vue1.2.5通过`/threads/{id}/stream/events`订阅原生v2事件。真实线程有values和生命周期快照，却没有消息块与工具事件；大多数AI回复本身没有公开文本，动作在tool_calls中。官方工具投影只对已存在的handle进行values对账，不能依靠它补齐所有新调用，因此界面看起来不动。

后台启动改用官方`POST /threads/{id}/commands`的`run.start`，通过官方Python SDK的`HttpClient.post`发送。服务自身开启完整messages/tools/lifecycle等通道、子图和可恢复流；项目不新增SSE实现、工具消息装配器或Agent运行循环。调用方上下文、revision、并发reject及运行受理后保存run_id继续保留。HTTP200中的协议error也判为失败，禁止误标记任务已启动。恢复请求交给同一原生入口的force_resume及input/update/goto。

另一个实际问题是启动竞态：页面先打开而首个检查点尚未生成时，官方Vue SDK把`next=[]`识别为idle，推迟订阅。AgentPanel观察已有任务刷新中的run_id/run_status及真实模型/工具计量：任务仍活跃且SDK未进入执行时，重新挂载官方订阅。仅这些标量变化才触发，不因同值刷新重复挂载。没有新增轮询定时器，也不伪造事件或重复派发任务。旧协议失败任务可能保留next非空的检查点，SDK据此误判运行中；显示层以API返回的终态run_status排除转圈并显示停止提示，实际历史失败任务已只读验证，不恢复它。

## MCP与版本依据

本轮使用stop-that-shit change、design；查询LangChain Docs MCP的Protocol v2 Command/Event Stream、checkpointers durability及测试模型指南，API Reference MCP的useStream、AsyncThreadStream/RunModule、HttpClient与GenericFakeChatModel。安装组合为langgraph-api0.16.2、langgraph-sdk0.4.8、langgraph1.2.16、@langchain/vue1.2.5。

官方公开命令接口是首选，但当前0.16.2的`event_streaming/service.py`在run_payload中将durability固定为None，直接迁移会丢掉原有sync设置。因此只有这处兼容使用已安装LangGraph的`CONFIG_KEY_DURABILITY`（内部`__pregel_durability`），放进configurable；`Pregel._defaults`在durability为None时读取此默认值，原生运行再将它传给子图。本轮真实运行配置已确认保留sync、reject、完整stream_mode和resumable。此内部键不是公开稳定API，升级以上版本必须重核已安装实现和定向集成；公开命令支持durability后应移除此适配。

曾尝试给旧runs.create设置v2 marker，但旧REST schema不接受tools/lifecycle，过滤后又丢失部分可恢复工具事件。因此最终使用官方commands完整路径，源码没有保留该方案。

## 本轮验证

- 新回归先复现失败，修复后`test_task_runtime_streaming.py`及`test_task_deletion.py`共19 passed、1条既有MCP beta warning（5.37秒），不运行全量测试。
- Vue类型与Vite最终生产构建通过：2418 modules、Vite1.07秒，入口index-DzfPQr8K.js，AgentPanel-gK4gJAFb.js。
- 独立2025端口的真实官方Agent Server运行`create_agent`，仅模型使用官方GenericFakeChatModel的测试子类、材料与业务GET使用合成数据；原生后台启动适配器、队列、检查点、SSE及生产Vue实际执行，没有注入协议帧。
- 页面先打开再后台启动，无手动刷新即可展示；最终构建真实收到47条messages、4条tools（2 started/2 finished）、6条values、4条lifecycle（含两路订阅）。观察到29次界面内容变化，回复逐步追加、展开中的工具更新结果、结束后收起；刷新恢复2条完整调用，390px无横向溢出，无pageerror。当前真实失败任务不再显示运行徽标或转圈。
- [原生链路回执](../../backend/tests/reports/agent-activity-native.json)、[执行中截图](../../backend/tests/reports/agent-activity-native-running.png)、[完成截图](../../backend/tests/reports/agent-activity-native-finished.png)、[定向回归](../../backend/tests/reports/agent-activity-streaming-pytest.xml)。隔离图源码在backend/tests/fixtures/activity_streaming.py，启动适配调用记录在backend/tests/reports/verify-activity-start.py；临时配置和状态在backend/.build/activity-stream-fixture，与正式服务隔离。
- 无busy时向核实过的独立服务控制台发送Ctrl+C正常关闭，再用相同官方选项启动PID19252。28个既有线程ID和状态一致，GaussDB/Redis健康；[重启回执](../../backend/tests/reports/agent-activity-restart.json)。

未调用真实OCR/Qwen、未修改/重跑/代答/审批用户账单。现有旧协议运行不转换；历史已完成工具仍从检查点恢复。原生长断线与多层子图矩阵不在本轮范围，上一轮模拟展示检查也不能替代这些验证。
