import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import { composeCommand, filterCommands } from '../../src/uagent/static/command-picker.mjs';

test('command picker searches dynamically supplied labels', () => {
  const commands = [
    { name: 'otel', summary: 'Observability', usage: ':otel' },
    { name: 'model', summary: 'Model information', usage: ':model' },
  ];
  assert.deepEqual(filterCommands(commands, 'OBSER'), [commands[0]]);
  assert.deepEqual(filterCommands(commands, ':MODEL'), [commands[1]]);
  assert.deepEqual(filterCommands(commands, ''), commands);
});

test('command picker composes one command and optional subcommand and args', () => {
  assert.equal(composeCommand('otel'), ':otel');
  assert.equal(composeCommand('tools', 'list', 'python'), ':tools list python');
  assert.equal(composeCommand('model', '', '  '), ':model');
});

test('development and packaged Web use identical picker modules', () => {
  const paths = [
    new URL('../public/static/command-picker.mjs', import.meta.url),
    new URL('../../src/uagent/static/command-picker.mjs', import.meta.url),
  ];
  assert.equal(readFileSync(paths[0], 'utf8'), readFileSync(paths[1], 'utf8'));
  const style = [
    new URL('../public/static/command-picker.css', import.meta.url),
    new URL('../../src/uagent/static/command-picker.css', import.meta.url),
  ];
  assert.equal(readFileSync(style[0], 'utf8'), readFileSync(style[1], 'utf8'));
});

test('chat input treats colon-prefixed text as a user message, not a command', () => {
  const source = readFileSync(
    new URL('../src/lib/components/InputArea.svelte', import.meta.url),
    'utf8',
  );
  assert.ok(source.includes('onSend(message, pendingAttachments)'));
  assert.ok(!source.includes('onCommand('));
  const bundle = readFileSync(
    new URL('../../src/uagent/static/assets/index.js', import.meta.url),
    'utf8',
  );
  assert.ok(bundle.includes('function w(h){return[]}'));
  assert.ok(!bundle.includes('if(h.startsWith(":")){if(t.onCommand(h)'));
});
