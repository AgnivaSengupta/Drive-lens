from __future__ import annotations

import operator
from datetime import date
from typing import Annotated, Any, List, Optional, TypedDict

from dotenv import load_dotenv

from langchain_core.messages import SystemMessage
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from backend.agent.llm import create_chat_model
from backend.agent.tools import drive_search_tool
from backend.agent.prompts import SYSTEM_PROMPT


load_dotenv()

# State def
class AgentState(TypedDict):
    messages: Annotated[List, operator.add]
    retry_count: int
    long_term_context: Optional[str]

tools = [drive_search_tool]
tool_node = ToolNode(tools)

llm = create_chat_model()
llm_with_tools = llm.bind_tools(tools)

# edge
async def call_llm(state: AgentState):
    context = state.get('long_term_context') or ""
    system_content = SYSTEM_PROMPT.format(today=date.today())
    if context:
        system_content += f"\n\n{context}"
        
    system = SystemMessage(content=system_content)
    response = await llm_with_tools.ainvoke([system] + state["messages"])
    return {"messages": [response]}

def should_continue(state: AgentState):
    last = state["messages"][-1]
    if hasattr(last, "tool_calls") and last.tool_calls:
        return "tools"
    return END

def build_agent(checkpointer: Any):
    graph = StateGraph(AgentState)
    graph.add_node("llm", call_llm)
    graph.add_node("tools", tool_node)
    graph.set_entry_point("llm")
    graph.add_conditional_edges("llm", should_continue, {"tools": "tools", END: END})
    graph.add_edge("tools", "llm")
    return graph.compile(checkpointer=checkpointer)
