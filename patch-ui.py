#!/usr/bin/env python3
"""Apply the Claude pane to the Figma Desktop Bridge ui.html and manifest.json.

Idempotent: refuses to run twice on the same file (marker check), and every
anchor must match exactly once. Run from anywhere:

    python3 ~/CLAUDE/figma-claude-pane/patch-ui.py [path/to/figma-desktop-bridge]
"""
import json, sys, pathlib

BRIDGE = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else
                      pathlib.Path.home() / 'Documents/Claude/figma-console-mcp/figma-desktop-bridge')
UI = BRIDGE / 'ui.html'
MANIFEST = BRIDGE / 'manifest.json'
MARK = 'claude-pane:begin'
PORT = 9240

def once(src, anchor, what):
    n = src.count(anchor)
    if n != 1:
        sys.exit(f'anchor for {what} matched {n} times, expected 1')

# ------------------------------------------------------------------ CSS
CSS = f"""
    /* ===== {MARK} ===== */
    .claude-pane {{ flex-direction: column; gap: 6px; align-items: stretch; }}
    .cp-head {{ display: flex; align-items: center; gap: 6px; font-size: 10px; color: var(--figma-color-text-secondary, rgba(255,255,255,0.55)); min-height: 16px; }}
    .cp-head .cp-title {{ color: var(--figma-color-text, rgba(255,255,255,0.9)); font-weight: 600; }}
    .cp-dot {{ width: 6px; height: 6px; border-radius: 50%; background: var(--color-idle); flex: none; }}
    .cp-dot.on {{ background: var(--color-connected); }}
    .cp-dot.busy {{ background: var(--color-waiting); }}
    .cp-dot.err {{ background: var(--color-error); }}
    .cp-badge {{ margin-left: auto; padding: 1px 5px; border: 1px solid var(--figma-color-border, #4a4a4a); border-radius: 3px; font-family: 'SF Mono', 'Menlo', Consolas, monospace; font-size: 9px; white-space: nowrap; max-width: 140px; overflow: hidden; text-overflow: ellipsis; }}
    .cp-badge.edit {{ color: var(--color-error); border-color: var(--color-error); }}
    .cp-badge.critique {{ color: var(--log-info); border-color: var(--log-info); }}
    .cp-transcript {{ max-height: 320px; overflow-y: auto; display: flex; flex-direction: column; gap: 6px; padding: 6px; border: 1px solid var(--figma-color-border, #4a4a4a); border-radius: 3px; background: var(--figma-color-bg, #2c2c2c); font-size: 11px; line-height: 1.45; user-select: text; }}
    .cp-msg {{ white-space: pre-wrap; word-break: break-word; }}
    .cp-msg.user {{ align-self: flex-end; background: var(--figma-color-bg-secondary, #383838); padding: 4px 8px; border-radius: 6px; max-width: 92%; }}
    .cp-msg.assistant {{ align-self: stretch; }}
    .cp-msg.error {{ color: var(--color-error); }}
    .cp-tool {{ font-family: 'SF Mono', 'Menlo', Consolas, monospace; font-size: 9.5px; color: var(--figma-color-text-secondary, rgba(255,255,255,0.55)); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
    .cp-meta {{ font-size: 9px; opacity: .55; }}
    .cp-sel {{ font-size: 10px; color: var(--figma-color-text-secondary, rgba(255,255,255,0.55)); font-family: 'SF Mono', 'Menlo', Consolas, monospace; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
    .cp-perm {{ display: none; flex-direction: column; gap: 4px; padding: 6px; border: 1px solid var(--color-waiting); border-radius: 3px; font-size: 10px; }}
    .cp-perm.visible {{ display: flex; }}
    .cp-perm pre {{ font-family: 'SF Mono', 'Menlo', Consolas, monospace; font-size: 9px; max-height: 80px; overflow: auto; white-space: pre-wrap; word-break: break-all; margin: 0; user-select: text; }}
    .cp-row {{ display: flex; gap: 4px; align-items: flex-end; }}
    .cp-input {{ flex: 1; min-height: 34px; max-height: 120px; resize: vertical; font: inherit; font-size: 11px; line-height: 1.4; padding: 5px 6px; background: var(--figma-color-bg, #2c2c2c); color: var(--figma-color-text, rgba(255,255,255,0.9)); border: 1px solid var(--figma-color-border, #4a4a4a); border-radius: 3px; user-select: text; }}
    .cp-btn {{ height: 24px; padding: 0 8px; border-radius: 3px; border: 1px solid var(--figma-color-border, #4a4a4a); background: transparent; color: var(--figma-color-text, rgba(255,255,255,0.9)); font-size: 10px; cursor: pointer; white-space: nowrap; }}
    .cp-btn:hover {{ border-color: var(--figma-color-text-secondary, rgba(255,255,255,0.55)); }}
    .cp-btn.primary {{ background: var(--figma-color-bg-brand, #0d99ff); border-color: transparent; color: #fff; }}
    .cp-btn.danger {{ color: var(--color-error); border-color: var(--color-error); }}
    .cp-btn.active {{ background: var(--figma-color-bg-brand, #0d99ff); border-color: transparent; color: #fff; }}
    .cp-attach {{ display: none; gap: 6px; align-items: center; font-size: 10px; color: var(--figma-color-text-secondary, rgba(255,255,255,0.55)); }}
    .cp-attach.visible {{ display: flex; }}
    .cp-attach .cp-btn {{ height: 18px; padding: 0 6px; font-size: 9px; }}
    .claude-pane.cp-dragover .cp-input {{ border-color: var(--figma-color-bg-brand, #0d99ff); }}
    .cp-btn:disabled {{ opacity: .45; cursor: default; }}
    .cp-foot {{ display: flex; gap: 6px; align-items: center; justify-content: space-between; font-size: 9px; color: var(--figma-color-text-secondary, rgba(255,255,255,0.55)); }}
    .cp-foot .cp-actions {{ display: flex; gap: 4px; }}
    /* ===== claude-pane:end ===== */
"""

