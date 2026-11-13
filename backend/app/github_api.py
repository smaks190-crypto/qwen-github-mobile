import asyncio
import os
import pathlib
import tempfile
from contextlib import asynccontextmanager
from urllib.parse import quote
import httpx
from . import config

API = 'https://api.github.com'

async def github(method: str, route: str, **kwargs):
    if not config.GITHUB_TOKEN or config.GITHUB_TOKEN.startswith('REPLACE_'):
        raise RuntimeError('GITHUB_TOKEN is not configured')
    async with httpx.AsyncClient(timeout=35, headers={
        'Authorization': f'Bearer {config.GITHUB_TOKEN}',
        'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28',
        'User-Agent': 'qwen-github-mobile'
    }) as client:
        response = await client.request(method, API + route, **kwargs)
        response.raise_for_status()
        return response.json() if response.content else {}

async def git(*args, cwd: pathlib.Path, env=None, timeout=150):
    proc = await asyncio.create_subprocess_exec('git', *args, cwd=str(cwd), env=env,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout)
    except TimeoutError:
        proc.kill()
        await proc.communicate()
        raise RuntimeError('Git operation timed out')
    if proc.returncode:
        # Never expose command output: it might contain remote URLs/secrets.
        raise RuntimeError(f'Git operation failed (exit code {proc.returncode})')
    return stdout.decode(errors='replace').strip()

@asynccontextmanager
async def checkout(repo: str):
    # Keep GitHub PAT out of process arguments and git remote URLs.
    with tempfile.TemporaryDirectory(prefix='qwen-gh-') as directory:
        root = pathlib.Path(directory)
        askpass = root / 'askpass.sh'
        askpass.write_text('''#!/bin/sh
case "$1" in
  *Username*) printf x-access-token ;;
  *Password*) printf %s "$GITHUB_TOKEN" ;;
esac
''')
        askpass.chmod(0o700)
        env = dict(os.environ, GIT_ASKPASS=str(askpass), GIT_TERMINAL_PROMPT='0', GITHUB_TOKEN=config.GITHUB_TOKEN)
        workdir = root / 'work'
        await git('clone', '--depth', '1', '--', f'https://github.com/{repo}.git', str(workdir), cwd=root, env=env)
        yield workdir, env

async def repo_info(repo):
    info, pulls = await asyncio.gather(github('GET', f'/repos/{repo}'),
                                     github('GET', f'/repos/{repo}/pulls', params={'state':'open','per_page':100}))
    return {'name': info['full_name'], 'default_branch': info['default_branch'],
            'description': info.get('description'), 'open_issues_including_prs': info['open_issues_count'],
            'open_pr_count_first_page': len(pulls), 'url': info['html_url']}

async def pull_requests(repo):
    data = await github('GET', f'/repos/{repo}/pulls', params={'state':'open','per_page':100})
    return [{'number':pr['number'], 'title':pr['title'], 'url':pr['html_url'], 'author':pr['user']['login']} for pr in data]

async def create_issue(repo, title, body):
    result = await github('POST', f'/repos/{repo}/issues', json={'title':title, 'body':body})
    return {'number':result['number'], 'url':result['html_url']}

async def post_review(repo, number, comment):
    result = await github('POST', f'/repos/{repo}/issues/{number}/comments', json={'body':comment})
    return result['html_url']

async def open_pr(repo, title, branch, description, base):
    result = await github('POST', f'/repos/{repo}/pulls',
        json={'title':title[:240], 'head':branch, 'base':base, 'body':description, 'draft':True})
    return {'number':result['number'], 'url':result['html_url']}
