"""Pure helpers of the server: key grammar, safe messages, root URIs, digests."""

import re
import sqlite3

import pytest
from pydantic import BaseModel, ConfigDict, ValidationError

from xoot.exceptions.integrity_violation_error import IntegrityViolationError
from xoot.exceptions.version_conflict_error import VersionConflictError
from xoot.models.event.actor import Actor
from xoot.models.event.actor_kind import ActorKind
from xoot.models.fields import SQLITE_INT_MAX
from xoot.models.session.client import Client
from xoot.server.clients import session_client
from xoot.server.confirm import args_digest
from xoot.server.errors import not_found_message, safe_message
from xoot.server.keys import DECISION_KEY, ITEM_KEY, SESSION_KEY, parse_key
from xoot.server.roots import file_uri_path
from xoot.server.schemas.client_info_entry import ClientInfoEntry


@pytest.mark.parametrize(
    ("pattern", "text", "expected"),
    [
        (ITEM_KEY, "xoot-12", ("xoot", 12)),
        (ITEM_KEY, "ab-c1-7", ("ab-c1", 7)),
        (DECISION_KEY, "xoot-D3", ("xoot", 3)),
        (SESSION_KEY, "xoot-S4", ("xoot", 4)),
        (ITEM_KEY, "xoot-D3", None),
        (ITEM_KEY, "xoot-012", None),
        (ITEM_KEY, "Xoot-1", None),
        (ITEM_KEY, f"xoot-{SQLITE_INT_MAX + 1}", None),
        (SESSION_KEY, "xoot-s4", None),
    ],
)
def test_key_grammar(
    pattern: re.Pattern[str], text: str, expected: tuple[str, int] | None
) -> None:
    """Prefix is lowercase; D and S are uppercase; numbers fit a stored id."""
    assert parse_key(pattern, text) == expected


def test_not_found_echoes_only_well_formed_keys() -> None:
    """A well-formed key is echoed; arbitrary text is not."""
    assert not_found_message("xoot-5") == "not found: xoot-5"
    assert not_found_message("'; DROP TABLE item") == "not found: malformed key"


class _Probe(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str
    dispositions: dict[str, int] = {}


def test_validation_locations_mask_caller_names() -> None:
    """Unknown field names and dict keys become '*'; known fields stay."""
    with pytest.raises(ValidationError) as caught:
        _Probe.model_validate(
            {"title": 5, "secret_name": 1, "dispositions": {"k": "x"}}
        )
    message = safe_message(caught.value)
    assert "title (string_type)" in message
    assert "* (extra_forbidden)" in message
    assert "dispositions.* (int_parsing)" in message
    assert "secret_name" not in message and "k (" not in message


def test_conflict_message_uses_public_names() -> None:
    """Reference columns appear under their public names."""
    actors = (Actor(kind=ActorKind.USER, client=Client.CLI),)
    exc = VersionConflictError("xoot-3", 4, ("parent_id", "title"), actors)
    assert safe_message(exc) == (
        "VersionConflictError: xoot-3 is at version 4; changed since your "
        "version: parent, title; by: user/cli"
    )


def test_driver_text_is_never_forwarded() -> None:
    """A constraint error keeps only its code name, not the driver's text."""
    error = sqlite3.IntegrityError("CHECK constraint failed: length(title) <= 200")
    error.sqlite_errorname = "SQLITE_CONSTRAINT_CHECK"
    message = safe_message(IntegrityViolationError(error))
    assert message == (
        "IntegrityViolationError: the database could not complete the "
        "operation (SQLITE_CONSTRAINT_CHECK)"
    )


@pytest.mark.parametrize(
    ("uri", "expected"),
    [
        ("file:///x/proj", "/x/proj"),
        ("file://localhost/x/a%20b/", "/x/a b"),
        ("file:///x/proj/../other", "/x/other"),
        ("file://host/x/proj", None),
        ("https://example.com/x", None),
        ("file:relative/path", None),
    ],
)
def test_file_uri_path(uri: str, expected: str | None) -> None:
    """Only local file URIs become paths, normalized like registered paths."""
    assert file_uri_path(uri) == expected


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("claude-code", Client.CODE),
        ("MY-CLAUDE-CODE", Client.CODE),
        ("claude", Client.CHAT),
    ],
)
def test_session_client(name: str, expected: Client) -> None:
    """Only a name containing claude-code, in any case, maps to code."""
    assert session_client(ClientInfoEntry(name=name, version="1")) is expected
    assert session_client(None) is Client.CHAT


def test_digest_is_canonical() -> None:
    """Key order and spacing do not change the digest; values do."""
    first = args_digest({"a": 1, "b": {"y": [1, 2], "x": "é"}})
    assert first == args_digest({"b": {"x": "é", "y": [1, 2]}, "a": 1})
    assert first != args_digest({"a": 2, "b": {"y": [1, 2], "x": "é"}})