# ------------------------------------------------------------------ markup
SUB_BTN = """      <button class="sub-btn" id="claude-toggle" onclick="toggleClaude()" aria-expanded="false" aria-controls="claude-pane">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
        </svg>
        Claude
      </button>
"""

PANE = """
    <!-- claude-pane:begin — chat with the Claude Code session for this file -->
    <div class="row claude-pane" id="claude-pane" role="region" aria-label="Claude">
      <div class="cp-head">
        <span class="cp-dot" id="cp-dot" aria-hidden="true"></span>
        <span class="cp-title">Claude</span>
        <span id="cp-status">offline</span>
        <span class="cp-badge" id="cp-scope" title="Scope guard state from ~/CLAUDE/figma-scope.json">no scope</span>
      </div>
      <div class="cp-transcript" id="cp-transcript" aria-live="polite"></div>
      <div class="cp-sel" id="cp-sel">Select something on the canvas</div>
      <div class="cp-attach" id="cp-attach"><span id="cp-attach-text"></span><button class="cp-btn" onclick="claudeClearAttachments()" title="Drop the pasted screenshots">Clear</button></div>
      <div class="cp-perm" id="cp-perm" role="alertdialog" aria-labelledby="cp-perm-title">
        <div id="cp-perm-title"><strong>Allow</strong> <span id="cp-perm-tool"></span>?</div>
        <pre id="cp-perm-input"></pre>
        <div class="cp-row">
          <button class="cp-btn primary" onclick="claudePermission(true)">Allow</button>
          <button class="cp-btn danger" onclick="claudePermission(false)">Deny</button>
        </div>
      </div>
      <div class="cp-row">
        <textarea class="cp-input" id="cp-input" rows="2" placeholder="Message Claude… (Enter to send, Shift+Enter for a new line, paste or drop a screenshot)" aria-label="Message Claude"></textarea>
        <button class="cp-btn primary" id="cp-send" onclick="claudeSend('message')" title="Send">Send</button>
      </div>
      <div class="cp-foot">
        <div class="cp-actions">
          <button class="cp-btn" id="cp-comment" onclick="claudeSend('comment')" title="Send the message with the selected layers and their screenshots attached" disabled>Comment on selection</button>
          <button class="cp-btn" id="cp-stop" onclick="claudeInterrupt()" title="Interrupt the current turn" style="display:none">Stop</button>
        </div>
        <div class="cp-actions">
          <button class="cp-btn" onclick="claudeCommand('session-start')" title="Re-run /design-session-start for this file (it runs by itself when the pane connects)">Session start</button>
          <button class="cp-btn" onclick="claudeCommand('session-end')" title="Run /design-session-end">Session end</button>
        </div>
      </div>
    </div>
    <!-- claude-pane:end -->
"""

