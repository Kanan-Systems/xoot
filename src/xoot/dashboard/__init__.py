"""
The xoot dashboard: a web view and editor served on 127.0.0.1.

A Starlette app exposes /api/v1 JSON reads and writes built from the same
services and leaf models as the MCP server, and serves the committed
single-page bundle from static/. Every request is checked by the guard (Host
allowlist, per-launch token cookie, Origin; writes also need a JSON body)
and every database access runs on a worker thread with its own short-lived
Store. Run it with `xoot dashboard`.
"""
