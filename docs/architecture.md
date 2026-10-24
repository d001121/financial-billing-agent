# 架构入口

[实现说明](implementation.md) 统一维护模块、材料流、执行与扩展边界；[项目答辩](project-solution.md) 对照题面解释取舍。

LangChain主控通过原生工具及按需专家理解材料，八个业务Skill承载领域规则，十一类Hook检查证据、金额、版本及导出。Agent Server管理运行与流，LangGraph检查点保存状态，Vue通过官方SDK订阅同一线程。

不另建Agent runner、固定财务DAG、Skill引擎或消息重放服务。开发要求见 [AGENT.md](../AGENT.md)，验证边界见 [验收记录](acceptance.md)。
