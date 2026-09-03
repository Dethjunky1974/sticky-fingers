// Relay between the Figma Desktop Bridge "Claude" pane and a headless Claude Code
// session driven through the Agent SDK. One session per Figma file, resumed across runs.
//
// Run:   node relay.mjs
// Port:  9240 (outside the bridge's own 9223–9232 scan range on purpose)
// Path:  ws://localhost:9240/claude   (anything else is closed)
// Health: GET http://localhost:9240/health → { status:'ok', service:'claude-pane' }
//         (no `clients` field, so the bridge's isOurHealthPayload() ignores it)

import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { randomUUID } from 'node:crypto';
import { WebSocketServer } from 'ws';
import { query } from '@anthropic-ai/claude-agent-sdk';

const PORT = Number(process.env.CLAUDE_PANE_PORT || 9240);
const ROOT = path.dirname(new URL(import.meta.url).pathname);
// Config dir: explicit env wins; otherwise ~/CLAUDE if it exists (Quince's layout), else the default ~/.claude.
const CONFIG_DIR = process.env.CLAUDE_CONFIG_DIR
  || (fs.existsSync(path.join(os.homedir(), 'CLAUDE', 'settings.json')) ? path.join(os.homedir(), 'CLAUDE') : path.join(os.homedir(), '.claude'));
const MODEL = process.env.CLAUDE_PANE_MODEL || 'claude-fable-5-1';
const CWD = process.env.CLAUDE_PANE_CWD || os.homedir();
const SESSIONS_FILE = path.join(ROOT, 'sessions.json');
const ATTACH_DIR = path.join(ROOT, 'attachments');
const SCOPE_FILE = path.join(CONFIG_DIR, 'figma-scope.json');
const LOG_FILE = path.join(ROOT, 'relay.log');
const PERMISSION_TIMEOUT_MS = 5 * 60 * 1000;

fs.mkdirSync(ATTACH_DIR, { recursive: true });

// ---------------------------------------------------------------- logging
function log(level, msg, extra) {
  const line = `${new Date().toISOString()} ${level.padEnd(5)} ${msg}${extra ? ' ' + JSON.stringify(extra) : ''}\n`;
  process.stdout.write(line);
  try { fs.appendFileSync(LOG_FILE, line); } catch { /* non-critical */ }
}

// ---------------------------------------------------------------- sessions.json
function readSessions() {
  try { return JSON.parse(fs.readFileSync(SESSIONS_FILE, 'utf8')); } catch { return {}; }
}
function writeSessions(map) {
  fs.writeFileSync(SESSIONS_FILE, JSON.stringify(map, null, 2) + '\n');
}

// ---------------------------------------------------------------- scope file
function readScope() {
  try {
    const s = JSON.parse(fs.readFileSync(SCOPE_FILE, 'utf8'));
    return { type: 'scope', mode: s.mode || null, target: s.target || [], note: s.note || '' };
  } catch {
    return { type: 'scope', mode: null, target: [], note: '' };
  }
}

// ---------------------------------------------------------------- async queue → AsyncIterable
class Inbox {
  constructor() { this.items = []; this.waiters = []; this.closed = false; }
  push(item) {
    if (this.closed) return;
    const w = this.waiters.shift();
    if (w) w({ value: item, done: false }); else this.items.push(item);
  }
  close() { this.closed = true; for (const w of this.waiters.splice(0)) w({ value: undefined, done: true }); }
  [Symbol.asyncIterator]() {
    return {
      next: () => {
        if (this.items.length) return Promise.resolve({ value: this.items.shift(), done: false });
        if (this.closed) return Promise.resolve({ value: undefined, done: true });
        return new Promise(resolve => this.waiters.push(resolve));
      },
    };
  }
}

// ---------------------------------------------------------------- one Claude session per Figma file
const sessions = new Map(); // fileKey → Session

