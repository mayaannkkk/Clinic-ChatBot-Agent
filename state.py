from typing import TypedDict, Annotated
from langgraph.graph.message import add_messages

class ClinicState(TypedDict):
    messages: Annotated[list, add_messages]

