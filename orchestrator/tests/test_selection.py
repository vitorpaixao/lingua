from lingua.selection import (
    format_selection_block,
    format_selections_block,
    prepend_selection,
    prepend_selections,
)


def test_empty_selection_returns_empty_string():
    assert format_selection_block(None) == ""
    assert format_selection_block({}) == ""


def test_only_summary_field_returns_empty():
    # summary is for the chip; not part of the prefix block
    assert format_selection_block({"summary": "Button"}) == ""


def test_full_selection_includes_all_fields_in_order():
    sel = {
        "source": "src/components/Hero.tsx:42:5",
        "component": "Hero",
        "selector": "button.primary",
        "text": "Get started",
        "html": "<button>Get started</button>",
        "summary": "Button",
    }
    block = format_selection_block(sel)
    expected = (
        "[Selected element from preview — edit this in code]\n"
        "source: src/components/Hero.tsx:42:5\n"
        "component: Hero\n"
        "selector: button.primary\n"
        "text: Get started\n"
        "html: <button>Get started</button>"
    )
    assert block == expected


def test_missing_optional_fields_are_omitted():
    sel = {"source": "src/App.tsx:1:1", "summary": "App"}
    block = format_selection_block(sel)
    assert block == (
        "[Selected element from preview — edit this in code]\n"
        "source: src/App.tsx:1:1"
    )


def test_prepend_selection_attaches_block_above_prompt():
    sel = {"source": "src/App.tsx:1:1", "summary": "App"}
    result = prepend_selection("Make it blue", sel)
    assert result == (
        "[Selected element from preview — edit this in code]\n"
        "source: src/App.tsx:1:1\n"
        "\n"
        "Make it blue"
    )


def test_prepend_with_no_selection_returns_prompt_unchanged():
    assert prepend_selection("Make it blue", None) == "Make it blue"
    assert prepend_selection("Make it blue", {}) == "Make it blue"


# ---------- list variant ----------


def test_format_selections_block_none_returns_empty():
    assert format_selections_block(None) == ""


def test_format_selections_block_empty_list_returns_empty():
    assert format_selections_block([]) == ""


def test_format_selections_block_single_item_matches_single_block():
    sel = {"source": "src/A.tsx:1:1", "summary": "A"}
    assert format_selections_block([sel]) == format_selection_block(sel)


def test_format_selections_block_two_items_joins_with_blank_line():
    sels = [
        {"source": "src/A.tsx:1:1", "summary": "A"},
        {"source": "src/B.tsx:2:2", "summary": "B"},
    ]
    block = format_selections_block(sels)
    expected = (
        "[Selected element from preview — edit this in code]\n"
        "source: src/A.tsx:1:1\n"
        "\n"
        "[Selected element from preview — edit this in code]\n"
        "source: src/B.tsx:2:2"
    )
    assert block == expected


def test_format_selections_block_skips_empty_payloads():
    # An item with only "summary" produces an empty block and is dropped
    sels = [
        {"source": "src/A.tsx:1:1", "summary": "A"},
        {"summary": "only-summary"},
    ]
    block = format_selections_block(sels)
    assert block == format_selection_block(sels[0])


def test_prepend_selections_with_no_selections_returns_prompt_unchanged():
    assert prepend_selections("Make it blue", None) == "Make it blue"
    assert prepend_selections("Make it blue", []) == "Make it blue"


def test_prepend_selections_attaches_blocks_above_prompt():
    sels = [
        {"source": "src/A.tsx:1:1", "summary": "A"},
        {"source": "src/B.tsx:2:2", "summary": "B"},
    ]
    result = prepend_selections("Make them blue", sels)
    expected = (
        "[Selected element from preview — edit this in code]\n"
        "source: src/A.tsx:1:1\n"
        "\n"
        "[Selected element from preview — edit this in code]\n"
        "source: src/B.tsx:2:2\n"
        "\n"
        "Make them blue"
    )
    assert result == expected
