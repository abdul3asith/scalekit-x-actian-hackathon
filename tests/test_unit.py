"""Pure unit tests -- no external services required."""

import json

from app.auth.identity import normalize_phone
from app.llm import tools
from app.llm.loop import _chunk_text, _sse_chunk


def test_normalize_phone_keeps_plus_and_digits():
    assert normalize_phone("+1 (415) 555-0123") == "+14155550123"
    assert normalize_phone("415-555-0123") == "4155550123"
    assert normalize_phone("  +44 20 7946 0958 ") == "+442079460958"
    assert normalize_phone("") == ""


def test_chunk_text_roundtrips():
    assert _chunk_text("") == [""]
    assert "".join(_chunk_text("book me a shift")) == "book me a shift"
    assert _chunk_text("a b c") == ["a", " b", " c"]


def test_sse_chunk_is_valid_openai_event():
    raw = _sse_chunk("chatcmpl-x", 123, {"content": "hi"}, None)
    assert raw.startswith("data: ") and raw.endswith("\n\n")
    payload = json.loads(raw[len("data: ") :])
    assert payload["object"] == "chat.completion.chunk"
    assert payload["choices"][0]["delta"] == {"content": "hi"}
    assert payload["choices"][0]["finish_reason"] is None


def test_tool_schemas_well_formed():
    names = set()
    for t in tools.TOOL_SCHEMAS:
        assert t["type"] == "function"
        fn = t["function"]
        assert fn["name"] and "parameters" in fn
        names.add(fn["name"])
    # The schemas advertised to the model match what dispatch can execute.
    assert {
        "get_my_schedule",
        "check_availability",
        "set_shift",
        "adjust_shift",
        "cancel_shift",
        "remember",
        "recall",
    } <= names


async def test_dispatch_unknown_tool_is_graceful():
    result = await tools.dispatch("does_not_exist", {}, None, "staff-1")
    assert result["ok"] is False
    assert result["error"] == "unknown_tool"
