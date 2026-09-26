"""
Domain rules and transactions.

Services own the transaction boundary: each public function opens one read
or write transaction on a Store and applies every rule inside it.
"""
