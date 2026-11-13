import assert from 'node:assert/strict';
import { test } from 'node:test';
import { readFileSync } from 'node:fs';

const source = readFileSync(new URL('./termuxPermission.js', import.meta.url), 'utf8');
const { ensureTermuxPermission } = await import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'));

test('already granted: do not request access again', async () => {
  let requests = 0;
  const bridge = {hasTermuxPermission: () => true, requestTermuxPermission: async () => { requests++; }};
  assert.equal(await ensureTermuxPermission(bridge), true);
  assert.equal(requests, 0);
});

test('first use: request permission and recheck Android grant', async () => {
  let granted = false;
  const bridge = {hasTermuxPermission: () => granted, requestTermuxPermission: async () => { granted = true; }};
  assert.equal(await ensureTermuxPermission(bridge), true);
});

test('permission denied: return false and keep task blocked', async () => {
  const bridge = {hasTermuxPermission: () => false, requestTermuxPermission: async () => ({status:'denied'})};
  assert.equal(await ensureTermuxPermission(bridge), false);
});
