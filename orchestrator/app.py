"""Lingua - Chainlit frontend hosting the LangGraph orchestrator."""

import chainlit as cl
from langchain_core.messages import HumanMessage, AIMessage
from dotenv import load_dotenv

from opencode_client import OpenCodeClient, QUESTION_DETECTED

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
    cl.user_session.set("pending_question", False)

    if not cl.user_session.get("repo_setup_done"):
        await _maybe_setup_target_remote()
        cl.user_session.set("repo_setup_done", True)

    await cl.Message(
        content="Tell me what to build! The preview is on the right."
    ).send()


async def _maybe_setup_target_remote():
    """Probe /project remotes. If 'origin' is missing, prompt user for target URL.

    Bootstrap clone is handled by entrypoint.sh based on env vars; this only
    handles the per-session 'origin' (push destination) when not preconfigured.
    """
    try:
        probe = await _client.run_bash(
            "cd /project 2>/dev/null && git remote -v 2>/dev/null || echo NO_GIT"
        )
    except Exception as e:
        await cl.Message(
            content=f"Could not probe `/project` git state: {type(e).__name__}: {e}"
        ).send()
        return

    if "NO_GIT" in probe:
        await cl.Message(
            content="`/project` is not a git repo. Restart the container with `BOOTSTRAP_REPO_URL` set, or work without git."
        ).send()
        return

    if "origin\t" in probe or "origin " in probe:
        return  # already configured

    res = await cl.AskUserMessage(
        content=(
            "No `origin` remote configured. Paste the **target repo URL** "
            "where session changes should be pushed (or leave empty to skip):"
        ),
        timeout=300,
    ).send()
    target_url = ""
    if res:
        target_url = (
            res.get("output", "") if isinstance(res, dict) else getattr(res, "output", "")
        ).strip()

    if not target_url:
        await cl.Message(
            content="Skipping target remote. You can add one later: `git remote add origin <url>`."
        ).send()
        return

    try:
        await _client.run_bash(
            f"cd /project && git remote add origin {target_url}"
        )
        await cl.Message(content=f"`origin` set to `{target_url}`.").send()
    except Exception as e:
        await cl.Message(
            content=f"Failed to set origin: {type(e).__name__}: {e}"
        ).send()


@cl.action_callback("opencode_answer")
async def on_answer(action: cl.Action):
    answer = action.payload.get("value", action.label)
    await action.remove()

    await cl.Message(content=f"**You chose:** {answer}").send()

    await _run_opencode(answer, is_answer=True)


@cl.on_message
async def on_message(message: cl.Message):
    await _run_opencode(message.content)


async def _run_opencode(prompt: str, is_answer: bool = False):
    history = cl.user_session.get("messages") or []
    if not is_answer and prompt not in [
        m.content for m in history if isinstance(m, HumanMessage)
    ]:
        history.append(HumanMessage(content=prompt))
        cl.user_session.set("messages", history)

    parent_step = cl.Step(name="Building...", type="run")
    await parent_step.send()

    thinking_step: cl.Step | None = None
    action_count = 0

    async def on_new_step(step_info):
        nonlocal thinking_step, action_count

        tool = step_info.get("tool", "")
        label = step_info.get("label", "Tool call")
        output = step_info.get("output", "")

        if tool == "text":
            if not thinking_step:
                thinking_step = cl.Step(
                    name="Thinking", type="run", parent_id=parent_step.id
                )
                await thinking_step.send()
            thinking_step.output = output
            await thinking_step.update()
        else:
            action_count += 1
            child = cl.Step(
                name=label, type="tool", parent_id=parent_step.id, show_input=True
            )
            inp = step_info.get("input", {})
            if isinstance(inp, dict):
                if tool in ("edit", "write") and inp.get("newString"):
                    child.input = (
                        f"File: {inp.get('filePath', '?')}\n\n{inp['newString'][:500]}"
                    )
                elif tool == "read":
                    child.input = f"Reading {inp.get('filePath', '?')}"
                elif tool == "todowrite":
                    todos = inp.get("todos", [])
                    items = [t.get("content", "?") for t in todos[:5]]
                    child.input = ", ".join(items)
                else:
                    child.input = str(inp)[:500]
            child.output = output if output else "Done"
            await child.send()

            parent_step.output = (
                f"{action_count} action{'s' if action_count != 1 else ''} completed"
            )
            await parent_step.update()

    try:
        if is_answer:
            result = await _client.continue_after_answer(
                answer=prompt,
                on_new_step=on_new_step,
            )
        else:
            result = await _client.send_prompt_with_polling(
                prompt=prompt,
                on_new_step=on_new_step,
            )

        if QUESTION_DETECTED in result:
            parent_step.name = "Needs input"
            parent_step.output = "Waiting for your answer"
            await parent_step.update()

            question_data = result.get("question", {})
            q = OpenCodeClient.extract_question(question_data)

            question_text = q.get("question", "OpenCode has a question")
            header = q.get("header", "")
            options = q.get("options", [])

            content = f"**{header}**\n\n{question_text}" if header else question_text

            actions = [
                cl.Action(
                    name="opencode_answer",
                    label=opt.get("label", "?"),
                    payload={"value": opt.get("label", "?")},
                )
                for opt in options
            ]

            if not actions:
                actions = [
                    cl.Action(
                        name="opencode_answer",
                        label="Continue",
                        payload={"value": "continue"},
                    )
                ]

            msg = cl.Message(content=content, actions=actions)
            await msg.send()
            cl.user_session.set("pending_question", True)
            return

        text = OpenCodeClient.extract_text_response(result)
        files = OpenCodeClient.extract_file_changes(result)

        parent_step.name = "Done"
        if files:
            parent_step.output = f"Changed: {', '.join(f'`{f}`' for f in files)}"
        else:
            parent_step.output = text[:200] if text else "Done"
        parent_step.auto_collapse = True
        await parent_step.update()

        response = text
        if files:
            response += f"\n\n**Files changed:** `{', '.join(files)}`"

        history.append(AIMessage(content=text))
        cl.user_session.set("messages", history)

        await cl.Message(content=response).send()

    except Exception as e:
        parent_step.name = "Error"
        parent_step.output = f"{type(e).__name__}: {e}"
        parent_step.is_error = True
        await parent_step.update()
        await cl.Message(
            content=f"Something went wrong: {type(e).__name__}: {e}"
        ).send()
