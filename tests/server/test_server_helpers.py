"""Pure helpers of the server: safe messages, root URIs, client mapping, digests."""

import sqlite3

import pytest
from pydantic import BaseModel, ConfigDict, ValidationError

from xoot.exceptions.integrity_violation_error import IntegrityViolationError
from xoot.exceptions.version_conflict_error import VersionConflictError
from xoot.models.event.actor import Actor
from xoot.models.event.actor_kind import ActorKind
from xoot.models.event.client import Client
from xoot.server.clients import map_client
from xoot.server.confirm import args_digest
from xoot.server.errors import not_found_message, safe_message
from xoot.server.roots import file_uri_path
from xoot.server.schemas.client_info_entry import ClientInfoEntry


def test_not_found_echoes_only_well_formed_keys() -> None:
    """A well-formed key is echoed; arbitrary text is not."""
    assert not_found_message("goal-5") == "not found: goal-5"
    assert not_found_message("xoot:goal-5/batch-1") == "not found: xoot:goal-5/batch-1"
    assert not_found_message("xoot-5") == "not found: malformed key"
    assert not_found_message("'; DROP TABLE item") == "not found: malformed key"


class _Probe(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str
    changes: dict[str, int] = {}


def test_validation_locations_mask_caller_names() -> None:
    """Unknown field names and dict keys become '*'; known fields stay."""
    with pytest.raises(ValidationError) as caught:
        _Probe.model_validate({"title": 5, "secret_name": 1, "changes": {"k": "x"}})
    message = safe_message(caught.value)
    assert "title (string_type)" in message
    assert "* (extra_forbidden)" in message
    assert "changes.* (int_parsing)" in message
    assert "secret_name" not in message and "k (" not in message


def test_conflict_message_uses_public_names() -> None:
    """Reference columns appear under their public names."""
    actors = (Actor(kind=ActorKind.USER, client=Client.CLI),)
    exc = VersionConflictError("goal-3", 4, ("parent_id", "title"), actors)
    assert safe_message(exc) == (
        "VersionConflictError: goal-3 is at version 4; changed since your "
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
def test_map_client(name: str, expected: Client) -> None:
    """Only a name containing claude-code, in any case, maps to code."""
    assert map_client(ClientInfoEntry(name=name, version="1")) is expected
    assert map_client(None) is Client.CHAT


def test_digest_is_canonical() -> None:
    """Key order and spacing do not change the digest; values do."""
    first = args_digest({"a": 1, "b": {"y": [1, 2], "x": "é"}})
    assert first == args_digest({"b": {"x": "é", "y": [1, 2]}, "a": 1})
    assert first != args_digest({"a": 2, "b": {"y": [1, 2], "x": "é"}})
