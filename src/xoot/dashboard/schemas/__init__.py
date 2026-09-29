"""
Response envelopes of the dashboard API.

They reuse the MCP server's leaf models (items, decisions, events,
tree and workflow entries) but carry none of the MCP-only fields: no
resolved_by, no header and no database path.
"""
