"""Project resolution by alias, then key qualifier, then client roots, then cwd."""

from pathlib import Path
from typing import Any

import pytest
from mcp import ClientSession

from xoot.models.event.actor import Actor
from xoot.models.event.write_context import WriteContext
from xoot.models.item.item_create import ItemCreate
from xoot.models.item.item_kind import ItemKind
from xoot.models.project.project_registration import ProjectRegistration
from xoot.services.item_service import create_item
from xoot.services.project_service import register_project
from xoot.store.store import Store

ALIASES = "aliasp, cwdp, innerp, rootp"


@pytest.fixture(name="cwd_dir")
def fixture_cwd_dir(tmp_path: Path) -> Path:
    """A real directory registered to the cwdp project."""
    path = tmp_path / "cwdproj"
    path.mkdir()
    return path.resolve()


@pytest.fixture(name="projects", autouse=True)
def fixture_projects(store: Store, user: Actor, cwd_dir: Path) -> None:
    """Four projects: one per resolution step, plus a nested path; aliasp has goal-1."""
    for prefix, paths in (
        ("aliasp", ()),
        ("cwdp", (str(cwd_dir),)),
        ("rootp", ("/x/proj",)),
        ("innerp", ("/x/proj/inner",)),
    ):
        registration = ProjectRegistration(
            key_prefix=prefix, name=prefix, aliases=(prefix,), paths=paths
        )
        created = register_project(store, registration, user)
        if prefix == "aliasp":
            create_item(
                store,
                created.id,
                ItemCreate(kind=ItemKind.GOAL, title="g"),
                WriteContext(actor=user),
            )


def _found(output: dict[str, Any]) -> tuple[str, str]:
    project = output["project"]
    prefix = project["key_prefix"] if isinstance(project, dict) else project
    return prefix, output["resolved_by"]


def test_alias_beats_roots_and_roots_beat_cwd(cwd_dir: Path, harness: Any) -> None:
    """With all three available, a name wins, and without one the roots win.

    Each alias repeats its own prefix, so the name is reported as "prefix".
    """

    async def scenario(client: ClientSession) -> list[tuple[str, str]]:
        return [
            _found(await harness.ok(client, "brief_get", project="aliasp")),
            _found(await harness.ok(client, "brief_get")),
            _found(await harness.ok(client, "tree_get")),
            _found(await harness.ok(client, "backlog_list")),
            _found(await harness.ok(client, "decisions_list")),
            _found(await harness.ok(client, "tree_get", root="aliasp:goal-1")),
        ]

    found = harness.run(scenario, cwd=cwd_dir, roots=["file:///x/proj"])
    assert found == (
        [("aliasp", "prefix")] + [("rootp", "roots")] * 4 + [("aliasp", "qualified")]
    )


def test_cwd_when_the_client_has_no_roots(cwd_dir: Path, harness: Any) -> None:
    """A client without the roots capability falls back to the spawn cwd."""

    async def scenario(client: ClientSession) -> tuple[str, str]:
        return _found(await harness.ok(client, "brief_get"))

    assert harness.run(scenario, cwd=cwd_dir) == ("cwdp", "cwd")


@pytest.mark.parametrize(
    ("roots", "expected"),
    [
        (["file:///x/proj2"], ("cwdp", "cwd")),
        (["file:///x/proj/innerx"], ("rootp", "roots")),
        (["file:///x/proj/sub/dir"], ("rootp", "roots")),
        (["file:///x/proj", "file:///x/proj/inner/deep"], ("innerp", "roots")),
        (["file://localhost/x/proj/inner"], ("innerp", "roots")),
    ],
)
def test_roots_match_whole_segments_only(
    cwd_dir: Path,
    harness: Any,
    roots: list[str],
    expected: tuple[str, str],
) -> None:
    """/x/proj2 is not /x/proj; the longest match across all roots wins."""

    async def scenario(client: ClientSession) -> tuple[str, str]:
        return _found(await harness.ok(client, "brief_get"))

    assert harness.run(scenario, cwd=cwd_dir, roots=roots) == expected


def test_unresolved_lists_the_aliases(tmp_path: Path, harness: Any) -> None:
    """Nothing matching, or an unknown alias, names every alias and echoes nothing."""

    async def scenario(client: ClientSession) -> list[str]:
        return [
            await harness.error(client, "brief_get"),
            await harness.error(client, "brief_get", project="zzz-unknown"),
            await harness.error(
                client, "item_create", kind="goal", title="t", project="NOT A SLUG"
            ),
        ]

    roots = ["file:///elsewhere", "https://example.com/x/proj", "file://host/x/proj"]
    messages = harness.run(scenario, cwd=tmp_path, roots=roots)
    for message in messages:
        assert f"one of: {ALIASES}" in message
        assert "zzz-unknown" not in message and "NOT A SLUG" not in message
