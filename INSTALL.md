# STICKY FINGERS · install

Claude Code inside Figma. STICKY FINGERS is the Figma Desktop Bridge plugin (from
figma-console-mcp) with a Claude chat pane added. You get three things:

1. Claude drives Figma through the figma-console MCP server, as before.
2. A **Claude** pane in the plugin window: talk to a Claude Code session without leaving Figma.
3. **Comment on selection**: select layers, type, send. Claude gets the layer names, IDs, sizes
   and a screenshot of each. Paste or drop a screenshot into the field to attach it.

Setup takes about ten minutes. Mac only as tested.

## You need

- Figma desktop app.
- Node.js 20 or newer. Check with `node --version`.
- Claude Code installed and logged in. Check with `claude --version`.
  The pane uses your own Claude account and runs on your machine.
- A Figma personal access token (Figma → Settings → Security → Personal access tokens).
  Only the MCP server needs it, for REST reads like comments and file versions.

## 1. Install the figma-console MCP server in Claude Code

```bash
claude mcp add figma-console -s user -e FIGMA_ACCESS_TOKEN=figd_YOUR_TOKEN_HERE -e ENABLE_MCP_APPS=true -- npx -y figma-console-mcp@latest
```

Start a Claude Code session once so the server starts. It listens on `localhost:9223`.

## 2. Unzip and keep the folder somewhere stable

Unzip `STICKY-FINGERS.zip` into a folder you will not move, for example
`~/Tools/sticky-fingers/`. Figma remembers the manifest path of a development plugin, so
moving the folder later breaks the import.

```
sticky-fingers/
  plugin/    manifest.json  code.js  ui.html  icon.png   ← import this in Figma
  relay/     relay.mjs  package.json  package-lock.json   ← run this
  INSTALL.md
```

## 3. Import the plugin in Figma

Figma → Plugins → Development → **Import plugin from manifest…** → pick
`sticky-fingers/plugin/manifest.json`.

## 4. Install and start the relay

```bash
cd ~/Tools/sticky-fingers/relay
npm install
node relay.mjs
```

Leave that terminal open. The relay listens on `localhost:9240`. Stop it with Ctrl+C.

Options, set as environment variables before `node relay.mjs`:

| Variable | Default | Meaning |
|---|---|---|
| `CLAUDE_PANE_MODEL` | `claude-fable-5-1` | Model for the pane's session. Use `claude-opus-5` if you don't have Fable. |
| `CLAUDE_PANE_PORT` | `9240` | Relay port. Must match the plugin manifest if changed. |
| `CLAUDE_CONFIG_DIR` | `~/.claude` | Your Claude Code config dir, if you moved it. |

## 5. Run it

Figma → Plugins → Development → **STICKY FINGERS**. The window opens with the Claude pane
expanded. Status should read "new session" on the first run and "session resumed" after that.

- **Send**: your message plus the file name and current page.
- **Comment on selection**: select layers first. The button turns blue. Up to three
  screenshots are attached.
- **Paste or drop** a screenshot into the field to attach it to your next message.
- **Session start / Session end** run `/design-session-start` and `/design-session-end` if
  you have those skills; otherwise Claude will say it doesn't know them. Ignore the buttons.
- **Poke** appears while Claude is busy. It asks the relay, not Claude, what is happening:
  time in the turn, tool calls so far, last tool. Instant and free.
- **Stop** interrupts the current turn.

One Claude session per Figma file, kept in `relay/sessions.json`. Delete an entry there to
start that file fresh.

## Permissions

The pane never asks for permission. Every tool call is allowed, except Figma write tools
while `~/CLAUDE/figma-scope.json` (or `$CLAUDE_CONFIG_DIR/figma-scope.json`) says
`"mode": "critique"`. If you don't use that file, nothing is blocked.

## If something is off

| Symptom | Fix |
|---|---|
| Header says "Looking for your AI app…" | The MCP server isn't running. Open a Claude Code session, or check step 1. |
| Pane says "relay not running" | Start `node relay.mjs` (step 4). |
| Pane says "could not read file info" | Close and re-run the plugin. |
| Nothing happens after Send, status "thinking…" | Claude is working. Watch `relay/relay.log` for `result` lines. |
| Model error in the pane | Set `CLAUDE_PANE_MODEL` to a model your account has. |

## Updating

Replace the `plugin/` and `relay/` folders with the new ones, then close and re-run the
plugin in Figma and restart the relay. `sessions.json` can stay.
