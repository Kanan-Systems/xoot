"""The text forms of `xoot project list` and a single project."""

from xoot.cli.render.text import clean, table
from xoot.server.schemas.project_entry import ProjectEntry
from xoot.server.schemas.projects_list_output import ProjectsListOutput

HEADERS = ("PREFIX", "NAME", "ALIASES", "PATHS")


def render_project_list(output: ProjectsListOutput) -> str:
    """
    Render every project as one table row, under the database path.

    Args:
        - output (ProjectsListOutput): the projects and the database path.

    Returns:
        - text (str): the database line and the table.
    """
    rows = [
        (
            p.key_prefix,
            clean(p.name),
            ", ".join(p.aliases) or "-",
            ", ".join(clean(path) for path in p.paths) or "-",
        )
        for p in output.projects
    ]
    return f"database: {clean(output.db_path)}\n" + table(HEADERS, rows)


def render_project(entry: ProjectEntry) -> str:
    """
    Render one project.

    Args:
        - entry (ProjectEntry): the project.

    Returns:
        - text (str): prefix, name, aliases and paths, one per line.
    """
    return "\n".join(project_lines(entry))


def project_lines(entry: ProjectEntry) -> list[str]:
    """
    Describe a project in labelled lines.

    Args:
        - entry (ProjectEntry): the project.

    Returns:
        - lines (list[str]): one line per attribute, values cleaned.
    """
    return [
        f"project: {entry.key_prefix}",
        f"name: {clean(entry.name)}",
        f"aliases: {', '.join(entry.aliases) or '-'}",
        f"paths: {', '.join(clean(path) for path in entry.paths) or '-'}",
    ]
