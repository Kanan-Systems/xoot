"""
xoot: local-only tracker for goals, batches, subtasks and backlog, for Claude.

Package root. The version is read from the installed distribution metadata so
that pyproject.toml stays its only source.
"""

from importlib.metadata import version

__version__ = version("xoot")
