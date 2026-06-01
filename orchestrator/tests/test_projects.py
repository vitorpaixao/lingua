from pathlib import Path

import pytest

from lingua.projects import ProjectStore


@pytest.fixture
async def store(tmp_path: Path) -> ProjectStore:
    return ProjectStore(tmp_path / "lingua.db")


async def test_list_empty(store: ProjectStore):
    assert await store.list_() == []


async def test_create_and_get(store: ProjectStore):
    p = await store.create("My App", "https://x/b", "https://x/t")
    assert p["name"] == "My App"
    assert p["bootstrap_url"] == "https://x/b"
    assert p["target_url"] == "https://x/t"
    assert p["status"] == "active"
    assert p["last_opened_at"] is None
    assert p["created_at"] is not None
    assert (await store.get(p["id"])) == p


async def test_create_without_target(store: ProjectStore):
    p = await store.create("App2", "https://x/b")
    assert p["target_url"] is None


async def test_list_excludes_archived(store: ProjectStore):
    p1 = await store.create("A", "https://x/b")
    await store.create("B", "https://x/b")
    await store.archive(p1["id"])
    active = await store.list_()
    assert len(active) == 1
    assert active[0]["name"] == "B"


async def test_list_include_archived(store: ProjectStore):
    p1 = await store.create("A", "https://x/b")
    await store.create("B", "https://x/b")
    await store.archive(p1["id"])
    all_ = await store.list_(include_archived=True)
    assert len(all_) == 2


async def test_update_changes_allowed_fields(store: ProjectStore):
    p = await store.create("Name1", "https://x/b")
    updated = await store.update(p["id"], name="Name2", target_url="https://x/new")
    assert updated["name"] == "Name2"
    assert updated["target_url"] == "https://x/new"


async def test_update_ignores_disallowed_fields(store: ProjectStore):
    p = await store.create("App", "https://x/b")
    updated = await store.update(p["id"], id="hacker", created_at="2000-01-01")
    # id + created_at unchanged
    assert updated["id"] == p["id"]
    assert updated["created_at"] == p["created_at"]


async def test_touch_updates_last_opened_at(store: ProjectStore):
    p = await store.create("App", "https://x/b")
    assert p["last_opened_at"] is None
    touched = await store.touch(p["id"])
    assert touched["last_opened_at"] is not None


async def test_archive_sets_status(store: ProjectStore):
    p = await store.create("App", "https://x/b")
    archived = await store.archive(p["id"])
    assert archived["status"] == "archived"


async def test_get_missing_returns_none(store: ProjectStore):
    assert await store.get("no-such-id") is None
