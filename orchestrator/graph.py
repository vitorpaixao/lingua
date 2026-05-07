"""Single-node LangGraph that forwards user prompts to OpenCode."""

from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage

from opencode_client import OpenCodeClient


class State(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    last_files_changed: List[str]


_client = OpenCodeClient()


async def forward_to_opencode(state: State) -> dict:
    last_message = state["messages"][-1]
    prompt = (
        str(last_message.content)
        if hasattr(last_message, "content")
        else str(last_message)
    )

    try:
        result = await _client.send_prompt(prompt)
        text = OpenCodeClient.extract_text_response(result)
        files = OpenCodeClient.extract_file_changes(result)

        return {
            "messages": [AIMessage(content=text)],
            "last_files_changed": files,
        }

    except Exception as e:
        return {
            "messages": [AIMessage(content=f"Error talking to OpenCode: {e}")],
            "last_files_changed": [],
        }


def create_graph():
    workflow = StateGraph(State)
    workflow.add_node("forward_to_opencode", forward_to_opencode)
    workflow.set_entry_point("forward_to_opencode")
    workflow.add_edge("forward_to_opencode", END)
    return workflow.compile()


graph = create_graph()