class Session {
  constructor(fileKey, fileName) {
    this.fileKey = fileKey;
    this.fileName = fileName;
    this.sockets = new Set();
    this.inbox = new Inbox();
    this.pending = new Map(); // permission id → { resolve, timer }
    this.sessionId = readSessions()[fileKey] || null;
    this.resumed = !!this.sessionId;
    this.busy = false;
    this.history = []; // transcript events replayed to a pane that (re)connects
    this.start();
  }

  send(obj) {
    this.remember(obj);
    const data = JSON.stringify(obj);
    for (const ws of this.sockets) if (ws.readyState === 1) ws.send(data);
  }

  remember(obj) {
    if (!['delta', 'tool', 'result', 'error', 'user_echo', 'command_echo'].includes(obj.type)) return;
    const last = this.history[this.history.length - 1];
    if (obj.type === 'delta' && last && last.type === 'delta') last.text += obj.text; // coalesce
    else this.history.push({ ...obj });
    if (this.history.length > 600) this.history.splice(0, this.history.length - 600);
  }

  attach(ws) {
    this.sockets.add(ws);
    ws.send(JSON.stringify({ type: 'hello_ack', sessionId: this.sessionId, resumed: this.resumed, model: MODEL, busy: this.busy }));
    ws.send(JSON.stringify(readScope()));
    // Replay the transcript so nothing said while the pane was closed is lost.
    ws.send(JSON.stringify({ type: 'replay_start', count: this.history.length }));
    for (const ev of this.history) ws.send(JSON.stringify(ev));
    ws.send(JSON.stringify({ type: 'replay_end', busy: this.busy }));
    // Re-arm any permission prompt the pane may have missed while disconnected.
    for (const [id, p] of this.pending) ws.send(JSON.stringify(p.request));
  }

  detach(ws) { this.sockets.delete(ws); }

  start() {
    const options = {
      model: MODEL,
      cwd: CWD,
      env: { ...process.env, CLAUDE_CONFIG_DIR: CONFIG_DIR },
      settingSources: ['user', 'project'],
      includePartialMessages: true,
      // 'default' so every tool that would prompt is routed through canUseTool below,
      // which auto-allows and enforces the scope guard itself. Not 'bypassPermissions':
      // under bypass neither canUseTool nor the settings-file PreToolUse guard blocked a
      // Figma write in critique mode (probe 2026-09-03).
      permissionMode: 'default',
      canUseTool: (toolName, input, opts) => this.canUseTool(toolName, input, opts),
      stderr: d => log('cli', d.trim()),
      ...(this.sessionId ? { resume: this.sessionId } : {}),
    };
    if (process.env.CLAUDE_PANE_EXECUTABLE) options.pathToClaudeCodeExecutable = process.env.CLAUDE_PANE_EXECUTABLE;

    log('info', `session start for ${this.fileName} (${this.fileKey})`, { resume: this.sessionId, model: MODEL });
    this.q = query({ prompt: this.inbox, options });
    this.consume().catch(err => {
      log('error', 'consume loop died', { err: String(err && err.stack || err) });
      this.send({ type: 'error', text: 'Claude session ended: ' + String(err && err.message || err) });
      this.busy = false;
    });
  }

