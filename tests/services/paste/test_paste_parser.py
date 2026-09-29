"""
Parsing a paste: exactly one fenced block with info string "xoot", decoded
as UTF-8 within 256 KiB, parsed only by Pydantic's depth-limited JSON parser
into strict, extra="forbid" models. Errors name ops, fields and error types,
never the input.
"""

import json
from typing import Any

import pytest

from xoot.exceptions.paste_error import PasteError
from xoot.exceptions.paste_op_error import PasteOpError
from xoot.services.paste.models.item_update_op import ItemUpdateOp
from xoot.services.paste.parser import (
    MANY_BLOCKS,
    MAX_BYTES,
    NO_BLOCK,
    UNCLOSED,
    decode_paste,
    extract_block,
    parse_paste,
)

MARKER = "paste-secret-51c2"
START = {"op": "item_create", "kind": "goal", "title": "g"}
CAPTURE = {"op": "capture", "found_on": "goal-1", "title": "c", "body": "why"}


def _json(ops: list[dict[str, Any]], **top: Any) -> str:
    return json.dumps({"xoot": 2, "project": "xoot", **top, "ops": ops})


def _fence(body: str, info: str = "xoot") -> str:
    return f"```{info}\n{body}\n```"


def test_no_block_is_refused() -> None:
    """Prose alone holds no block."""
    with pytest.raises(PasteError, match=f"^{NO_BLOCK}$"):
        parse_paste("I think we should create a goal for this.")


def test_two_blocks_are_refused() -> None:
    """Two xoot blocks are ambiguous; the user must send one."""
    body = _json([START])
    with pytest.raises(PasteError, match=f"^{MANY_BLOCKS}$"):
        parse_paste(f"{_fence(body)}\nand also\n{_fence(body)}")


def test_block_inside_prose_is_found() -> None:
    """Text before and after the block, and other fenced blocks, are ignored."""
    text = (
        "Here is the plan.\n\n```python\nprint('x')\n```\n\n"
        f"{_fence(_json([START, CAPTURE]))}\n\nLet me know."
    )
    block = parse_paste(text)
    assert [op.op for op in block.ops] == ["item_create", "capture"]


def test_crlf_line_endings_are_accepted() -> None:
    """A Windows clipboard ends lines with CRLF."""
    text = _fence(_json([START])).replace("\n", "\r\n")
    assert parse_paste(text).ops[0].op == "item_create"


def test_receipt_block_alone_is_not_a_block() -> None:
    """A receipt's info string is xoot-receipt, not xoot."""
    with pytest.raises(PasteError, match=f"^{NO_BLOCK}$"):
        parse_paste(_fence(_json([START]), info="xoot-receipt"))


def test_receipt_next_to_a_block_is_ignored() -> None:
    """Only the xoot block counts; a pasted-back receipt beside it does not."""
    text = f"{_fence('{}', info='xoot-receipt')}\n{_fence(_json([START]))}"
    assert parse_paste(text).ops[0].op == "item_create"


def test_example_nested_in_a_longer_fence_is_content() -> None:
    """The brief's own example sits inside a four-backtick fence."""
    text = f"````text\n{_fence(_json([START]))}\n````"
    with pytest.raises(PasteError, match=f"^{NO_BLOCK}$"):
        parse_paste(text)


def test_unclosed_block_is_refused() -> None:
    """A block cut off by a partial copy is refused, not guessed at."""
    with pytest.raises(PasteError, match=f"^{UNCLOSED}$"):
        extract_block(f"```xoot\n{_json([START])}\n")


def test_info_string_must_be_exactly_xoot() -> None:
    """```xoot2 and ```xoot json are other blocks."""
    for info in ("xoot2", "xoot json", "XOOT"):
        with pytest.raises(PasteError, match=f"^{NO_BLOCK}$"):
            parse_paste(_fence(_json([START]), info=info))


def test_over_the_cap_is_refused() -> None:
    """One byte past 256 KiB is refused; exactly 256 KiB is decoded."""
    assert len(decode_paste(b"a" * MAX_BYTES)) == MAX_BYTES
    with pytest.raises(PasteError, match="larger than 256 KiB"):
        decode_paste(b"a" * (MAX_BYTES + 1))


def test_non_utf8_is_refused() -> None:
    """Latin-1 bytes are not guessed at."""
    with pytest.raises(PasteError, match="^the paste is not valid UTF-8$"):
        decode_paste("café".encode("latin-1"))


def test_byte_order_mark_is_dropped() -> None:
    """A UTF-8 BOM some Windows tools add is not part of the text."""
    assert decode_paste(b"\xef\xbb\xbfhi") == "hi"


def test_nesting_beyond_the_depth_limit_is_refused() -> None:
    """The JSON parser's recursion limit refuses deep nesting before validation."""
    deep = "[" * 1000 + "]" * 1000
    text = _fence(
        '{"xoot": 2, "project": "xoot", "ops": '
        f'[{{"op": "capture", "found_on": "goal-1", "title": "t", "body": {deep}}}]}}'
    )
    with pytest.raises(PasteError, match="not valid JSON \\(json_invalid\\)"):
        parse_paste(text)


def test_101_ops_are_refused() -> None:
    """At most 100 ops."""
    with pytest.raises(PasteError, match="block: ops \\(too_long\\)"):
        parse_paste(_fence(_json([START] + [CAPTURE] * 100)))
    assert len(parse_paste(_fence(_json([START] + [CAPTURE] * 99))).ops) == 100


