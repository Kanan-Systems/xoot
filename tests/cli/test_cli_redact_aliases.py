"""
Redacting a project name keeps its aliases, and says which ones may still
spell the old name, with the command to remove each; rename's help says
the same.
"""

from typing import Any

import pytest

from xoot.cli.commands.common import ALIAS_HINT
from xoot.cli.commands.redact import name_slug
from xoot.models.event.actor import Actor
from xoot.models.project.project_registration import ProjectRegistration
from xoot.services.project_service import get_overview, register_project
from xoot.store.store import Store


def _register(store: Store, user: Actor, name: str, *aliases: str) -> int:
    registration = ProjectRegistration(key_prefix="kr", name=name, aliases=aliases)
    return register_project(store, registration, user).id


def _warnings(err: str) -> list[str]:
    return [line for line in err.splitlines() if line.startswith("warning: ")]


def test_matching_aliases_are_listed_and_kept(
    xoot: Any, store: Store, user: Actor
) -> None:
    """Only the alias spelling the old name is listed; none is removed."""
    project_id = _register(store, user, "Kroot Site", "kroot-site", "ks")
    run = xoot("redact", "kr", "name", "--yes")
    assert run.code == 0, run.err
    assert _warnings(run.err) == [
        f"warning: {ALIAS_HINT}",
        "warning: alias kroot-site: xoot project remove-alias kroot-site "
        "--project kr",
    ]
    assert get_overview(store, project_id).aliases == ("kroot-site", "ks")


def test_every_alias_is_listed_when_none_matches(
    xoot: Any, store: Store, user: Actor
) -> None:
    """No alias spells the name: each one is listed, to be checked by hand."""
    _register(store, user, "Kanan Root", "kroot", "ks")
    run = xoot("redact", "kr", "name", "--yes")
    assert run.code == 0, run.err
    assert _warnings(run.err)[1:] == [
        "warning: alias kroot: xoot project remove-alias kroot --project kr",
        "warning: alias ks: xoot project remove-alias ks --project kr",
    ]


def test_an_alias_spelling_the_new_name_is_listed(
    xoot: Any, store: Store, user: Actor
) -> None:
    """ "[redacted]" spells "redacted": an alias with that name is named too."""
    _register(store, user, "Kanan Root", "redacted", "ks")
    run = xoot("redact", "kr", "name", "--yes")
    assert _warnings(run.err)[1:] == [
        "warning: alias redacted: xoot project remove-alias redacted --project kr"
    ]


def test_no_aliases_no_warning(xoot: Any, store: Store, user: Actor) -> None:
    """A project without aliases has nothing to warn about."""
    _register(store, user, "Kanan Root")
    run = xoot("redact", "kr", "name", "--yes")
    assert run.code == 0, run.err
    assert _warnings(run.err) == []


def test_an_item_redaction_does_not_warn(xoot: Any, secret_item: Any) -> None:
    """Only a project name redaction checks aliases."""
    run = xoot("redact", f"xoot:{secret_item.key}", "title", "--yes")
    assert run.code == 0, run.err
    assert _warnings(run.err) == []


def test_rename_help_carries_the_hint(xoot: Any) -> None:
    """The same sentence, reflowed by argparse."""
    run = xoot("project", "rename", "--help")
    assert " ".join(ALIAS_HINT.split()) in " ".join(run.out.split())


@pytest.mark.parametrize(
    ("name", "slug"),
    [("Kroot Site", "kroot-site"), ("[redacted]", "redacted"), ("a__b  c", "a-b-c")],
)
def test_name_slug(name: str, slug: str) -> None:
    """Lowercase, runs of anything else become one hyphen, none at the ends."""
    assert name_slug(name) == slug
