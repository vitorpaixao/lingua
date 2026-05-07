"""Lingua - Chainlit frontend hosting the LangGraph orchestrator."""

import chainlit as cl
from langchain_core.messages import HumanMessage
from dotenv import load_dotenv

from graph import graph

load_dotenv()


@cl.set_starters
async def set_starters(user: cl.User | None = None, conversation_id: str | None = None):
    return [
        cl.Starter(
            label="Counter",
            message="Add a counter component with +/- buttons that update the count",
        ),
        cl.Starter(
            label="Gradient background",
            message="Make the page background a smooth gradient from purple to pink",
        ),
        cl.Starter(
            label="To-do list",
            message="Add a simple to-do list with three default items I can check off",
        ),
        cl.Starter(
            label="Card layout",
            message="Replace the content with three cards showing fake product names, descriptions, and prices",
        ),
    ]


@cl.on_chat_start
async def on_chat_start():
    cl.user_session.set("messages", [])

    preview = cl.CustomElement(name="Preview")
    await cl.Message(
        content="Preview is ready. Tell me what to build!",
        elements=[preview],
    ).send()


@cl.on_message
async def on_message(message: cl.Message):
    history = cl.user_session.get("messages") or []
    history.append(HumanMessage(content=message.content))

    async with cl.Step(name="Talking to OpenCode", type="tool") as step:
        step.input = message.content

        try:
            result = await graph.ainvoke(
                {
                    "messages": history,
                    "last_files_changed": [],
                }
            )

            ai_message = result["messages"][-1]
            files = result.get("last_files_changed", [])

            history.append(ai_message)
            cl.user_session.set("messages", history)

            step.output = f"Modified: {', '.join(files) if files else '(no files)'}"

            response_text = ai_message.content
            if files:
                response_text += f"\n\n**Files changed:** `{', '.join(files)}`"
            response_text += "\n\nCheck the preview."

            await cl.Message(content=response_text).send()

        except Exception as e:
            step.output = f"Error: {e}"
            await cl.Message(content=f"Something went wrong: {e}").send()