# ------------------------------------------------------------------ JS
JS = r"""
    // ============================================================================
    // claude-pane:begin — talks to the local relay (~/CLAUDE/figma-claude-pane/relay.mjs)
    // over its own socket. Never joins the bridge's connection pool.
    // ============================================================================
    (function() {
      var CP_URL = 'ws://localhost:%(port)d/claude';
      var CP_MAX_RETRIES = 5;
      var cpWs = null, cpRetries = 0, cpRetryTimer = null;
      var cpFileInfo = null, cpSelection = null, cpPage = null;
      var cpPending = null;          // current permission request {id, toolName, input}
      var cpBubble = null;           // assistant bubble receiving deltas
      var cpBusy = false;
      var cpAttachments = [];        // pasted or dropped screenshots {nodeId, base64, format}

      function $(id) { return document.getElementById(id); }
      function paneVisible() { var p = $('claude-pane'); return !!(p && p.classList.contains('visible')); }

      function setStatus(text, dot) {
        var s = $('cp-status'); if (s) s.textContent = text;
        var d = $('cp-dot'); if (d) d.className = 'cp-dot' + (dot ? ' ' + dot : '');
      }
      function setBusy(b) {
        cpBusy = b;
        var stop = $('cp-stop'); if (stop) stop.style.display = b ? '' : 'none';
        if (b) setStatus('thinking…', 'busy'); else if (cpWs && cpWs.readyState === 1) setStatus('ready', 'on');
        updateCommentButton();
      }
      function updateCommentButton() {
        var b = $('cp-comment'); if (!b) return;
        var has = !!(cpSelection && cpSelection.nodes && cpSelection.nodes.length);
        b.disabled = !has;
        b.classList.toggle('active', has); // blue while a selection exists
      }
      function scrollTranscript() {
        var t = $('cp-transcript'); if (t) t.scrollTop = t.scrollHeight;
      }
      function addMsg(cls, text) {
        var t = $('cp-transcript'); if (!t) return null;
        var d = document.createElement('div');
        d.className = 'cp-msg ' + cls;
        d.textContent = text || '';
        t.appendChild(d);
        while (t.children.length > 200) t.removeChild(t.firstChild);
        scrollTranscript();
        return d;
      }
      function addTool(name, summary) {
        var t = $('cp-transcript'); if (!t) return;
        var d = document.createElement('div');
        d.className = 'cp-tool';
        d.textContent = '⚙ ' + name + (summary ? '  ' + summary : '');
        d.title = summary || name;
        t.appendChild(d);
        cpBubble = null; // next delta opens a fresh bubble after a tool line
        scrollTranscript();
      }
      function renderSelection() {
        var el = $('cp-sel'); if (!el) return;
        var nodes = cpSelection && cpSelection.nodes ? cpSelection.nodes : [];
        if (!nodes.length) { el.textContent = 'Select something on the canvas'; el.title = ''; }
        else if (nodes.length === 1) {
          var n = nodes[0];
          el.textContent = 'Selected: ' + n.name + ' · ' + n.id + ' · ' + Math.round(n.width) + '×' + Math.round(n.height);
          el.title = n.type + ' ' + n.id;
        } else {
          el.textContent = 'Selected: ' + nodes.length + ' layers · ' + nodes.slice(0, 3).map(function(n) { return n.name; }).join(', ') + (nodes.length > 3 ? '…' : '');
          el.title = nodes.map(function(n) { return n.name + ' ' + n.id; }).join('\n');
        }
        updateCommentButton();
      }
      function renderAttachments() {
        var box = $('cp-attach'), t = $('cp-attach-text'); if (!box || !t) return;
        if (!cpAttachments.length) { box.classList.remove('visible'); autoResize(); return; }
        t.textContent = '📎 ' + cpAttachments.length + ' screenshot' + (cpAttachments.length > 1 ? 's' : '') + ' attached';
        box.classList.add('visible');
        autoResize();
      }
      // Files pasted or dropped into the pane. Only images are taken.
      function addFiles(files) {
        var list = Array.prototype.slice.call(files || []).filter(function(f) { return f && f.type && f.type.indexOf('image/') === 0; });
        if (!list.length) return false;
        list.forEach(function(f) {
          var r = new FileReader();
          r.onload = function() {
            var s = String(r.result || ''); var i = s.indexOf(',');
            cpAttachments.push({ nodeId: 'paste-' + (cpAttachments.length + 1), base64: s.slice(i + 1), format: f.type === 'image/jpeg' ? 'JPG' : 'PNG' });
            renderAttachments();
          };
          r.readAsDataURL(f);
        });
        return true;
      }
      window.claudeClearAttachments = function() { cpAttachments = []; renderAttachments(); };
      function renderScope(s) {
        var b = $('cp-scope'); if (!b) return;
        if (!s || !s.mode) { b.textContent = 'no scope'; b.className = 'cp-badge'; b.title = 'No ~/CLAUDE/figma-scope.json'; return; }
        var tgt = (s.target && s.target.length) ? s.target.join(', ') : '—';
        b.textContent = s.mode + ' · ' + tgt;
        b.className = 'cp-badge ' + s.mode;
        b.title = (s.note || '') + '\nmode: ' + s.mode + '\ntarget: ' + tgt;
      }
      function showPermission(req) {
        cpPending = req;
        var tool = $('cp-perm-tool'); if (tool) tool.textContent = req.toolName;
        var inp = $('cp-perm-input'); if (inp) inp.textContent = req.summary || JSON.stringify(req.input, null, 1);
        var box = $('cp-perm'); if (box) box.classList.add('visible');
        setStatus('needs your OK', 'busy');
        autoResize();
      }
      function hidePermission() {
        cpPending = null;
        var box = $('cp-perm'); if (box) box.classList.remove('visible');
        if (cpBusy) setStatus('thinking…', 'busy');
        autoResize();
      }

      // ---------------------------------------------------------------- socket
      function connect() {
        if (cpWs && cpWs.readyState <= 1) return;
        setStatus('connecting…', '');
        try { cpWs = new WebSocket(CP_URL); } catch (e) { onDown(); return; }
        cpWs.onopen = function() {
          cpRetries = 0;
          setStatus('connected', 'on');
          hello();
        };
        cpWs.onmessage = function(ev) {
          var msg; try { msg = JSON.parse(ev.data); } catch (e) { return; }
          switch (msg.type) {
            case 'hello_ack':
              setStatus(msg.resumed ? 'session resumed' : 'new session', 'on');
              setBusy(!!msg.busy);
              break;
            case 'replay_start': { var tr = $('cp-transcript'); if (tr) tr.innerHTML = ''; cpBubble = null; break; }
            case 'replay_end': cpBubble = null; setBusy(!!msg.busy); scrollTranscript(); break;
            case 'user_echo': cpBubble = null; addMsg('user', msg.text); break;
            case 'status': setStatus(msg.text, cpBusy ? 'busy' : 'on'); break;
            case 'scope': renderScope(msg); break;
            case 'session': break;
            case 'busy': setBusy(true); break;
            case 'delta':
              if (!cpBubble) cpBubble = addMsg('assistant', '');
              cpBubble.textContent += msg.text;
              scrollTranscript();
              break;
            case 'tool': addTool(msg.name, msg.summary); break;
            case 'result':
              if (!cpBubble && msg.text) addMsg(msg.isError ? 'error' : 'assistant', msg.text);
              else if (cpBubble && msg.isError) cpBubble.classList.add('error');
              if (typeof msg.cost === 'number') {
                var m = document.createElement('div'); m.className = 'cp-meta';
                m.textContent = '$' + msg.cost.toFixed(3) + (msg.turns ? ' · ' + msg.turns + ' turns' : '');
                $('cp-transcript').appendChild(m);
              }
              cpBubble = null;
              setBusy(false);
              scrollTranscript();
              break;
            case 'permission': showPermission(msg); break;
            case 'command_echo': addMsg('user', msg.text); setBusy(true); break; // relay fired a command itself
            case 'permission_closed': if (cpPending && cpPending.id === msg.id) hidePermission(); break;
            case 'error': addMsg('error', msg.text); setBusy(false); break;
          }
        };
        cpWs.onclose = function() { onDown(); };
        cpWs.onerror = function() { /* onclose follows */ };
      }
      function onDown() {
        cpWs = null;
        if (!paneVisible()) { setStatus('offline', ''); return; }
        if (cpRetries >= CP_MAX_RETRIES) { setStatus('relay not running — start it: node ~/CLAUDE/figma-claude-pane/relay.mjs', 'err'); return; }
        cpRetries++;
        setStatus('reconnecting… (' + cpRetries + '/' + CP_MAX_RETRIES + ')', 'err');
        clearTimeout(cpRetryTimer);
        cpRetryTimer = setTimeout(connect, 1000 * cpRetries);
      }
      function send(obj) {
        if (!cpWs || cpWs.readyState !== 1) { addMsg('error', 'Not connected to the relay.'); return false; }
        cpWs.send(JSON.stringify(obj));
        return true;
      }
      function hello() {
        var doHello = function() {
          if (!cpFileInfo) return;
          send({ type: 'hello', fileKey: cpFileInfo.fileKey, fileName: cpFileInfo.fileName });
        };
        if (cpFileInfo) { doHello(); return; }
        // _origSendPluginCommand keeps the hello out of the Activity log.
        var fn = window._origSendPluginCommand || window.sendPluginCommand;
        fn('GET_FILE_INFO').then(function(r) {
          if (r && r.success && r.fileInfo) { cpFileInfo = r.fileInfo; cpPage = r.fileInfo.currentPage; doHello(); }
          else setStatus('could not read file info', 'err');
        }).catch(function() { setStatus('could not read file info', 'err'); });
      }
      function context() {
        return {
          fileKey: cpFileInfo ? cpFileInfo.fileKey : null,
          fileName: cpFileInfo ? cpFileInfo.fileName : null,
          page: cpPage || (cpFileInfo ? cpFileInfo.currentPage : null)
        };
      }

      // ---------------------------------------------------------------- public
      window.toggleClaude = function() {
        var opening = !paneVisible();
        toggleRow('claude-pane', 'claude-toggle');
        if (opening) {
          cpRetries = 0;
          connect();
          renderSelection();
          setTimeout(function() { var i = $('cp-input'); if (i) i.focus(); }, 50);
        }
        autoResize();
      };

      window.claudeSend = function(kind) {
        var input = $('cp-input'); if (!input) return;
        var text = input.value.trim();
        if (!text) { input.focus(); return; }
        var queued = cpBusy;
        var payload = { type: 'user', text: text, context: context(), selection: [], attachments: cpAttachments.slice() };
        var pasted = cpAttachments.length;
        var finish = function() {
          if (!send(payload)) return;
          input.value = '';
          cpAttachments = []; renderAttachments();
          if (queued) addMsg('user', text + '   (queued)'); // otherwise the relay echoes it back
          if (typeof logWithHistory === 'function') logWithHistory('Claude: ' + text.slice(0, 60), 'info');
          setBusy(true);
        };
        if (kind !== 'comment' || !(cpSelection && cpSelection.nodes && cpSelection.nodes.length)) { finish(); return; }

        var nodes = cpSelection.nodes.slice(0, 3);
        payload.selection = cpSelection.nodes.slice(0, 50);
        setStatus('capturing ' + nodes.length + ' screenshot' + (nodes.length > 1 ? 's' : '') + '…', 'busy');
        var jobs = nodes.map(function(n) {
          return window.captureScreenshot(n.id, { format: 'PNG' }).then(function(r) {
            if (r && r.success && r.image && r.image.base64) {
              payload.attachments.push({ nodeId: n.id, base64: r.image.base64, format: r.image.format || 'PNG' });
            }
          });
        });
        Promise.all(jobs).then(finish, finish);
      };

      window.claudePermission = function(allow) {
        if (!cpPending) return;
        send({ type: 'permission_reply', id: cpPending.id, allow: !!allow });
        if (typeof logWithHistory === 'function') logWithHistory('Claude permission: ' + (allow ? 'allow ' : 'deny ') + cpPending.toolName, allow ? 'success' : 'warn');
        hidePermission();
      };

      window.claudeCommand = function(name) {
        var args = name === 'session-start' && cpFileInfo ? cpFileInfo.fileName : '';
        if (!send({ type: 'command', name: name, args: args, context: context() })) return;
        setBusy(true);
      };

      window.claudeInterrupt = function() { send({ type: 'interrupt' }); };

      // Fed from window.onmessage (SELECTION_CHANGE / PAGE_CHANGE cases).
      window.__claudePaneSelection = function(data) { cpSelection = data || null; if (data && data.page) cpPage = data.page; renderSelection(); };
      window.__claudePanePage = function(data) { if (data && (data.name || data.page)) cpPage = data.name || data.page; };

      // Open with the [+] toolbar and this pane expanded. Registered after the bridge's
      // own load handler, so it runs after the bridge has laid itself out.
      window.addEventListener('load', function() {
        setTimeout(function() {
          var sub = $('sub-toolbar');
          if (sub && !sub.classList.contains('visible')) toggleSubToolbar();
          if (!paneVisible()) window.toggleClaude();
        }, 0);
      });

      // Enter sends, Shift+Enter inserts a newline.
      document.addEventListener('DOMContentLoaded', function() {
        var i = $('cp-input'); if (!i) return;
        i.addEventListener('keydown', function(e) {
          if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); window.claudeSend('message'); }
        });
        // Paste a screenshot from the clipboard into the field.
        i.addEventListener('paste', function(e) {
          var files = e.clipboardData && e.clipboardData.files;
          if (files && files.length && addFiles(files)) e.preventDefault();
        });
        // Drop an image file anywhere on the pane.
        var pane = $('claude-pane'); if (!pane) return;
        ['dragenter', 'dragover'].forEach(function(ev) { pane.addEventListener(ev, function(e) { e.preventDefault(); pane.classList.add('cp-dragover'); }); });
        pane.addEventListener('dragleave', function() { pane.classList.remove('cp-dragover'); });
        pane.addEventListener('drop', function(e) { e.preventDefault(); pane.classList.remove('cp-dragover'); if (e.dataTransfer) addFiles(e.dataTransfer.files); });
      });
    })();
    // ============================================================================
    // claude-pane:end
    // ============================================================================
""" % {'port': PORT}

