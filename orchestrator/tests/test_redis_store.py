import asyncio

import pytest
from fakeredis.aioredis import FakeRedis

from lingua.redis_store import RedisStore


@pytest.fixture
async def store():
    redis = FakeRedis(decode_responses=True)
    yield RedisStore(redis)
    await redis.flushall()
    await redis.aclose()


async def _drain(gen, want: int, timeout: float = 2.0) -> list[tuple[str, dict]]:
    """Consume `want` non-heartbeat events from an async generator."""
    out: list[tuple[str, dict]] = []

    async def consume():
        async for entry_id, event in gen:
            if not entry_id:
                continue  # heartbeat tick
            out.append((entry_id, event))
            if len(out) >= want:
                return

    await asyncio.wait_for(consume(), timeout=timeout)
    return out


# ---------- events stream ----------


async def test_add_event_returns_id_and_persists(store: RedisStore):
    entry_id = await store.add_event("s1", {"type": "agent_step", "tool": "read"})
    assert isinstance(entry_id, str)
    assert "-" in entry_id  # XADD ids are like "1717248000000-0"


async def test_read_events_replays_from_beginning(store: RedisStore):
    await store.add_event("s1", {"type": "agent_step", "n": 1})
    await store.add_event("s1", {"type": "agent_step", "n": 2})
    await store.add_event("s1", {"type": "agent_response", "n": 3})

    gen = store.read_events("s1", since="0", block_ms=100)
    events = await _drain(gen, want=3)
    assert [e["n"] for _, e in events] == [1, 2, 3]


async def test_read_events_since_id_skips_earlier(store: RedisStore):
    id1 = await store.add_event("s1", {"n": 1})
    await store.add_event("s1", {"n": 2})
    await store.add_event("s1", {"n": 3})

    gen = store.read_events("s1", since=id1, block_ms=100)
    events = await _drain(gen, want=2)
    assert [e["n"] for _, e in events] == [2, 3]


async def test_truncate_events_wipes_stream(store: RedisStore):
    await store.add_event("s1", {"n": 1})
    await store.truncate_events("s1")

    gen = store.read_events("s1", since="0", block_ms=100)
    # Should yield only heartbeats; collect one heartbeat tick then stop
    consumed_heartbeat = False
    async for entry_id, _ in gen:
        if not entry_id:
            consumed_heartbeat = True
            break
    assert consumed_heartbeat


# ---------- OpenCode session mapping ----------


async def test_opencode_session_set_and_get(store: RedisStore):
    assert await store.get_opencode_session("s1") is None
    await store.set_opencode_session("s1", "sess_abc")
    assert await store.get_opencode_session("s1") == "sess_abc"


async def test_clear_opencode_session(store: RedisStore):
    await store.set_opencode_session("s1", "sess_abc")
    await store.clear_opencode_session("s1")
    assert await store.get_opencode_session("s1") is None


# ---------- pending question flag ----------


async def test_pending_question_flag(store: RedisStore):
    assert not await store.has_pending_question("s1")
    await store.set_pending_question("s1")
    assert await store.has_pending_question("s1")
    await store.clear_pending_question("s1")
    assert not await store.has_pending_question("s1")


# ---------- history ----------


async def test_append_and_get_history_preserves_order(store: RedisStore):
    await store.append_history("s1", {"role": "user", "content": "hi"})
    await store.append_history("s1", {"role": "assistant", "content": "hello"})
    history = await store.get_history("s1")
    assert history == [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
    ]


async def test_clear_history(store: RedisStore):
    await store.append_history("s1", {"role": "user", "content": "hi"})
    await store.clear_history("s1")
    assert await store.get_history("s1") == []


# ---------- active workspace ----------


async def test_active_workspace_set_and_get(store: RedisStore):
    assert await store.get_active_workspace() is None
    await store.set_active_workspace("proj-1")
    assert await store.get_active_workspace() == "proj-1"


# ---------- combined truncate ----------


async def test_truncate_session_wipes_all_per_session_keys(store: RedisStore):
    sid = "s1"
    await store.add_event(sid, {"n": 1})
    await store.set_opencode_session(sid, "sess_abc")
    await store.set_pending_question(sid)
    await store.append_history(sid, {"role": "user"})

    await store.truncate_session(sid)

    assert await store.get_opencode_session(sid) is None
    assert not await store.has_pending_question(sid)
    assert await store.get_history(sid) == []
