// Fake pane: hello → one user message → print events until result. Usage: node test-client.mjs "prompt"
import WebSocket from 'ws';
const prompt = process.argv[2] || 'Reply with exactly: pong';
const ws = new WebSocket('ws://localhost:9240/claude');
let text = '';
const t0 = Date.now();
ws.on('open', () => {
  ws.send(JSON.stringify({ type: 'hello', fileKey: 'TESTFILE', fileName: 'Relay test' }));
  setTimeout(() => ws.send(JSON.stringify({ type: 'user', text: prompt, context: { fileKey: 'TESTFILE', fileName: 'Relay test', page: 'Test page' }, selection: [], attachments: [] })), 300);
});
ws.on('message', d => {
  const m = JSON.parse(d);
  if (m.type === 'delta') { text += m.text; return; }
  if (m.type === 'permission') { console.log('PERMISSION', m.toolName, m.summary); ws.send(JSON.stringify({ type: 'permission_reply', id: m.id, allow: process.env.ALLOW !== '0' })); return; }
  console.log(((Date.now() - t0) / 1000).toFixed(1) + 's', JSON.stringify(m).slice(0, 300));
  if (m.type === 'result') { console.log('TEXT:', text.slice(0, 500)); ws.close(); process.exit(0); }
});
ws.on('error', e => { console.error('ws error', e.message); process.exit(1); });
setTimeout(() => { console.error('timeout'); process.exit(2); }, 180000);
