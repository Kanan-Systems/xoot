"""Project tools: projects_list and brief_get."""

from mcp.server.mcpserver import Context, MCPServer

from xoot.server.brief import build_brief, project_entry
from xoot.server.db_call import run_db
from xoot.server.resolution import resolve_project
from xoot.server.roots import root_paths
from xoot.server.schemas.arguments import ProjectAlias
from xoot.server.schemas.brief_output import BriefOutput
from xoot.server.schemas.projects_list_output import ProjectsListOutput
from xoot.server.tool_meta import READ, RESOLUTION, describe
from xoot.services.project_service import list_projects
from xoot.store.store import Store


async def projects_list(ctx: Context) -> ProjectsListOutput:
    """
    List every registered project and the database path.

    Args:
        - ctx (Context): the request context.

    Returns:
        - output (ProjectsListOutput): projects and the database path.
    """

    def work(store: Store) -> ProjectsListOutput:
        projects = [project_entry(p) for p in list_projects(store)]
        return ProjectsListOutput(db_path=str(store.path), projects=projects)

    return await run_db(ctx, work)


async def brief_get(ctx: Context, project: ProjectAlias = None) -> BriefOutput:
    """
    Summarize one project.

    Args:
        - ctx (Context): the request context.
        - project (str | None): an alias or prefix; resolved from roots or
          cwd if None.

    Returns:
        - output (BriefOutput): the brief.
    """
    roots = await root_paths(ctx, project)

    def work(store: Store) -> BriefOutput:
        found, resolved_by = resolve_project(store, project, roots)
        with store.read() as conn:
            return build_brief(conn, found, resolved_by, store.path)

    return await run_db(ctx, work)


def register(server: MCPServer) -> None:
    """
    Add the project tools to a server.

    Args:
        - server (MCPServer): the server.
    """
    server.add_tool(
        projects_list,
        description=describe(
            "List registered projects with their key prefixes, names, aliases "
            "and paths, and the database file in use."
        ),
        annotations=READ,
    )
    server.add_tool(
        brief_get,
        description=describe(
            "Brief on one project: item counts per category, open sessions, "
            "active and awaiting-input items, pending session-backlog items, the "
            "project-backlog count, the latest decisions, and the workflow: per "
            "kind, each state with its category and whether transitions are "
            f"restricted. Read this first. {RESOLUTION}"
        ),
        annotations=READ,
    )
