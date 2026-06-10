from pathlib import Path

import pytest

from lingua.conversations import ConversationStore


@pytest.fixture
async def store(tmp_path: Path) -> ConversationStore:
    return ConversationStore(tmp_path / "lingua.db")


async def test_create_and_get(store: ConversationStore):
    c = await store.create("proj1", "First chat")
    assert c["project_id"] == "proj1"
    assert c["title"] == "First chat"
    assert c["status"] == "active"
    assert c["engine_session"] is None
    assert (await store.get(c["id"])) == c


async def test_create_default_title(store: ConversationStore):
    c = await store.create("proj1")
    assert c["title"] == "New conversation"


async def test_list_scoped_to_project_and_excludes_archived(store: ConversationStore):
    a = await store.create("projA", "A1")
    await store.create("projA", "A2")
    await store.create("projB", "B1")
    await store.archive(a["id"])

    active_a = await store.list_for_project("projA")
    assert [c["title"] for c in active_a] == ["A2"]  # archived A1 excluded

    all_a = await store.list_for_project("projA", include_archived=True)
    assert {c["title"] for c in all_a} == {"A1", "A2"}

    b = await store.list_for_project("projB")
    assert [c["title"] for c in b] == ["B1"]


async def test_rename(store: ConversationStore):
    c = await store.create("proj1", "old")
    updated = await store.rename(c["id"], "new title")
    assert updated is not None and updated["title"] == "new title"


async def test_engine_session_roundtrip(store: ConversationStore):
    c = await store.create("proj1")
    await store.set_engine_session(c["id"], "ses_opencode_123")
    assert await store.get_engine_session(c["id"]) == "ses_opencode_123"
    await store.set_engine_session(c["id"], None)
    assert await store.get_engine_session(c["id"]) is None


async def test_events_append_and_ordered_read(store: ConversationStore):
    c = await store.create("proj1")
    cid = c["id"]
    assert await store.get_events(cid) == []

    s1 = await store.append_event(cid, {"type": "agent_step", "tool": "read"})
    s2 = await store.append_event(cid, {"type": "agent_response", "text": "done"})
    assert (s1, s2) == (1, 2)

    events = await store.get_events(cid)
    assert events == [
        {"type": "agent_step", "tool": "read"},
        {"type": "agent_response", "text": "done"},
    ]


async def test_delete_removes_conversation_and_events(store: ConversationStore):
    c = await store.create("proj1")
    cid = c["id"]
    await store.append_event(cid, {"type": "agent_response", "text": "x"})
    await store.delete(cid)
    assert await store.get(cid) is None
    assert await store.get_events(cid) == []


async def test_events_isolated_between_conversations(store: ConversationStore):
    a = await store.create("proj1")
    b = await store.create("proj1")
    await store.append_event(a["id"], {"type": "agent_response", "text": "a"})
    assert await store.get_events(b["id"]) == []
    assert len(await store.get_events(a["id"])) == 1
