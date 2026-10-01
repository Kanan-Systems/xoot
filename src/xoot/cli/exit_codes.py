"""
Process exit codes of the xoot CLI.

0 success; 1 a refused request (an XootError or invalid input); 2 a usage
error, as argparse reports it; 3 the database could not be used as asked:
an unsafe path, a failed open, a busy database, stored data it cannot read,
or a redaction whose purge did not complete; `xoot dashboard` also exits 3 when its port cannot be
bound.
"""

OK = 0
ERROR = 1
USAGE = 2
UNAVAILABLE = 3
