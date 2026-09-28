# Clients

How to connect each client to xoot, and what each one actually does when it
starts the server. Install xoot first (see the [README](../README.md#install)).

## Claude Code

Register the installed server once, at user scope, in one of two ways. Use
one, not both.

- **claude mcp add** (what `install.sh` offers):

  ```sh
  claude mcp add xoot --scope user -- "$(uv tool dir --bin)/xoot-mcp"
  ```

- **The plugin**, which adds the same server plus the `xoot-session` skill.
  The checkout is a local plugin marketplace:

  ```sh
  claude plugin marketplace add /path/to/xoot
  claude plugin install xoot@xoot
  ```

  The plugin runs `xoot-mcp` by name, so the uv tool bin directory
  (`uv tool dir --bin`) must be on the PATH Claude Code starts with.

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
  two-phase confirm: bulk creates, subtree drops and moves, and session
  closes return a plan and a single-use `confirm_token` first, and write
  nothing until the same call is repeated with that token.

## Browser (no MCP)

Chats without MCP use paste mode (see the
[README](../README.md#paste-mode)):

1. `xoot paste brief --project NAME` and paste the brief into the chat.
2. Copy Claude's reply with the copy button under the whole message. A code
   block's own copy button drops the fence lines, and the block no longer
   parses.
3. `xoot paste apply reply.md`, or on WSL the `xpaste` alias, which reads
   the Windows clipboard.

## Environment

Clients do not start the server from your shell, so do not rely on your
shell's variables reaching it. Measured: Claude Desktop, through `wsl.exe`,
passed only the fixed set of variables in the table below, and no
`XDG_DATA_HOME`. Claude Code passed through the environment it was started
with.

If you set `XDG_DATA_HOME`, the server and the CLI can end up on different
databases. Pass the database explicitly in every client config:

```sh
claude mcp add xoot --scope user -- "$(uv tool dir --bin)/xoot-mcp" --db "$XDG_DATA_HOME/xoot/xoot.db"
```

In Desktop's entry, append `"--db", "<the same path>"` to `args`;
`install.sh` prints that line when `XDG_DATA_HOME` is set. The server logs
the database path it uses to stderr once at start.

## Measured facts

Observed on 2026-09-28 on Windows with WSL2, by inspecting the running
`xoot-mcp` processes and the results of `session_start`.

| | Claude Code 2.1.283 (in WSL) | Claude Desktop (Windows, via `wsl.exe`) |
|---|---|---|
| Working directory | The directory Claude Code was launched in | `/mnt/c/WINDOWS/System32` |
| Environment | The environment Claude Code was started with | `DBUS_SESSION_BUS_ADDRESS`, `DISPLAY`, `HOME`, `HOSTTYPE`, `LANG`, `LOGNAME`, `NAME`, `PATH`, `PULSE_SERVER`, `PWD`, `SHELL`, `SHLVL`, `TERM`, `USER`, `WAYLAND_DISPLAY`, `WSL2_GUI_APPS_ENABLED`, `WSLENV`, `WSL_DISTRO_NAME`, `WSL_INTEROP`, `XDG_RUNTIME_DIR` |
| Roots | Sent; the project resolved by roots (`resolved_by: roots`) | Not measured |
| `client_info` name | `claude-code`, so sessions record client `code` | Does not contain `claude-code`, so sessions record client `chat` |
| Server processes | One per Claude Code session | Two per Desktop launch |
