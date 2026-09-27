"""
B1-B3: prefixes and aliases share one namespace, "/" is never a project
path, and aliases and paths can be listed and removed.
"""

import sqlite3
from collections.abc import Callable

import pytest
from pydantic import ValidationError

from xoot.exceptions.duplicate_error import DuplicateError
from xoot.exceptions.integrity_violation_error import IntegrityViolationError
from xoot.exceptions.not_found_error import NotFoundError
from xoot.models.event.actor import Actor
from xoot.models.event.write_context import WriteContext
from xoot.models.project.project import Project
from xoot.models.project.project_registration import ProjectRegistration
from xoot.services.project_resolver import resolve_by_alias
from xoot.services.project_service import (
    add_alias,
    add_path,
    get_overview,
    list_projects,
    register_project,
    remove_alias,
    remove_path,
)
from xoot.store.store import Store


def _register(
    store: Store, user: Actor, prefix: str, **names: tuple[str, ...]
) -> Project:
    registration = ProjectRegistration(key_prefix=prefix, name=prefix, **names)
    return register_project(store, registration, user)


@pytest.mark.usefixtures("project")
@pytest.mark.parametrize(
    "case",
    [("xo", (), "key_prefix"), ("new", ("xoot",), "alias")],
    ids=["prefix=alias", "alias=prefix"],
)
def test_registration_refuses_a_name_of_another_project(
    store: Store,
    user: Actor,
    row_counts: Callable[[], dict[str, int]],
    case: tuple[str, tuple[str, ...], str],
) -> None:
    """A prefix equal to an alias, or an alias equal to a prefix, writes nothing."""
    prefix, aliases, field = case
    before = row_counts()
    with pytest.raises(DuplicateError) as caught:
        _register(store, user, prefix, aliases=aliases)
    assert caught.value.field == field
    assert row_counts() == before


def test_add_alias_refuses_another_projects_prefix(
    store: Store, project: Project, other_project: Project, ctx: WriteContext
) -> None:
    """Both directions through add_alias: another prefix, then another alias."""
    with pytest.raises(DuplicateError):
        add_alias(store, other_project.id, project.key_prefix, ctx)
    with pytest.raises(DuplicateError):
        add_alias(store, other_project.id, "xo", ctx)
    with pytest.raises(DuplicateError):
        add_alias(store, project.id, other_project.key_prefix, ctx)


def test_own_prefix_as_alias_is_accepted(
    store: Store, user: Actor, ctx: WriteContext
) -> None:
    """An alias repeating its own prefix is redundant, not ambiguous."""
    registered = _register(store, user, "self", aliases=("self",))
    later = _register(store, user, "late")
    add_alias(store, later.id, "late", ctx)
    for project in (registered, later):
        found = resolve_by_alias(store, project.key_prefix)
        assert found is not None and found.id == project.id
    assert get_overview(store, later.id).aliases == ("late",)


def test_resolve_by_alias_matches_prefixes(
    store: Store, project: Project, other_project: Project
) -> None:
    """A prefix resolves like an alias; an unknown name resolves to nothing."""
    for name, expected in (("xoot", project), ("xo", project), ("nova", other_project)):
        found = resolve_by_alias(store, name)
        assert found is not None and found.id == expected.id
    assert resolve_by_alias(store, "zz") is None


@pytest.mark.parametrize(
    "sql",
    [
        "INSERT INTO project_alias (alias, project_id) VALUES ('nova', :xoot)",
        "UPDATE project_alias SET alias = 'nova' WHERE alias = 'xo'",
        "INSERT INTO project (key_prefix, name, created_at) "
        "VALUES ('xo', 'n', '2026-01-01T00:00:00.000000Z')",
    ],
)
def test_schema_enforces_the_namespace(
    store: Store, project: Project, other_project: Project, sql: str
) -> None:
    """The triggers refuse a cross-project clash even without the service."""
    assert other_project.key_prefix == "nova"
    with pytest.raises(IntegrityViolationError) as caught:
        with store.write() as conn:
            conn.execute(sql, {"xoot": project.id})
    assert isinstance(caught.value.__cause__, sqlite3.IntegrityError)


def test_schema_allows_an_alias_of_the_own_prefix(
    store: Store, project: Project
) -> None:
    """The same exception the service makes holds in SQL."""
    with store.write() as conn:
        conn.execute(
            "INSERT INTO project_alias (alias, project_id) VALUES ('xoot', ?)",
            (project.id,),
        )


@pytest.mark.parametrize("path", ["/", "/..", "//", "/./"])
def test_root_is_refused(
    store: Store, project: Project, ctx: WriteContext, path: str
) -> None:
    """Registration and add_path refuse "/" after normalization."""
    with pytest.raises(ValidationError):
        ProjectRegistration(key_prefix="rooty", name="r", paths=(path,))
    with pytest.raises(ValidationError):
        add_path(store, project.id, path, ctx)


def test_schema_refuses_root(store: Store, project: Project) -> None:
    """The path CHECK refuses "/" itself."""
    with pytest.raises(IntegrityViolationError):
        with store.write() as conn:
            conn.execute(
                "INSERT INTO project_path (path, project_id) VALUES ('/', ?)",
                (project.id,),
            )


def test_remove_alias_and_path(
    store: Store,
    project: Project,
    ctx: WriteContext,
    event_kinds: Callable[[Project], list[tuple[str, str]]],
) -> None:
    """Removals delete the row, record an event and free the name."""
    add_alias(store, project.id, "xa", ctx)
    remove_alias(store, project.id, "xa", ctx)
    assert remove_path(store, project.id, "/work//xoot/", ctx) == "/work/xoot"
    overview = get_overview(store, project.id)
    assert (overview.aliases, overview.paths) == (("xo",), ())
    assert event_kinds(project)[-2:] == [
        ("project", "remove_alias"),
        ("project", "remove_path"),
    ]
    add_alias(store, project.id, "xa", ctx)


def test_removing_what_is_not_there(
    store: Store, project: Project, other_project: Project, ctx: WriteContext
) -> None:
    """A missing alias or path, or another project's, is NotFoundError."""
    add_alias(store, other_project.id, "nv", ctx)
    for call in (
        lambda: remove_alias(store, project.id, "zz", ctx),
        lambda: remove_alias(store, project.id, "nv", ctx),
        lambda: remove_path(store, project.id, "/work/other", ctx),
        lambda: remove_alias(store, 999, "xo", ctx),
    ):
        with pytest.raises(NotFoundError):
            call()


def test_list_projects(
    store: Store, project: Project, other_project: Project, ctx: WriteContext
) -> None:
    """Every project with its aliases and paths, by prefix."""
    add_path(store, other_project.id, "/work/nova", ctx)
    listed = list_projects(store)
    assert [(o.project.id, o.aliases, o.paths) for o in listed] == [
        (other_project.id, (), ("/work/nova",)),
        (project.id, ("xo",), ("/work/xoot",)),
    ]