def test_unknown_op_is_refused_without_echo() -> None:
    """The unknown tag is input, so it is not repeated."""
    with pytest.raises(PasteError) as caught:
        parse_paste(_fence(_json([START, {"op": MARKER}])))
    assert "op 2: * (union_tag_invalid)" in str(caught.value)
    assert MARKER not in str(caught.value)


def test_extra_field_is_refused_without_echo() -> None:
    """An unknown field name is input, so it is masked."""
    with pytest.raises(PasteError) as caught:
        parse_paste(_fence(_json([START, {**CAPTURE, MARKER: 1}])))
    assert "op 2 (capture): * (extra_forbidden)" in str(caught.value)
    assert MARKER not in str(caught.value)


def test_extra_top_level_field_is_refused() -> None:
    """The top level is extra="forbid" too."""
    with pytest.raises(PasteError, match=r"block: \* \(extra_forbidden\)"):
        parse_paste(_fence(_json([START], actor="user")))


@pytest.mark.parametrize("version", [1, 3, True, 2.0, "2"])
def test_protocol_version_must_be_the_integer_2(version: Any) -> None:
    """Strict: not the 0.2 protocol 1, not true, not 2.0, not "2"."""
    body = json.dumps({"xoot": version, "project": "xoot", "ops": [START]})
    with pytest.raises(PasteError, match="invalid xoot block: block: xoot"):
        parse_paste(_fence(body))


@pytest.mark.parametrize("version", ["3", 3.0, True])
def test_expected_version_is_strict(version: Any) -> None:
    """A version must be a real integer, as in the MCP tools."""
    op = {"op": "item_update", "key": "goal-1", "expected_version": version}
    op["changes"] = {"state": "active"}
    with pytest.raises(PasteError, match=r"op 2 \(item_update\): expected_version"):
        parse_paste(_fence(_json([START, op])))


def test_title_errors_do_not_echo_the_title() -> None:
    """A too-long title is named by field and type, never quoted."""
    with pytest.raises(PasteError) as caught:
        parse_paste(_fence(_json([START, {**CAPTURE, "title": MARKER * 20}])))
    assert "op 2 (capture): title (string_too_long)" in str(caught.value)
    assert MARKER not in str(caught.value)


def test_item_update_uses_the_mcp_changes_model() -> None:
    """changes is the item_update tool's own model, extra="forbid" included."""
    op = {"op": "item_update", "key": "goal-1", "expected_version": 1}
    block = parse_paste(_fence(_json([START, {**op, "changes": {"state": "done"}}])))
    assert isinstance(block.ops[1], ItemUpdateOp)
    with pytest.raises(PasteError, match=r"changes\.\* \(extra_forbidden\)"):
        parse_paste(_fence(_json([START, {**op, "changes": {MARKER: "x"}}])))


def test_a_session_field_is_refused() -> None:
    """Blocks carry no session: the field is unknown now."""
    with pytest.raises(PasteError, match=r"block: \* \(extra_forbidden\)"):
        parse_paste(_fence(_json([START], session="anything")))


@pytest.mark.parametrize(
    ("op", "field"),
    [
        ({"op": "item_update", "key": MARKER, "expected_version": 1}, "key"),
        ({"op": "capture", "found_on": "xoot-1", "title": "t"}, "found_on"),
        ({"op": "backlog_push", "key": "goal-1/decision-1"}, "key"),
        ({"op": "backlog_cover", "key": "backlog-1", "batch": "goal-1/"}, "batch"),
        (
            {"op": "decision_update", "key": "goal-1", "expected_version": 1},
            "key",
        ),
    ],
)
def test_keys_off_the_grammar_are_refused_without_echo(
    op: dict[str, Any], field: str
) -> None:
    """Every key field is checked against the grammar when the block is parsed."""
    body = {**op, "changes": {}} if "expected_version" in op else op
    with pytest.raises(PasteError) as caught:
        parse_paste(_fence(_json([body])))
    message = str(caught.value)
    assert f"{field} (" in message
    assert MARKER not in message and "xoot-1" not in message


def test_keys_inside_changes_are_checked_too() -> None:
    """The parent and awaited decision of an item_update fit the grammar."""
    op = {
        "op": "item_update",
        "key": "goal-1/batch-1",
        "expected_version": 1,
        "changes": {"parent": MARKER},
    }
    with pytest.raises(PasteOpError, match=r"^op 1 \(item_update\): not an item key"):
        parse_paste(_fence(_json([op])))


def test_qualified_keys_and_refs_are_accepted() -> None:
    """<prefix>:<key> and $refs both parse."""
    ops = [
        {**START, "ref": "g"},
        {"op": "capture", "found_on": "$g", "title": "t"},
        {"op": "backlog_push", "key": "xoot:goal-1/backlog-1"},
    ]
    assert len(parse_paste(_fence(_json(ops))).ops) == 3


def test_decision_record_cannot_start_superseded() -> None:
    """Only locked or deferred, as in the decision_record tool."""
    op = {
        "op": "decision_record",
        "owner": "goal-1",
        "title": "d",
        "body": "",
        "status": "superseded",
    }
    with pytest.raises(
        PasteError, match=r"op 2 \(decision_record\): status \(literal_error\)"
    ):
        parse_paste(_fence(_json([START, op])))
