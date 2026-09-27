"""
Paste mode: apply one xoot block copied from a chat reply.

The parser extracts and validates the block, and the executor runs it in one
write transaction: once as a dry run that always rolls back, then for real,
refusing to commit unless the result matches the dry run exactly.
"""
