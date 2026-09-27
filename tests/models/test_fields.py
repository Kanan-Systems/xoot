"""Input limits are enforced by the shared field types and the models."""

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import TypeAdapter, ValidationError

from xoot.models.fields import (
    AbsolutePath,
    Body,
    Id,
    KeyPrefix,
    Slug,
    StateName,
    Timestamp,
    Title,
    format_timestamp,
)
from xoot.models.item.item_create import ItemCreate
from xoot.models.item.item_draft import ItemDraft
from xoot.models.item.item_kind import ItemKind
from xoot.models.session.session_close import SessionClose
from xoot.models.session.session_start import SessionStart


def _accepts(field: object, value: object) -> bool:
    try:
        TypeAdapter(field).validate_python(value)
    except ValidationError:
        return False
    return True


@pytest.mark.parametrize(
    ("value", "ok"),
    [
        ("", False),
        ("a", True),
        ("a" * 200, True),
        ("a" * 201, False),
        ("a\x00b", False),
    ],
)
def test_title_limits(value: str, ok: bool) -> None:
    """Titles are 1-200 characters without NUL."""
    assert _accepts(Title, value) is ok


@pytest.mark.parametrize(
    ("value", "ok"),
    [("", True), ("b" * 32768, True), ("b" * 32769, False), ("\x00", False)],
)
def test_body_limits(value: str, ok: bool) -> None:
    """Bodies are up to 32768 characters without NUL."""
    assert _accepts(Body, value) is ok


def test_limits_count_characters_not_bytes() -> None:
    """A 200-character title of multi-byte characters is still allowed."""
    assert _accepts(Title, "é" * 200)
    assert not _accepts(Title, "é" * 201)


@pytest.mark.parametrize(
    ("value", "ok"),
    [
        ("xo", True),
        ("kroot-2", True),
        ("ab-12", True),
        ("a" * 32, True),
        ("a", False),
        ("a" * 33, False),
        ("1abc", False),
        ("Abc", False),
        ("a_b", False),
        ("ab\n", False),
        ("ab\x00", False),
    ],
)
def test_slug_limits(value: str, ok: bool) -> None:
    """Aliases match ^[a-z][a-z0-9-]{1,31}$ exactly."""
    assert _accepts(Slug, value) is ok


@pytest.mark.parametrize(
    ("value", "ok"),
    [
        ("xo", True),
        ("kroot2", True),
        ("a" * 32, True),
        ("ab-12", False),
        ("ab-", False),
        ("a", False),
        ("a" * 33, False),
        ("1abc", False),
        ("Abc", False),
        ("a_b", False),
        ("ab\n", False),
    ],
)
def test_key_prefix_limits(value: str, ok: bool) -> None:
    """Key prefixes match ^[a-z][a-z0-9]{1,31}$ exactly: no dash."""
    assert _accepts(KeyPrefix, value) is ok


@pytest.mark.parametrize(
    ("value", "ok"),
    [
        ("open", True),
        ("in-review", True),
        ("wait_2", True),
        ("", False),
        ("Open", False),
    ],
)
def test_state_name_limits(value: str, ok: bool) -> None:
    """State names are lowercase identifiers."""
    assert _accepts(StateName, value) is ok


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("/a/b", "/a/b"),
        ("/a//b/./c/../d/", "/a/b/d"),
        ("//a", "/a"),
        ("/", "/"),
        ("/..", "/"),
    ],
)
def test_paths_are_normalized(value: str, expected: str) -> None:
    """Paths are normalized lexically so one directory has one spelling."""
    assert TypeAdapter(AbsolutePath).validate_python(value) == expected


@pytest.mark.parametrize("value", ["relative/path", "", "/a\x00b", "/" + "a" * 4096])
def test_bad_paths_are_rejected(value: str) -> None:
    """Relative, empty, NUL-containing and over-long paths are rejected."""
    assert not _accepts(AbsolutePath, value)


@pytest.mark.parametrize(("value", "ok"), [(1, True), (0, False), (2**63, False)])
def test_ids_fit_sqlite(value: int, ok: bool) -> None:
    """Ids are positive and fit a SQLite INTEGER."""
    assert _accepts(Id, value) is ok


def test_timestamps_must_be_aware_and_are_stored_in_utc() -> None:
    """Naive datetimes are rejected; aware ones are converted to UTC."""
    assert not _accepts(Timestamp, datetime(2026, 9, 26, 12, 0))
    plus_two = timezone(timedelta(hours=2))
    value = TypeAdapter(Timestamp).validate_python(
        datetime(2026, 9, 26, 12, 0, tzinfo=plus_two)
    )
    assert format_timestamp(value) == "2026-09-26T10:00:00.000000Z"


def test_input_models_apply_the_limits() -> None:
    """The service inputs reject over-limit values before any write."""
    with pytest.raises(ValidationError):
        ItemCreate(kind=ItemKind.GOAL, title="t" * 201)
    with pytest.raises(ValidationError):
        ItemDraft(title="ok", body="\x00")
    with pytest.raises(ValidationError):
        SessionStart(title="")
    with pytest.raises(ValidationError):
        SessionClose(summary="s" * 32769)


def test_input_models_forbid_unknown_fields() -> None:
    """Unexpected fields are an error, not silently dropped."""
    with pytest.raises(ValidationError):
        ItemDraft.model_validate({"title": "t", "state": "done"})
