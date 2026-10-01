# Clients

How to connect each client to xoot, and what each one actually does when it
starts the server. Install xoot first (see the [README](../README.md#install)).

## Claude Code

Register xoot once, at user scope, one way or the other: never both, or
Claude Code gets the same tools twice.

- **The plugin** (recommended, and what `install.sh` offers): the xoot MCP
  server plus the `xoot-workflow` skill. The checkout is a local plugin
  marketplace:

  ```sh
  claude plugin marketplace add --scope user /path/to/xoot
  claude plugin install --scope user xoot@xoot
  ```

  The plugin runs `xoot-mcp` by name, so the uv tool bin directory
  (`uv tool dir --bin`) must be on the PATH Claude Code starts with.

- **claude mcp add**: the server alone, without the skill:

  ```sh
  claude mcp add xoot --scope user -- "$(uv tool dir --bin)/xoot-mcp"
  ```

`install.sh` skips registration when it finds either one (`claude plugin
list` or `claude mcp get xoot`).

Claude Code sends its launch directory as the MCP root, and xoot resolves
the project from the roots. Launch it inside a registered project directory
and project-level calls need no `project` argument.

## Claude Desktop on Windows (WSL)

The server runs inside WSL; Desktop starts it through `wsl.exe`.

1. Install xoot inside WSL with `./install.sh`. On WSL it prints the entry
   below with your distro name and the absolute `xoot-mcp` path.
2. In Claude Desktop, open **Settings > Developer > Edit Config**.
3. Put the `xoot` entry inside the existing `mcpServers` object. Do not add a
   second `mcpServers` key:

   ```json
   {
     "mcpServers": {
       "xoot": {
         "command": "wsl.exe",
         "args": ["-d", "Ubuntu-24.04", "/home/you/.local/bin/xoot-mcp"]
       }
     }
   }
   ```

   `wsl.exe -d <distro>` names the distro that runs the server; use the name
   `install.sh` printed and the absolute path it printed.
4. Fully quit Claude Desktop after every config change: end it in Task
   Manager, since closing the window leaves it running. Then start it again.

What to expect:

- The server's working directory is `/mnt/c/WINDOWS/System32`, which is no
  project's directory. Always pass `project` (an alias or key prefix) in
  Desktop chats; `projects_list` shows the choices.
- Each Desktop launch starts two server processes. Both open the same
  database.
- Desktop does not show a tool's `destructiveHint`. xoot's safeguard is the
  two-phase confirm: bulk creates, subtree drops and moves, and backlog
  pushes return a plan and a single-use `confirm_token` first, and write
  nothing until the same call is repeated with that token.

## Browser (no MCP)

Chats without MCP, such as claude.ai in a browser, use paste mode (block
format, limits and the full steps:
[Claude in the browser](../README.md#claude-in-the-browser-paste-mode)):

1. `xoot paste brief --project NAME` and paste the brief into the chat.
2. Copy Claude's reply with the copy button under the whole message. A code
   block's own copy button drops the fence lines, and the block no longer
   parses.
3. `xoot paste apply reply.md`, or on WSL the `xpaste` alias, which reads
   the Windows clipboard.
4. Paste the `xoot-receipt` block it prints back into the chat.

## Environment

Clients do not start the server from your shell, so do not rely on your
shell's variables reaching it. Measured: Claude Desktop, through `wsl.exe`,
passed only the minimal set of variables in the table below, with no
`CLAUDE_*` and no `XDG_DATA_HOME`. Claude Code passed through the
environment it was started with.

If you set `XDG_DATA_HOME`, the server and the CLI can end up on different
databases:

- Claude Desktop: append `"--db", "<path>/xoot/xoot.db"` to the entry's
  `args`; `install.sh` prints that line when `XDG_DATA_HOME` is set.
- Claude Code with `claude mcp add`: add `--db` after the command:

  ```sh
  claude mcp add xoot --scope user -- "$(uv tool dir --bin)/xoot-mcp" --db "$XDG_DATA_HOME/xoot/xoot.db"
  ```

- Claude Code with the plugin: the plugin passes no `--db`, so start Claude
  Code from a shell where `XDG_DATA_HOME` is set.

The server logs the database path it uses to stderr once at start. If that
path is unsafe (a symlink, another owner, or group or other permissions on
the directory or the files), the server exits at start with exit code 3 and
`error: UnsafePathError: ...` in the client's server log, the line `xoot
dashboard` prints, instead of failing each tool call.

## Measured facts

Observed on Windows with WSL2 in live verifications of the server (2026-09):
by inspecting the running `xoot-mcp` processes and from what the server
received at initialization.

| | Claude Code 2.1.283 (in WSL) | Claude Desktop (Windows, via `wsl.exe`) |
|---|---|---|
| Working directory | The directory Claude Code was launched in | `/mnt/c/WINDOWS/System32` |
| Environment | The environment Claude Code was started with | 21 variable names, minimal, no `CLAUDE_*`, no `XDG_DATA_HOME`: `DBUS_SESSION_BUS_ADDRESS`, `DISPLAY`, `HOME`, `HOSTTYPE`, `LANG`, `LOGNAME`, `NAME`, `PATH`, `PULSE_SERVER`, `PWD`, `SHELL`, `SHLVL`, `TERM`, `USER`, `WAYLAND_DISPLAY`, `WSL2_GUI_APPS_ENABLED`, `WSLENV`, `WSL_DISTRO_NAME`, `WSL_INTEROP`, `XDG_RUNTIME_DIR`, `_` |
| Roots | Sent; the project resolved by roots (`resolved_by: roots`) | Never matched a project; values not measured |
| `client_info` | `claude-code` 2.1.283, so writes record client `code` | `claude-ai` 0.1.0, so writes record client `chat` |
| Protocol version | `2025-11-25` | Not measured |
| Server processes | One per running Claude Code | Two per Desktop launch |
