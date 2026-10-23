# 持久化与恢复实测

更新：2026-10-21。框架执行状态与业务记录分别保存。本轮按职责重构后已核验三个历史任务的checkpoint、19/9/17条消息、原中断和revision保留，未新建或恢复Agent运行，见backend/tests/reports/responsibility-after.json；下述重启实验保留原验收版本身份。

| 存储 | 职责与边界 |
| --- | --- |
| GaussDB | 任务、业务 Revision、产物、审批、预算和回执；psycopg 事务、行锁、期望版本，不作为未经验证的 Server 内部 PostgreSQL |
| SQLite | 官方 AsyncSqliteSaver 保存消息、todos、中断与检查点；标准 backup API 备份，不能漏掉 WAL |
| .langgraph_api | 官方 dev 的线程/运行等元数据，周期刷盘，未刷盘窗口仍可能丢失 |
| data/assets | 原件、附件、派生件及 OCR 响应；storage_path 相对定位，兼容迁移前旧引用 |
| data/releases | 任务能力哈希固定的 Skill 内容，完整写入后原子发布 |
| Redis | 解析缓存，非唯一事实；不可用可重新接入 |

backend/langgraph.json 的 checkpointer.path 挂载官方 AsyncSqliteSaver；backend/infrastructure/checkpoints.py 只管理生命周期，没有自研 saver。官方 Server 负责向 graph 注入检查点。

## 验证结果

- 官方 conformance 的 58 个必需基础检查通过，报告为 backend/tests/reports/sqlite-conformance.json。
- backend/tests/test_persistence.py 关闭并重开 SQLite、重建原生 Agent，再按同一个 HITL ID 恢复；成功工具各执行一次。
- 整个 Agent Server 停止后重新启动，比较以下实际任务：

| 任务 | 重启后 |
| --- | --- |
| 合成 Excel abab67c9-2fe2-44fe-a416-6dbd92058b26 | 同 checkpoint ID，19 条消息、3 项已完成 todos、2 条费用和批准状态保留 |
| 原题 EML 29c0ae9b-f792-4b53-b1f8-2423e72d852f | 同 checkpoint ID，9 条消息、2 项 todos、中断 30832cf381a3f0f54da6b58e9a2db950 保留，仍 awaiting_input |

原始对比：backend/tests/reports/restart-before.json、backend/tests/reports/restart-after.json。停止时没有在途外部请求，EML 中断保留未答复。

另在无在途调用时对自己的 Server 执行 Stop-Process -Force，再启动整个服务；上述两任务仍保留同 checkpoint、19/9 条消息、批准状态或同中断 ID，预算未重置。报告为 backend/tests/reports/server-force-restart.json。该项只证明稳定检查点上的进程终止恢复，不代表断电、未刷盘新线程和 OCR 在途故障均已覆盖。

初始 dev 组合曾出现线程/运行仍在而检查点为空。改用官方 SQLite 后完成上述验证。旧任务若缺检查点会显示 checkpoint_unavailable / recovery_required；不能声称旧线程已恢复。恢复接口拒绝缺检查点直接续跑。

启动时若 active_depth 尚未结算，会保留中断区间并暂停为 recovery_required，不把停机时长算入活跃预算，也不杜撰中断期间耗时。

## 修订和副作用

人工编辑需 expected_revision，数据库锁内检查；旧版本返回409。新版本保留人工锁、删除墓碑和拆分历史，相关校验/审批/导出失效。重提取不得覆盖人工确认字段。

HITL 恢复可能重放外层 wrapper；动态解析不提前执行工具。审批之后、原生重试内侧重新检查暂停、启用、版本和预算。工具成功事实与后处理状态分别保留。远端副作用结果未知时仍需服务自身的幂等/查询合同，不能撤回已发送的请求。

## 已知边界

SQLite 缺三个 Server 可选扩展：adelete_for_runs、acopy_thread、aprune。项目使用 reject 多任务策略；复制走官方慢回退，长期历史裁剪暂不支持。

GaussDB、SQLite 与 dev 元数据没有跨库原子提交。历史打包需暂停、等待在途结束与元数据刷盘，再进行 SQLite backup，保留对应 assets/releases。多实例和断电级恢复应采用满足条件的官方生产部署；本地 dev 没有生产级零丢失承诺。

