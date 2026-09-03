# Claude pane for the Figma Desktop Bridge

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

Then in Figma: run the Desktop Bridge plugin, press `[+]`, press **Claude**.

Environment overrides: `CLAUDE_PANE_PORT` (9240), `CLAUDE_PANE_MODEL` (`claude-fable-5-1`),
`CLAUDE_PANE_CWD` (home), `CLAUDE_PANE_EXECUTABLE` (path to a specific `claude` binary),
`CLAUDE_CONFIG_DIR` (`~/CLAUDE`).

## What the pane does

- **Send**: your text plus file name, key, and current page.
- **Comment on selection**: same, plus the selected layers (name, type, id, size) and a
  screenshot of each (first three), saved under `attachments/` and read by Claude.
  Figma's selection is the pointer. A plugin cannot draw a crosshair on the canvas.
- **Allow / Deny**: not shown since 2026-09-03. The relay runs with
  `permissionMode: 'bypassPermissions'`, so tool calls never prompt. Figma writes are still
  gated by the `figma-scope-guard` PreToolUse hook. The card code stays in place; set the
  mode back to `'default'` in `relay.mjs` to get prompts again.
- **Scope badge**: mirrors `~/CLAUDE/figma-scope.json` (critique or edit, target nodes).
- **Session start / end**: sends `/design-session-start <file name>` or `/design-session-end`.

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
