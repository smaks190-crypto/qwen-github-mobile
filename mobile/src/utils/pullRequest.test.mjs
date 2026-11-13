import assert from 'node:assert/strict';
import { test } from 'node:test';
import { readFileSync } from 'node:fs';
const source = readFileSync(new URL('./pullRequest.js', import.meta.url), 'utf8');
const { makePullRequestUrl, readPreparedPullRequest } = await import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'));
test('GitHub compare query opens the official create form', () => {
  const url = makePullRequestUrl({repo:'owner/repo',head:'qwen/fix',base:'main',title:'Fix issue',body:'hello & world'});
  assert.match(url, /compare\/main\.\.\.qwen%2Ffix\?quick_pull=1/);
  assert.match(url, /title=Fix%20issue/);
  assert.match(url, /body=hello%20%26%20world/);
});
test('requires different valid branches and title', () => {
  assert.throws(() => makePullRequestUrl({repo:'owner/repo',head:'main',base:'main',title:'ok'}));
  assert.throws(() => makePullRequestUrl({repo:'owner/repo',head:'feature',base:'main',title:''}));
  assert.throws(() => makePullRequestUrl({repo:'owner/repo',head:'../x',base:'main',title:'ok'}));
});
test('auto prompt requires completed matching code task', () => {
  const result = JSON.stringify({type:'pr_ready',repo:'owner/repo',base:'main',head:'qwen/fix',title:'Fix'});
  assert.equal(readPreparedPullRequest({id:'a',repo:'owner/repo',kind:'code',status:'completed',result}).head,'qwen/fix');
  assert.equal(readPreparedPullRequest({id:'a',repo:'other/repo',kind:'code',status:'completed',result}),null);
  assert.equal(readPreparedPullRequest({id:'a',repo:'owner/repo',kind:'code',status:'running',result}),null);
});
