"""
The dashboard's default port, apart from the server modules.

The CLI parser needs the default without importing starlette or uvicorn,
which load only when `xoot dashboard` runs.
"""

DEFAULT_PORT = 7373
