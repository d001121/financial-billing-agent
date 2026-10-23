"""Official Agent Server SDK connection used by the API adapters."""
from langgraph_sdk import get_client

from backend.config import settings


def sdk():
    return get_client(url=settings.SERVER_URL)
