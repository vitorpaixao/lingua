"""Contract tests for the shared Step contract (`lingua.engines.steps`).

These assert that BOTH engines' native shapes (OpenCode-style and deepagents-style
names/arg-keys) normalize to the identical canonical UI step — parity by construction.
"""

from lingua.engines.steps import record_file_change, text_step, tool_step


# ---------- parity: same canonical step from both native shapes ----------


def test_read_parity_across_native_shapes():
    opencode = tool_step("read", {"filePath": "src/App.tsx"}, "(loaded)")
    deepagents = tool_step("read_file", {"file_path": "src/App.tsx"}, "whatever")
    assert opencode == deepagents
    assert opencode["tool"] == "read"
    assert opencode["label"] == "Read `src/App.tsx`"
    assert opencode["input"] == {"filePath": "src/App.tsx"}
    assert opencode["output"] == "(file contents loaded)"
    assert opencode["status"] == "completed"


def test_write_and_edit_parity():
    w_oc = tool_step("write", {"filePath": "src/B.tsx", "newString": "x" * 300}, "ok")
    w_da = tool_step("write_file", {"file_path": "src/B.tsx", "content": "x" * 300}, "ok")
    assert w_oc == w_da
    assert w_oc["tool"] == "write"
    assert w_oc["label"] == "Write `src/B.tsx`"
    assert len(w_oc["input"]["newString"]) == 200  # truncated

    e_oc = tool_step("edit", {"filePath": "src/B.tsx", "newString": "y"}, "ok")
    e_da = tool_step("edit_file", {"file_path": "src/B.tsx", "new_string": "y"}, "ok")
    assert e_oc == e_da
    assert e_oc["tool"] == "edit"
    assert e_oc["label"] == "Edit `src/B.tsx`"
    assert e_oc["input"]["newString"] == "y"


def test_bash_parity_and_label_truncation():
    cmd = "npm i react-icons " + "x" * 100
    oc = tool_step("bash", {"command": cmd}, "[exit 0]")
    da = tool_step("run_bash", {"command": cmd}, "[exit 0]")
    shell = tool_step("shell", {"cmd": cmd}, "[exit 0]")
    assert oc == da == shell
    assert oc["tool"] == "bash"
    assert oc["label"] == f"Run `{cmd[:50]}`"
    assert oc["input"] == {"command": cmd}


def test_todowrite_parity():
    todos = [{"content": "step one"}, {"content": "step two"}]
    oc = tool_step("todowrite", {"todos": todos}, "")
    da = tool_step("write_todos", {"todos": todos}, "")
    assert oc == da
    assert oc["tool"] == "todowrite"
    assert "step one" in oc["label"] and "step two" in oc["label"]


def test_unknown_tool_surfaced_generically():
    g = tool_step("glob", {"pattern": "**/*.tsx"}, "out")
    assert g["tool"] == "glob"
    assert g["label"] == "glob"
    assert g["input"] == {"pattern": "**/*.tsx"}
    assert g["status"] == "completed"


def test_failed_status_passes_through_with_error_output():
    f = tool_step("bash", {"command": "rm -rf /"}, "Operation not permitted", "failed")
    assert f["status"] == "failed"
    assert "Operation not permitted" in f["output"]
    # read keeps its real output when not completed
    r = tool_step("read", {"filePath": "x"}, "boom", "failed")
    assert r["output"] == "boom"


def test_output_truncated_to_200():
    s = tool_step("bash", {"command": "x"}, "y" * 500)
    assert len(s["output"]) == 200


# ---------- text step ----------


def test_text_step_shape():
    s = text_step("hello", "prt_1")
    assert s == {
        "tool": "text",
        "label": "Thinking",
        "input": {},
        "output": "hello",
        "status": "streaming",
        "part_id": "prt_1",
    }


# ---------- file-change tracking ----------


def test_record_file_change_only_mutating_and_deduped():
    files: list[str] = []
    record_file_change(tool_step("write", {"filePath": "a.tsx"}, ""), files)
    record_file_change(tool_step("edit", {"filePath": "a.tsx"}, ""), files)  # dedupe
    record_file_change(tool_step("read", {"filePath": "b.tsx"}, ""), files)  # not mutating
    record_file_change(tool_step("edit", {"filePath": "c.tsx"}, ""), files)
    assert files == ["a.tsx", "c.tsx"]


def test_record_file_change_ignores_unknown_path():
    files: list[str] = []
    record_file_change(tool_step("write", {}, ""), files)  # path resolves to "?"
    assert files == []