  async consume() {
    for await (const msg of this.q) {
      switch (msg.type) {
        case 'system':
          if (msg.subtype === 'init') {
            if (msg.session_id && msg.session_id !== this.sessionId) this.setSessionId(msg.session_id);
            this.send({ type: 'status', text: `ready · ${msg.model}` });
          }
          break;
        case 'stream_event': {
          if (msg.parent_tool_use_id) break; // subagent chatter stays out of the pane
          const ev = msg.event;
          if (ev && ev.type === 'content_block_delta' && ev.delta && ev.delta.type === 'text_delta') {
            this.send({ type: 'delta', text: ev.delta.text });
          }
          break;
        }
        case 'assistant': {
          if (msg.parent_tool_use_id) break;
          const blocks = (msg.message && Array.isArray(msg.message.content)) ? msg.message.content : [];
          for (const b of blocks) {
            if (b.type === 'tool_use') this.send({ type: 'tool', name: b.name, summary: summariseInput(b.name, b.input) });
          }
          break;
        }
        case 'result': {
          this.busy = false;
          log('info', 'result', { fileKey: this.fileKey, turns: msg.num_turns, cost: msg.total_cost_usd, chars: (msg.result || '').length, subtype: msg.subtype });
          if (msg.session_id && msg.session_id !== this.sessionId) this.setSessionId(msg.session_id);
          this.send({
            type: 'result',
            text: msg.subtype === 'success' ? msg.result : (msg.errors ? msg.errors.join('\n') : msg.subtype),
            isError: msg.subtype !== 'success' || !!msg.is_error,
            cost: msg.total_cost_usd,
            turns: msg.num_turns,
            sessionId: this.sessionId,
          });
          break;
        }
        default:
          break;
      }
    }
    log('info', 'query iterator finished', { fileKey: this.fileKey });
  }

  setSessionId(id) {
    this.sessionId = id;
    const map = readSessions();
    map[this.fileKey] = id;
    writeSessions(map);
    log('info', 'session id recorded', { fileKey: this.fileKey, sessionId: id });
    this.send({ type: 'session', sessionId: id });
  }

  // Auto-allow everything; deny Figma writes while ~/CLAUDE/figma-scope.json is in
  // critique mode. Mirrors hooks/figma-scope-guard.py so the pane has the same gate
  // even if the settings-file hook does not load in the SDK session.
  canUseTool(toolName, input) {
    if (isFigmaWrite(toolName)) {
      const scope = readScope();
      if (scope.mode === 'critique') {
        const target = scope.target.length ? ` (scope target: ${scope.target.join(', ')})` : '';
        log('info', 'blocked by scope guard', { toolName });
        this.send({ type: 'status', text: `blocked · ${toolName.split('__').pop()} · critique mode` });
        return Promise.resolve({
          behavior: 'deny',
          message: `BLOCKED by scope guard: figma-scope.json is in CRITIQUE (read-only) mode${target}. ` +
                   'A critique never edits. Rewrite ~/CLAUDE/figma-scope.json to {"mode":"edit",...} on a named instruction first.',
        });
      }
    }
    return Promise.resolve({ behavior: 'allow', updatedInput: input });
  }

  // Kept for the pane's Allow/Deny card; unused while canUseTool auto-allows.
  answerPermission(id, allow) {
    const p = this.pending.get(id);
    if (!p) return;
    log('info', 'permission answered', { id, allow });
    p.finish(allow
      ? { behavior: 'allow', updatedInput: p.request.input }
      : { behavior: 'deny', message: 'Denied from the Figma pane.' });
  }

  userMessage({ text, context, selection, attachments }) {
    const header = [];
    if (context) header.push(`[Figma context] file: ${context.fileName || this.fileName} (${context.fileKey || this.fileKey}) · page: ${context.page || '?'}`);
    const saved = [];
    for (const a of attachments || []) {
      try {
        const safe = String(a.nodeId || 'page').replace(/[^0-9A-Za-z_-]/g, '_');
        const ext = (a.format || 'PNG').toLowerCase() === 'jpg' ? 'jpg' : 'png';
        const file = path.join(ATTACH_DIR, `${Date.now()}-${safe}.${ext}`);
        fs.writeFileSync(file, Buffer.from(a.base64, 'base64'));
        saved.push({ nodeId: a.nodeId, file });
      } catch (err) {
        log('warn', 'attachment write failed', { err: String(err) });
      }
    }
    for (const n of selection || []) {
      const shot = saved.find(s => s.nodeId === n.id);
      header.push(`[Selection] ${n.name} · ${n.type} · ${n.id} · ${Math.round(n.width)}×${Math.round(n.height)}${shot ? ` → screenshot: ${shot.file}` : ''}`);
    }
    for (const s of saved.filter(s => !(selection || []).some(n => n.id === s.nodeId))) header.push(`[Screenshot] ${s.file}`);
    if (saved.length) header.push('Read each screenshot path with the Read tool before answering.');
    const prompt = (header.length ? header.join('\n') + '\n\n' : '') + text;

    this.remember({ type: 'user_echo', text });
    this.busy = true;
    this.send({ type: 'busy' });
    this.inbox.push({ type: 'user', message: { role: 'user', content: prompt }, parent_tool_use_id: null });
    log('info', 'user message queued', { chars: prompt.length, attachments: saved.length });
  }

