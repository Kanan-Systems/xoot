"""The security headers every dashboard response carries."""

CSP = (
    "default-src 'none'; script-src 'self'; style-src 'self'; "
    "img-src 'self' data:; connect-src 'self'; font-src 'self'; "
    "base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
)

ALWAYS = {
    "content-security-policy": CSP,
    "x-content-type-options": "nosniff",
    "referrer-policy": "no-referrer",
}

# API bodies hold tracker data; no browser or proxy may keep them.
API_ONLY = {"cache-control": "no-store"}
