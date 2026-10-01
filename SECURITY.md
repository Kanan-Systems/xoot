# Security Policy

## Supported versions

| Version | Supported |
|---|---|
| 1.x | Yes |
| Older (0.x) | No |

## Reporting a vulnerability

Report vulnerabilities through GitHub private vulnerability reporting
(the "Report a vulnerability" button on this repository's Security tab).
Do not open a public issue.

## Threat model

xoot is a local-only tracker. All state lives on the user's machine and is
never stored in this repository. No state is sent to a remote service. The
server exposes no filesystem or shell tools. A client can only read and
write xoot's own tracker records, so a compromised or misbehaving client
cannot use xoot to reach arbitrary files or run commands. The main risks in
scope are corrupting or leaking the local tracker data. Anyone with access
to the user's account already has that data, so that attacker is out of scope.

## MCP server

The server speaks MCP over stdio only. The `mcp` SDK it depends on also ships
an HTTP transport, so installing xoot pulls in starlette, uvicorn, PyJWT,
cryptography and the SDK's HTTP client. xoot only ever starts the stdio
transport: that stack is installed and partly imported, but no server is
started, no port is opened, and xoot makes no outbound network request. The
one exception to "no port is opened" is `xoot dashboard`, below, which the
user starts explicitly and which listens on 127.0.0.1 only.

The server checks the database path at start, as every other entry point
does on open: a data directory, database, WAL or SHM file that is a symlink,
has another owner or grants any group or other permission is refused before
anything is served, with exit code 3 and the same line `xoot dashboard`
prints.

Every MCP write is recorded as `claude/code` or `claude/chat`; no tool
accepts an actor or a client. CLI admin commands write as `user/cli`.
The dashboard writes as `user/dashboard`.
`xoot paste apply` writes as `claude/paste`: Claude authored the block and
the user confirmed its plan at the terminal. Changes xoot makes on its own
(goals and batches completing or reopening, workflow remaps) are recorded
with actor `system`. A write's client (`code` or `chat`) comes, per call,
from the name the MCP client reported at initialization. That name is
unauthenticated: it labels the write and grants nothing.

Stored titles and bodies are written by users and agents. The
server returns them as data, and every tool description says so, but a
client model may still read them as instructions. Treat them as untrusted.

## Dashboard

`xoot dashboard` binds 127.0.0.1 only. GET and HEAD are reads. POST and
PATCH are writes, accepted only on the registered write routes under
`/api/v1`; any other method or path gets 405. A write needs the session
cookie (401), an Origin header that is present and names the served origin
exactly (403), a `Content-Type` of `application/json` (415), and a body of
at most 64 KiB (413). A `?token` query or a `?launch` code never
authenticates a write. Each launch makes a random token, printed once to
stdout and never logged or written to disk; it becomes an HttpOnly,
SameSite=Strict cookie named after the port (`xoot_token_<port>`) that every
API request needs (401 without it). `--open` never puts the token in the
browser opener's command line, which other local users can read: the
opener gets a one-time launch code, valid for 30 seconds and redeemable
once, that the dashboard swaps for the cookie. Only
the Host names `xoot.localhost`, `localhost` and `127.0.0.1` on the served
port are answered (400 otherwise, against DNS rebinding), and an API request
from a foreign Origin gets 403. A strict Content-Security-Policy allows
scripts, styles and connections from the dashboard itself only. Uvicorn's
access log is off, since request lines can carry the token.

## Secrets in identifiers

Never put secrets in key prefixes or aliases. They are part of every key,
appear in outputs and events, and cannot be redacted. `xoot redact` clears
item and decision titles and bodies, and project names, only.

## install.sh

`install.sh` prints every action before running it, and `--dry-run` runs
none. It never uses sudo and never downloads anything itself: `uv tool
install` fetches the dependencies from the package index, constrained to
the versions pinned in `uv.lock`, exported to a temporary file
that is removed on exit. It edits no shell rc files and writes no Windows
files; the Claude Desktop snippet is only printed. Installing the Claude
Code plugin asks first unless `--yes` is given.

The installed versions match `uv.lock` (verified with uv 0.9.8). Its hashes
are not enforced. This was tested in an isolated environment: with one
package's sha256 changed in the exported constraints file, `uv tool install
--constraints` installed without error, from a warm cache and from an empty
one (so the package was downloaded). uv 0.9.8 has no `uv tool install`
option that enforces hashes; neither `UV_REQUIRE_HASHES=1` nor passing the
file with `--with-requirements` made it refuse. The tool's uv receipt keeps
versions only. So the lock pins versions but does not rule out a tampered
file of a pinned version; the downloads are as trustworthy as the index
(PyPI over HTTPS).

## No telemetry

xoot collects no telemetry and makes no outbound network requests; the
only listening socket is the dashboard's, on 127.0.0.1. Adoption is judged
only from public GitHub signals.
