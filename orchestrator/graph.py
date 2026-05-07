"""Single-node LangGraph that forwards user prompts to OpenCode."""

import logging
import traceback
import httpx
from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage

from opencode_client import OpenCodeClient

logger = logging.getLogger("lingua")


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

    except httpx.TimeoutException as e:
        logger.error("OpenCode timeout: %s", e)
        return {
            "messages": [
                AIMessage(
                    content="OpenCode timed out. Try again with a simpler request."
                )
            ],
            "last_files_changed": [],
        }
    except httpx.HTTPStatusError as e:
        logger.error(
            "OpenCode HTTP error %s: %s", e.response.status_code, e.response.text[:500]
        )
        return {
            "messages": [
                AIMessage(
                    content=f"OpenCode returned HTTP {e.response.status_code}: "
                    f"{e.response.text[:300]}"
                )
            ],
            "last_files_changed": [],
        }
    except Exception as e:
        logger.error("OpenCode error: %s\n%s", e, traceback.format_exc())
        return {
            "messages": [AIMessage(content=f"Error: {type(e).__name__}: {e}")],
            "last_files_changed": [],
        }


def create_graph():
    workflow = StateGraph(State)
    workflow.add_node("forward_to_opencode", forward_to_opencode)
    workflow.set_entry_point("forward_to_opencode")
    workflow.add_edge("forward_to_opencode", END)
    return workflow.compile()


graph = create_graph()
