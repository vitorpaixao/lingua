"""Smoke test for the LangGraph. Run with: uv run python test_graph.py"""

import asyncio
from langchain_core.messages import HumanMessage
from graph import graph


async def main():
    result = await graph.ainvoke(
        {
            "messages": [
                HumanMessage(content="Change the heading to say 'Hello LangGraph'")
            ],
            "last_files_changed": [],
        }
    )
    print("Response:", result["messages"][-1].content)
    print("Files changed:", result["last_files_changed"])


if __name__ == "__main__":
    asyncio.run(main())
