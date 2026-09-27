"""
The xoot MCP server: stdio tools over the domain services.

Tools take public keys (never raw ids), resolve them, run every database call
on a worker thread with its own short-lived Store, and turn domain errors into
safe tool errors. Run it with `xoot-mcp` or `python -m xoot.server`.
"""
