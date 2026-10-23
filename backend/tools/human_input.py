"""Question tool governed by the native HumanInTheLoopMiddleware."""
from langchain.tools import tool


def human_input_tool():
    @tool
    def ask_user(question: str, choices: list[str] | None = None) -> str:
        """需要调用方补充信息或确认时询问；通过官方HITL等待respond，不能自行猜答案。
        确认记账主体时choices可提供材料中已识别的公司全称，用户仍可填写其他公司。
        """
        return '等待调用方通过HITL答复：' + question
    return ask_user
