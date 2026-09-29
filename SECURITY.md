# Security Policy

## Supported versions

| Version | Supported |
|---|---|
| 0.1.x | Yes |

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
started, no port is opened, and xoot makes no network request. The one
exception is `xoot dashboard`, below, which the user starts explicitly.

Every MCP write is recorded as `claude/code` or `claude/chat`; no tool
accepts an actor or a client. CLI admin commands write as `user/cli`.
`xoot paste apply` writes as `claude/paste`: Claude authored the block and
the user confirmed its plan at the terminal. Changes xoot makes on its own
(auto-backlog moves, workflow remaps) are recorded with actor `system`.
A session's client (`code` or `chat`) comes from the name the MCP
client reports at initialization. That name is unauthenticated: it labels
the session and grants nothing.

Stored titles, bodies and summaries are written by users and agents. The
server returns them as data, and every tool description says so, but a
client model may still read them as instructions. Treat them as untrusted.

## Dashboard

`xoot dashboard` binds 127.0.0.1 only and is read-only in 0.2: anything but
GET and HEAD gets 405. Each launch makes a random token, printed once to
stdout and never logged or written to disk; it becomes an HttpOnly,
SameSite=Strict cookie that every API request needs (401 without it). Only
the Host names `xoot.localhost`, `localhost` and `127.0.0.1` on the served
port are answered (400 otherwise, against DNS rebinding), and an API request
from a foreign Origin gets 403. A strict Content-Security-Policy allows
scripts, styles and connections from the dashboard itself only. Uvicorn's
access log is off, since request lines can carry the token.

## Secrets in identifiers

Never put secrets in key prefixes or aliases. They are part of every key,
appear in outputs and events, and cannot be redacted. `xoot redact` clears
titles, bodies, summaries and project names only.

## install.sh

`install.sh` prints every action before running it, and `--dry-run` runs
none. It never uses sudo and never downloads anything itself: `uv tool
install` fetches the dependencies from the package index, constrained to
the versions pinned in `uv.lock`, exported to a temporary file
that is removed on exit. It edits no shell rc files and writes no Windows
files; the Claude Desktop snippet is only printed. Installing the Claude
Code plugin asks first unless `--yes` is given.

The installed versions match `uv.lock` (verified with uv 0.9.8). Its hashes
are not guaranteed to be enforced: `uv tool install --constraints` does not
promise to check them, and the tool's uv receipt keeps versions only, so the
lock does not rule out a tampered file of a pinned version.

## No telemetry

xoot collects no telemetry and makes no network requests. Adoption is
judged only from public GitHub signals.