  async interrupt() {
    try { await this.q.interrupt(); } catch (err) { log('warn', 'interrupt failed', { err: String(err) }); }
  }
}

// Same marker list as hooks/figma-scope-guard.py. figma_execute is deliberately absent
// there too (dual-use); it stays behavioural.
const MUTATE_MARKERS = ['set_', 'create_', 'delete_', 'move_', 'resize_', 'rename_', 'clone_',
  'update_', 'add_', 'batch_', 'instantiate', 'import_', 'setup_'];
function isFigmaWrite(toolName) {
  if (!toolName.startsWith('mcp__figma-console__')) return false;
  const leaf = toolName.split('__').pop();
  return MUTATE_MARKERS.some(m => leaf.includes(m));
}

function summariseInput(toolName, input) {
  if (!input || typeof input !== 'object') return '';
  const pick = input.command || input.file_path || input.pattern || input.url || input.query || input.description || input.code;
  const s = pick ? String(pick) : JSON.stringify(input);
  return s.length > 140 ? s.slice(0, 137) + '…' : s;
}

// ---------------------------------------------------------------- HTTP + WS
const server = http.createServer((req, res) => {
  if (req.url === '/health') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ status: 'ok', service: 'claude-pane', port: PORT, sessions: sessions.size }));
    return;
  }
  res.writeHead(404); res.end();
});

const wss = new WebSocketServer({ noServer: true });

server.on('upgrade', (req, socket, head) => {
  if (req.url !== '/claude') { socket.destroy(); return; }
  wss.handleUpgrade(req, socket, head, ws => wss.emit('connection', ws, req));
});

wss.on('connection', ws => {
  let session = null;
  log('info', 'pane connected');
  ws.on('message', raw => {
    let msg;
    try { msg = JSON.parse(String(raw)); } catch { return; }
    switch (msg.type) {
      case 'hello': {
        const key = msg.fileKey || 'unknown';
        if (session) session.detach(ws);
        session = sessions.get(key);
        if (!session) { session = new Session(key, msg.fileName || key); sessions.set(key, session); }
        session.attach(ws);
        break;
      }
      case 'user':
        if (!session) { ws.send(JSON.stringify({ type: 'error', text: 'No session. Reopen the pane.' })); break; }
        session.userMessage(msg);
        break;
      case 'permission_reply':
        if (session) session.answerPermission(msg.id, !!msg.allow);
        break;
      case 'command': {
        if (!session) break;
        const map = { 'session-start': '/design-session-start', 'session-end': '/design-session-end' };
        const cmd = map[msg.name];
        if (cmd) session.userMessage({ text: `${cmd} ${msg.args || ''}`.trim(), context: msg.context });
        break;
      }
      case 'interrupt':
        if (session) session.interrupt();
        break;
      default:
        break;
    }
  });
  ws.on('close', () => { if (session) session.detach(ws); log('info', 'pane disconnected'); });
});

// Push scope-guard changes to every pane.
try {
  fs.watch(path.dirname(SCOPE_FILE), (_e, file) => {
    if (file && file !== path.basename(SCOPE_FILE)) return;
    const scope = readScope();
    for (const s of sessions.values()) s.send(scope);
  });
} catch (err) {
  log('warn', 'scope watch unavailable', { err: String(err) });
}

server.listen(PORT, '127.0.0.1', () => {
  log('info', `relay listening on ws://localhost:${PORT}/claude`, { model: MODEL, configDir: CONFIG_DIR, cwd: CWD });
});
