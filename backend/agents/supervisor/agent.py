"""Native LangChain supervisor with Todo and compiled specialist delegation."""

from pathlib import Path

from deepagents.middleware.subagents import SubAgentMiddleware
from langchain.agents import create_agent
from langchain.agents.middleware import TodoListMiddleware

PLANNING_PROMPT = """使用已pin的Skill正文，只有缺少正文时才读取Skill文件。简单任务用write_todos建立1-2项
结果目标，复杂任务最多5项，同一时间只有一个in_progress。与业务工具在同一轮批量更新真实计划变化，
不为每次阅读、保存或结束动作单独增加计划轮次。仅新证据、错误或目标改变时调整路线；人工回复轮不更新todos。
完成以真实产物、证据和当前revision校验为准。
"""


def build_supervisor(model, tools, backend, middleware, subagents):
    stack = list(middleware)
    if subagents:
        stack.insert(0, SubAgentMiddleware(backend=backend, subagents=subagents))
    prompt = Path(__file__).with_name('prompt.md').read_text(encoding='utf-8')
    return create_agent(
        model, tools=tools, middleware=[TodoListMiddleware(system_prompt=PLANNING_PROMPT), *stack],
        system_prompt=prompt, name='workorder-agent',
    )
