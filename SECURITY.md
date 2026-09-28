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
started, no port is opened, and xoot makes no network request.

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

## Secrets in identifiers

Never put secrets in key prefixes or aliases. They are part of every key,
appear in outputs and events, and cannot be redacted. `xoot redact` clears
titles, bodies, summaries and project names only.

## install.sh

`install.sh` prints every action before running it, and `--dry-run` runs
none. It never uses sudo and never downloads anything itself: `uv tool
install` resolves the dependencies from the package index as usual. It edits
no shell rc files and writes no Windows files; the Claude Desktop snippet is
only printed. Registering with Claude Code asks first unless `--yes` is
given.

## No telemetry

xoot collects no telemetry and makes no network requests. Adoption is
judged only from public GitHub signals.
