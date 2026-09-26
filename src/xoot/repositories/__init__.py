"""
SQL access, one module per stored model.

Repositories run single statements on a caller-owned connection; they never
open or commit transactions and never apply domain rules.
"""
