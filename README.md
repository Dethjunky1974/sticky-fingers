# STICKY FINGERS

The Figma Desktop Bridge plugin, renamed and extended with a Claude pane.

Talk to a Claude Code session from inside Figma. The bridge plugin panel gets a **Claude**
button under `[+]`. The pane talks to a local relay, and the relay drives a headless Claude
Code session through the Agent SDK. One session per Figma file, resumed across days.

```
Figma plugin panel (ui.html)  ──ws://localhost:9240/claude──▶  relay.mjs  ──Agent SDK──▶  Claude Code
```

## Parts

| Path | What |
|---|---|
| `relay.mjs` | WebSocket relay and SDK driver. Port 9240, path `/claude`. |
| `patch-ui.py` | Applies the pane to the bridge's `ui.html` and `manifest.json`. Idempotent. |
| `test-client.mjs` | Fake pane for testing the relay without Figma. |
| `sessions.json` | `fileKey → sessionId`, written by the relay. |
| `attachments/` | Screenshots the pane hands to Claude. |
| `relay.log` | Relay log. |

The patched plugin lives in the MCP checkout on branch `claude-pane`:
`~/Documents/Claude/figma-console-mcp/figma-desktop-bridge/`. `code.js` is untouched.

## Run

```bash
cd ~/CLAUDE/figma-claude-pane && node relay.mjs
```

After editing `relay.mjs`, `./restart.sh` swaps the process without a terminal: it launches
the new relay detached and kills the old one; the pane reconnects and fires the session
start. Works from inside a pane session (the running turn ends when the old relay dies).

Then in Figma: run the Desktop Bridge plugin, press `[+]`, press **Claude**.

Environment overrides: `CLAUDE_PANE_PORT` (9240), `CLAUDE_PANE_MODEL` (`claude-fable-5-1`),
`CLAUDE_PANE_CWD` (home), `CLAUDE_PANE_EXECUTABLE` (path to a specific `claude` binary),
`CLAUDE_CONFIG_DIR` (`~/CLAUDE`).

## What the pane does

- Opens expanded: on plugin launch the `[+]` toolbar and the pane are open and connected.
- **Send**: your text plus file name, key, and current page. Paste a screenshot into the
  field (Cmd+V) or drop an image file on the pane; it is saved under `attachments/` and
  handed to Claude as `[Screenshot] <path>`. A chip shows the count until you send or clear.
- **Comment on selection**: same, plus the selected layers (name, type, id, size) and a
  screenshot of each (first three), saved under `attachments/` and read by Claude.
  Figma's selection is the pointer. A plugin cannot draw a crosshair on the canvas.
- **Allow / Deny**: not shown since 2026-09-03. `canUseTool` in `relay.mjs` auto-allows
  every tool call, and denies figma-console write tools while `~/CLAUDE/figma-scope.json`
  is in `critique` mode (same marker list as `hooks/figma-scope-guard.py`). Probe result
  that drove this: under `permissionMode: 'bypassPermissions'` the settings-file hook did not
  block a write in critique mode, so the gate lives in the relay. The card code stays in
  place for a future opt-in.
- **Scope badge**: mirrors `~/CLAUDE/figma-scope.json` (critique or edit, target nodes).
- **Comment on selection** turns blue while something is selected on the canvas.
- **Session start**: fires by itself when the pane connects, as
  `/design-session-start <file name> <file key>`, once per relay process per file. The
  command resolves the project from the key. The button is the manual re-run.
- **Session end**: sends `/design-session-end`.

## After an upstream update of figma-console-mcp

```bash
cd ~/Documents/Claude/figma-console-mcp
git fetch origin
git rebase origin/main          # on branch claude-pane
# if ui.html or manifest.json conflict: take upstream, then
#   git checkout --theirs figma-desktop-bridge/ui.html figma-desktop-bridge/manifest.json
#   python3 ~/CLAUDE/figma-claude-pane/patch-ui.py
#   git add figma-desktop-bridge && git rebase --continue
npm run build:local             # if dist/ is part of the update
```

The MCP copies `figma-desktop-bridge/` to `~/.figma-console-mcp/plugin/` on every start
(`src/local.ts`, `setupStablePluginDir`). Restart the MCP, then re-run the plugin in Figma.

To test a change without restarting the MCP:

```bash
cp ~/Documents/Claude/figma-console-mcp/figma-desktop-bridge/{manifest.json,ui.html} ~/.figma-console-mcp/plugin/
```

then close and re-run the plugin in Figma. A manifest change needs the full re-run, not
`figma_reload_plugin`.

## Test without Figma

```bash
node test-client.mjs "Reply with exactly: pong"
ALLOW=0 node test-client.mjs "Use the Write tool to create /tmp/probe.txt"   # exercises Deny
```