# ------------------------------------------------------------------ apply to ui.html
src = UI.read_text()
if MARK in src:
    sys.exit('ui.html already carries the Claude pane; nothing to do')

# A. CSS before </style>
once(src, '  </style>', 'css'); src = src.replace('  </style>', CSS + '  </style>')

# B. sub-toolbar button, after the copy-log button
anchor_b = """          <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
        </svg>
      </button>
    </div>
"""
once(src, anchor_b, 'sub-toolbar button')
src = src.replace(anchor_b, anchor_b.replace('      </button>\n    </div>\n', '      </button>\n' + SUB_BTN + '    </div>\n'))

# C. pane markup after the log panel
anchor_c = """    <div class="row log-panel" id="log-panel">
      <div class="log-entries" id="log-entries"></div>
    </div>
"""
once(src, anchor_c, 'log panel'); src = src.replace(anchor_c, anchor_c + PANE)

# D. width follows the pane
once(src, 'var PLUGIN_WIDTH = 240;', 'PLUGIN_WIDTH def')
src = src.replace('var PLUGIN_WIDTH = 240;',
    "var PLUGIN_WIDTH = 240;\n"
    "    var PLUGIN_WIDTH_PANE = 360; // claude-pane: wider while the chat is open\n"
    "    function pluginWidth() { var p = document.getElementById('claude-pane'); return (p && p.classList.contains('visible')) ? PLUGIN_WIDTH_PANE : PLUGIN_WIDTH; }")
