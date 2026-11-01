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
      sockets.push(this);
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
