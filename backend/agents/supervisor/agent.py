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
        stack.insert(0, SubAgentMiddleware(backend=backend, subagents=subagents,
            system_prompt='只把复杂提取或具体语义疑点委派给专家；简单任务直接完成。专家隔离运行，只看到本次description；由主控验收产物与证据。',
            task_description='调用已注册专家处理具体疑点。description必须是JSON字符串，包含goal、source_ids、charge_ids、questions、acceptance。'
                'source_ids/charge_ids使用当前任务真实ID；questions和acceptance各1-6条。不要传完整聊天、整包OCR或让专家重做整单。'
                '宿主会补充真实任务版本、候选和剩余预算。可用专家：\n{available_agents}',
            private_state_keys=frozenset({'thread_model_call_count', 'run_model_call_count',
                'thread_tool_call_count', 'run_tool_call_count'})))
    prompt = Path(__file__).with_name('prompt.md').read_text(encoding='utf-8')
    return create_agent(
        model, tools=tools, middleware=[TodoListMiddleware(system_prompt=PLANNING_PROMPT), *stack],
        system_prompt=prompt, name='workorder-agent',
    )
