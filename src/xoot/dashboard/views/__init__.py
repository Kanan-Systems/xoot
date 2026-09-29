"""
Building API responses from one read snapshot.

Each function takes a connection inside the request's read transaction and
returns a response envelope; lookups by public key raise ApiError 404.
"""
