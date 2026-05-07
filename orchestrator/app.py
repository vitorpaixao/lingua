"""Lingua - Chainlit frontend hosting the LangGraph orchestrator."""

import chainlit as cl
from langchain_core.messages import HumanMessage
from dotenv import load_dotenv

from opencode_client import OpenCodeClient

load_dotenv()

_client = OpenCodeClient()


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
    await cl.Message(
        content="Tell me what to build! The preview is on the right."
    ).send()


@cl.on_message
async def on_message(message: cl.Message):
    history = cl.user_session.get("messages") or []
    history.append(HumanMessage(content=message.content))

    shown_step_ids: set = set()
    working_msg = None

    async def on_new_step(step_info):
        nonlocal working_msg
        step_id = step_info.get("id", "")
        if step_id and step_id in shown_step_ids:
            return
        if step_id:
            shown_step_ids.add(step_id)

        tool = step_info.get("tool", "")
        label = step_info.get("label", "Tool call")
        output = step_info.get("output", "")

        if tool == "text":
            if working_msg:
                working_msg.content = output
                await working_msg.update()
            else:
                working_msg = cl.Message(content=output)
                await working_msg.send()
        else:
            async with cl.Step(name=label, type="tool") as step:
                inp = step_info.get("input", {})
                if isinstance(inp, dict):
                    if tool in ("edit", "write") and inp.get("newString"):
                        step.input = f"File: {inp.get('filePath', '?')}\n\n{inp['newString'][:500]}"
                    elif tool == "read":
                        step.input = f"Reading {inp.get('filePath', '?')}"
                    elif tool == "todowrite":
                        todos = inp.get("todos", [])
                        items = [t.get("content", "?") for t in todos[:5]]
                        step.input = ", ".join(items)
                    else:
                        step.input = str(inp)[:500]
                step.output = output if output else "Done"
            working_msg = None

    try:
        result = await _client.send_prompt_with_polling(
            prompt=message.content,
            on_new_step=on_new_step,
        )

        text = OpenCodeClient.extract_text_response(result)
        files = OpenCodeClient.extract_file_changes(result)

        ai_message = cl.Message(content=text)
        if files:
            ai_message.content += f"\n\n**Files changed:** `{', '.join(files)}`"

        history.append(HumanMessage(content=message.content))
        from langchain_core.messages import AIMessage

        history.append(AIMessage(content=text))
        cl.user_session.set("messages", history)

        await ai_message.send()

    except Exception as e:
        await cl.Message(
            content=f"Something went wrong: {type(e).__name__}: {e}"
        ).send()
