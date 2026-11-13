import assert from 'node:assert/strict';
import { test } from 'node:test';
import { readFileSync } from 'node:fs';
const source = readFileSync(new URL('./agentRequest.js', import.meta.url), 'utf8');
const { isEditRequest, assertSettings, parseAgentResponse } = await import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'));
test('editing a project must require user approval', () => {
  assert.equal(isEditRequest('Исправь падение при запуске'), true);
  assert.equal(isEditRequest('Покажи открытые PR'), false);
  assert.equal(isEditRequest('Добавь тесты'), true);
});
test('settings require both credentials and a secure endpoint', () => {
  const good = {repo:'owner/repo',githubToken:'gh_token',aiKey:'ai_key',baseUrl:'https://host/v1',model:'model'};
  assert.doesNotThrow(() => assertSettings(good));
  assert.throws(() => assertSettings({...good,githubToken:''}), /GitHub token/);
  assert.throws(() => assertSettings({...good,aiKey:''}), /AI API key/);
  assert.throws(() => assertSettings({...good,baseUrl:'http://host'}), /HTTPS/);
});
test('only a structured, successful Termux result is accepted', () => {
  assert.equal(parseAgentResponse('{"ok":true,"message":"готово"}').message,'готово');
  assert.throws(() => parseAgentResponse('{"ok":false,"message":"тест"}'), /тест/);
  assert.throws(() => parseAgentResponse('terminal logs'), /некорректный/);
});