once(src, "pluginMessage: { type: 'RESIZE_UI', width: PLUGIN_WIDTH, height: Math.ceil(h) }", 'RESIZE_UI width')
src = src.replace("pluginMessage: { type: 'RESIZE_UI', width: PLUGIN_WIDTH, height: Math.ceil(h) }",
                  "pluginMessage: { type: 'RESIZE_UI', width: pluginWidth(), height: Math.ceil(h) }")

# E. [+] closing collapses the pane too
anchor_e = "        if (log.classList.contains('visible')) toggleLog();\n"
once(src, anchor_e, 'toggleSubToolbar collapse')
src = src.replace(anchor_e, anchor_e + "        var cpane = document.getElementById('claude-pane'); // claude-pane\n        if (cpane && cpane.classList.contains('visible')) toggleClaude();\n")

# F. selection + page pushes feed the pane
anchor_f = "          if (window.__wsForwardSelectionChange) window.__wsForwardSelectionChange(msg.data);\n"
once(src, anchor_f, 'SELECTION_CHANGE')
src = src.replace(anchor_f, anchor_f + "          if (window.__claudePaneSelection) window.__claudePaneSelection(msg.data); // claude-pane\n")
anchor_f2 = "          if (window.__wsForwardPageChange) window.__wsForwardPageChange(msg.data);\n"
once(src, anchor_f2, 'PAGE_CHANGE')
src = src.replace(anchor_f2, anchor_f2 + "          if (window.__claudePanePage) window.__claudePanePage(msg.data); // claude-pane\n")

# G. JS before </script>
once(src, '  </script>', 'script end'); src = src.replace('  </script>', JS + '  </script>')

UI.write_text(src)
print(f'ui.html patched ({len(src)} bytes)')

# ------------------------------------------------------------------ manifest (text-level, keeps upstream formatting)
ms = MANIFEST.read_text()
if f'localhost:{PORT}' in ms:
    print('manifest.json already patched')
else:
    old = '      "https://figma-console-mcp.southleft.com"\n'
    once(ms, old + '    ]', 'manifest allowedDomains tail') if ms.count(old) != 2 else None
    ms = ms.replace(old, old.rstrip('\n') + ',\n' + f'      "ws://localhost:{PORT}",\n      "http://localhost:{PORT}"\n')
    tail = 'for remote write access.",'
    once(ms, tail, 'manifest reasoning')
    ms = ms.replace(tail, f'for remote write access. Port {PORT} is the local Claude pane relay (~/CLAUDE/figma-claude-pane).",')
    json.loads(ms)
    MANIFEST.write_text(ms)
    print('manifest.json patched (text-level)')
