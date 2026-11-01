import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import { createContext, runInContext } from 'node:vm';

const source = readFileSync(new URL('../src/lib/stores.svelte.js', import.meta.url), 'utf8')
  .split('\n')
  .filter((line) => !line.trimStart().startsWith('export {'))
  .join('\n')
  .replaceAll('export ', '');
const bundle = readFileSync(
  new URL('../../src/uagent/static/assets/index.js', import.meta.url),
  'utf8',
);

function makeSocketHarness() {
  const sockets = [];
  const timers = [];
  class FakeSocket {
    static CONNECTING = 0;
    static OPEN = 1;
    static CLOSING = 2;
    constructor(url) {
      this.url = url;
      this.readyState = FakeSocket.CONNECTING;
      this.sent = [];
      sockets.push(this);
    }
    send(data) {
      if (this.failSend) throw new Error('send failed');
      this.sent.push(JSON.parse(data));
    }
    close() {
      this.readyState = 3;
      this.onclose?.({ code: 1006 });
    }
  }
  const context = createContext({
    $state: (value) => value,
    URL,
    WebSocket: FakeSocket,
    document: { documentElement: { lang: 'en' } },
    history: { replaceState() {} },
    window: {
      location: {
        href: 'https://app.example/room/alpha',
        host: 'app.example',
        protocol: 'https:',
      },
    },
    setTimeout: (callback) => {
      const timer = { callback };
      timers.push(timer);
      return timer;
    },
    clearTimeout: (timer) => { timer.cancelled = true; },
  });
  runInContext(source, context);
  return { sockets, timers, run: (code) => runInContext(code, context) };
}

test('connect keeps one socket while the first handshake is pending', () => {
  const { sockets, run } = makeSocketHarness();
  run('connect()');
  run('connect()');
  assert.equal(sockets.length, 1);
  assert.equal(run('getWs()'), sockets[0]);
  assert.equal(run('getConnected()'), false);
});

test('stale close/message events do not disrupt a replacement socket', () => {
  const { sockets, timers, run } = makeSocketHarness();
  run('connect()');
  const old = sockets[0];
  old.readyState = 2; // CLOSING: reconnect can start before onclose fires.
  run('connect()');
  const active = sockets[1];
  assert.ok(active);
  active.readyState = 1;
  active.onopen();
  old.onmessage({ data: JSON.stringify({
    type: 'status',
    status: { busy: true, label: 'BUSY' },
  }) });
  old.onclose({ code: 1006 });
  assert.equal(run('getWs()'), active);
  assert.equal(run('getConnected()'), true);
  assert.equal(run('getStatus().label'), 'IDLE');
  assert.equal(timers.length, 0);
});

test('the active socket still reconnects on ordinary close', () => {
  const { sockets, timers, run } = makeSocketHarness();
  run('connect()');
  sockets[0].onclose({ code: 1006 });
  assert.equal(run('getConnected()'), false);
  assert.equal(timers.length, 1);
  timers[0].callback();
  assert.equal(sockets.length, 2);
});

test('shipped Web bundle applies the same socket ownership guards', () => {
  assert.ok(bundle.includes('M.ws=o,xo&&(clearTimeout(xo),xo=null),o.onopen=()=>{if(M.ws!==o)return;'));
  assert.ok(bundle.includes('o.onmessage=i=>{if(M.ws!==o)return;'));
  assert.ok(bundle.includes('o.onclose=i=>{if(M.ws!==o)return;'));
});

test('commands retain failure status while the connection is unavailable', () => {
  const { sockets, run } = makeSocketHarness();
  assert.equal(run("sendCommand(':tools')"), false);
  run('connect()');
  assert.equal(run("sendCommand(':tools')"), false);
  sockets[0].readyState = 1;
  sockets[0].onopen();
  assert.equal(run("sendCommand(':tools')"), true);
  assert.deepEqual(sockets[0].sent[0], { type: 'command', text: ':tools' });
  sockets[0].failSend = true;
  assert.equal(run("sendCommand(':help')"), false);
});

test('command transport reports send errors independently of chat input', () => {
  const app = readFileSync(new URL('../src/App.svelte', import.meta.url), 'utf8');
  const input = readFileSync(
    new URL('../src/lib/components/InputArea.svelte', import.meta.url), 'utf8',
  );
  // Dedicated picker calls /api/command; text input only emits user_input.
  assert.ok(!app.includes('onCommand={handleCommand}'));
  assert.ok(!input.includes('onCommand('));
  assert.ok(input.includes('onSend(message, pendingAttachments)'));
  // Internal programmatic commands still report transport failures correctly.
  assert.ok(bundle.includes('function Vr(e){const t=M.ws;if(!t||t.readyState!==WebSocket.OPEN)return!1;try{'));
});
