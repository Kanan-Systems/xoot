"""
Spotting encoding damage: a "?" directly between two letters of any script
in a title or body is flagged, by op number, key or ref and field only. The
check never refuses a block and never changes the result digest.
"""

from collections.abc import Callable
from typing import Any

import pytest

from xoot.services.paste.encoding_check import (
    NO_TARGET,
    encoding_warnings,
    looks_damaged,
)
from xoot.services.paste.executor import dry_run, result_digest
from xoot.services.paste.models.paste_encoding_warning import PasteEncodingWarning
from xoot.services.paste.parser import parse_paste
from xoot.store.store import Store

START = {"op": "session_start", "title": "s"}

type Fenced = Callable[..., str]


@pytest.mark.parametrize("text", ["verificaci?n", "a?b", "?andu a?b", "ñ?ñ", "ж?ж"])
def test_question_mark_between_letters_warns(text: str) -> None:
    """Any script counts as a letter on both sides."""
    assert looks_damaged(text)


@pytest.mark.parametrize(
    "text", ["Why?", "? leading", "x ? y", "?andu", "a?1", "1?a", "?", "", "a?"]
)
def test_other_question_marks_do_not_warn(text: str) -> None:
    """A "?" at an edge, beside a space or beside a digit is ordinary text."""
    assert not looks_damaged(text)


def test_every_title_and_body_is_scanned(fenced: Fenced) -> None:
    """Creates, captures, updates and decisions: each field is named once."""
    ops: list[dict[str, Any]] = [
        {"op": "session_start", "title": "Paste LV ?a?b"},
        {"op": "item_create", "ref": "g", "kind": "goal", "title": "verificaci?n"},
        {"op": "capture", "title": "fine", "body": "codificaci?n"},
        {"op": "capture", "title": "a?b"},
        {"op": "item_update", "key": "$g", "changes": {"title": "x?y", "body": "y?z"}},
        {"op": "item_update", "key": "xoot-9", "expected_version": 1,
         "changes": {"state": "active"}},
        {"op": "decision_record", "ref": "d", "title": "Why?", "body": "a?b",
         "status": "locked"},
        {"op": "decision_update", "key": "xoot-D4", "expected_version": 2,
         "changes": {"title": "ñ?ú"}},
    ]  # fmt: skip
    warnings = encoding_warnings(parse_paste(fenced(ops)))
    assert [(w.index, w.target, w.field) for w in warnings] == [
        (1, NO_TARGET, "title"),
        (2, "$g", "title"),
        (3, NO_TARGET, "body"),
        (4, NO_TARGET, "title"),
        (5, "$g", "title"),
        (5, "$g", "body"),
        (7, "$d", "body"),
        (8, "xoot-D4", "title"),
    ]


def test_clean_block_has_no_warnings(fenced: Fenced) -> None:
    """Accents that survived, and ordinary question marks, raise nothing."""
    ops = [START, {"op": "capture", "title": "Revisar codificación?"}]
    assert not encoding_warnings(parse_paste(fenced(ops)))


@pytest.mark.usefixtures("project")
def test_warnings_do_not_change_the_digest(store: Store, fenced: Fenced) -> None:
    """The digest the apply compares is the same with or without warnings."""
    result = dry_run(store, parse_paste(fenced([START])))
    warned = result.model_copy(
        update={"warnings": (PasteEncodingWarning(index=1, target="-", field="title"),)}
    )
    assert result_digest(warned) == result_digest(result)
