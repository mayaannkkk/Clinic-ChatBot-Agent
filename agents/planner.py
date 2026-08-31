import os
from langchain_core.messages import SystemMessage
from langchain_openai import ChatOpenAI

from prompts.system_prompt import SYSTEM_PROMPT
from tools.appointment_tool import book_appointment
from tools.walkin_tool import check_walkin

# Only TWO tools
TOOLS = [
    book_appointment,
    check_walkin,
]

_MODEL_NAME = os.environ.get("OPENROUTER_MODEL", "openai/gpt-4o-mini")

_llm = ChatOpenAI(
    model=_MODEL_NAME,
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url="https://openrouter.ai/api/v1",
    temperature=0,
)

_llm_with_tools = _llm.bind_tools(TOOLS)


def planner_node(state):
    """The Planner Agent: classify intent and call the appropriate tool."""
    messages = state.get("messages", [])
    full_messages = [SystemMessage(content=SYSTEM_PROMPT)] + messages
    response = _llm_with_tools.invoke(full_messages)
    return {"messages": [response]}