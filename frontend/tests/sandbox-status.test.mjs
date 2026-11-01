import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import { sandboxLabel, sandboxDescription } from '../../src/uagent/static/sandbox-status.mjs';

test('Sandbox badge distinguishes configured, live, and unknown states', () => {
  assert.equal(sandboxLabel('OFF'), 'Sandbox: OFF');
  assert.equal(sandboxLabel('READY'), 'Sandbox: READY');
  assert.equal(sandboxLabel('RUNNING'), 'Sandbox: RUNNING');
  assert.equal(sandboxLabel('untrusted'), 'Sandbox: ?');
  assert.match(sandboxDescription('RUNNING', 'ja'), /稼働中/);
});

test('development and packaged Sandbox indicators are identical', () => {
  const frontend = readFileSync(new URL('../public/sandbox-status.mjs', import.meta.url), 'utf8');
  const packaged = readFileSync(new URL('../../src/uagent/static/sandbox-status.mjs', import.meta.url), 'utf8');
  assert.equal(frontend, packaged);
  assert.ok(frontend.includes("credentials: 'same-origin'"));
  assert.ok(frontend.includes("id !== roomId()"));
});
