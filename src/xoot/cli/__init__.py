"""
The xoot command line: project setup, briefs and trees, workflow files,
redaction and database maintenance, for the user at a terminal.

Every write is recorded as the user through the cli client, outside any
session. Results go to stdout, as text or with --json as the same Pydantic
models the MCP tools return; errors, warnings and prompts go to stderr.
"""
