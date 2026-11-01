import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import { sandboxLabel, sandboxDescription } from '../../src/uagent/static/sandbox-status.mjs';

test('Sandbox shows a Web server startup snapshot, not per-room activity', () => {
  assert.equal(sandboxLabel('ON'), 'Sandbox: ON');
  assert.equal(sandboxLabel('OFF'), 'Sandbox: OFF');
  assert.equal(sandboxLabel('READY'), 'Sandbox: ?');
  assert.match(sandboxDescription('ON', 'ja'), /初期化済み/);
});

test('one authenticated request in identical development and packaged assets', () => {
  const frontend = readFileSync(new URL('../public/sandbox-status.mjs', import.meta.url), 'utf8');
  const packaged = readFileSync(new URL('../../src/uagent/static/sandbox-status.mjs', import.meta.url), 'utf8');
  assert.equal(frontend, packaged);
  assert.ok(frontend.includes("fetch('/api/sandbox-status'"));
  assert.ok(frontend.includes("credentials: 'same-origin'"));
  assert.equal(frontend.split("fetch('/api/sandbox-status'").length, 2);
  assert.ok(!frontend.includes('setInterval('));
  assert.ok(!frontend.includes('roomId()'));
});
