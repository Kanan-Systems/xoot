"""
Request bodies of the dashboard's write routes.

Every model forbids unknown fields and bounds each value by the same limits
the services enforce, so a body that validates here is refused, if at all,
only by a domain rule.
"""
