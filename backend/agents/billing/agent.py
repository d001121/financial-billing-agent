"""Build configured LangChain specialists; billing algorithms live in Skills."""

from langchain.agents import create_agent
from langchain.agents.middleware import TodoListMiddleware


def build_billing_agent(model, tools, middleware, prompt, name):
    return create_agent(
        model, tools=tools, middleware=[TodoListMiddleware(), *middleware],
        system_prompt=prompt, name=name,
    )
