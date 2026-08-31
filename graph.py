from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode, tools_condition

from agents.planner import TOOLS, planner_node
from state import ClinicState

builder = StateGraph(ClinicState)

builder.add_node("assistant", planner_node)
builder.add_node("tools", ToolNode(TOOLS))

builder.set_entry_point("assistant")

builder.add_conditional_edges(
    "assistant",
    tools_condition,
    {
        "tools": "tools",
        END: END,
    }
)

builder.add_edge("tools", "assistant")

graph = builder.compile()