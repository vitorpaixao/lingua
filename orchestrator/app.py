"""Lingua - Chainlit frontend hosting the LangGraph orchestrator."""

import asyncio
import datetime
import os
import shlex
from pathlib import Path

import chainlit as cl
from chainlit.server import app as fastapi_app
from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from langchain_core.messages import HumanMessage, AIMessage
from dotenv import load_dotenv

from opencode_client import OpenCodeClient, QUESTION_DETECTED
import projects

load_dotenv()

_client = OpenCodeClient()

PROJECT_DIR = Path(os.getenv("PROJECT_DIR", "/project"))


async def _git(cmd: str) -> tuple[int, str, str]:
    """Run a git command in PROJECT_DIR. Returns (code, stdout, stderr)."""
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    proc = await asyncio.create_subprocess_exec(
        "bash", "-c", cmd,
        cwd=str(PROJECT_DIR),
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, err = await proc.communicate()
    return proc.returncode or 0, out.decode().strip(), err.decode().strip()


async def git_status():
    """GET /api/git/status — dispatched by _lingua_git_middleware."""
    code, branch, _ = await _git("git rev-parse --abbrev-ref HEAD 2>/dev/null || echo none")
    if code != 0 or branch == "none" or not branch:
        return {"ok": False, "reason": "no-git"}

    _, ahead, _ = await _git("git rev-list --count @{u}..HEAD 2>/dev/null || echo no-upstream")
    _, dirty, _ = await _git("git status --porcelain | wc -l")

    return {
        "ok": True,
        "branch": branch,
        "ahead": ahead if ahead.isdigit() else None,
        "no_upstream": ahead == "no-upstream",
        "dirty_files": int(dirty) if dirty.isdigit() else 0,
        "on_main": branch in ("main", "master"),
    }


async def git_publish():
    """POST /api/git/publish — stage all + commit + push. Auto-branches off main/master.
    Dispatched by _lingua_git_middleware."""
    timestamp_human = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    timestamp_slug = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    msg = f"Update from Lingua {timestamp_human}"

    code, branch, err = await _git("git rev-parse --abbrev-ref HEAD")
    if code != 0 or not branch:
        return {"ok": False, "step": "branch", "error": err or "could not read branch"}

    if branch in ("main", "master"):
        new_branch = f"lingua/{timestamp_slug}"
        bcode, _, berr = await _git(f"git checkout -b {shlex.quote(new_branch)}")
        if bcode != 0:
            return {"ok": False, "step": "branch", "error": berr}
        branch = new_branch

    await _git("git add -A")
    name = os.getenv("GIT_USER_NAME", "Lingua")
    email = os.getenv("GIT_USER_EMAIL", "lingua@local")
    ccode, _, cerr = await _git(
        f"git -c user.name={shlex.quote(name)} -c user.email={shlex.quote(email)}"
        f" commit -m {shlex.quote(msg)}"
    )
    if ccode != 0 and "nothing to commit" not in cerr:
        return {"ok": False, "step": "commit", "error": cerr}

    token = os.getenv("GITHUB_TOKEN", "")
    if token:
        helper = f"!f() {{ echo username=oauth2; echo password={token}; }}; f"
        push_cmd = f"git -c credential.helper={shlex.quote(helper)} push -u origin {shlex.quote(branch)}"
    else:
        push_cmd = f"git push -u origin {shlex.quote(branch)}"
    pcode, push_out, push_err = await _git(push_cmd)
    if pcode != 0:
        return {"ok": False, "step": "push", "branch": branch, "error": push_err}

    return {"ok": True, "branch": branch, "message": msg, "output": push_out}


@fastapi_app.middleware("http")
async def _strip_frame_headers(request: Request, call_next):
    response = await call_next(request)
    if "x-frame-options" in response.headers:
        del response.headers["x-frame-options"]
    response.headers["content-security-policy"] = "frame-ancestors *"
    return response


@fastapi_app.middleware("http")
async def _lingua_git_middleware(request: Request, call_next):
    """Intercept /api/git/* and /api/projects/* before Chainlit's catch-all SPA route.
    Route reordering proved unreliable; middleware is guaranteed to run first.
    """
    path = request.url.path
    method = request.method

    if path == "/api/git/status" and method == "GET":
        return JSONResponse(await git_status())
    if path == "/api/git/publish" and method == "POST":
        return JSONResponse(await git_publish())

    if path == "/api/projects":
        if method == "GET":
            return JSONResponse(await projects.list_projects())
        if method == "POST":
            body = await request.json()
            return JSONResponse(await projects.create_project(**body))
    if path.startswith("/api/projects/"):
        pid = path.split("/")[-1]
        if method == "GET":
            result = await projects.get_project(pid)
            return JSONResponse(result if result is not None else {}, status_code=200 if result else 404)
        if method == "PATCH":
            body = await request.json()
            result = await projects.update_project(pid, **body)
            return JSONResponse(result if result is not None else {})
        if method == "DELETE":
            result = await projects.archive_project(pid)
            return JSONResponse(result if result is not None else {})

    return await call_next(request)


# Registered last = outermost in Starlette's stack — CORS headers appear on ALL responses
# including those short-circuited by _lingua_git_middleware above.
fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


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
