import asyncio
import json
import pathlib
import re
import time
from . import store
from . import github_api as gh
from . import rag
from .agent import qwen_code

def safe_changed_path(path):
    pure = pathlib.PurePosixPath(path)
    if pure.is_absolute() or '..' in pure.parts or not path or path.startswith('"'):
        return False
    forbidden = {'id_rsa', 'id_ed25519', '.npmrc', '.pypirc', 'google-services.json'}
    for part in pure.parts:
        part_low = part.lower()
        if (part_low in forbidden or part_low == '.env' or part_low.startswith('.env.')
            or 'secret' in part_low or 'credential' in part_low or 'service-account' in part_low
            or part_low.endswith(('.pem', '.key', '.p12', '.pfx'))):
            return False
    return not path.startswith('.github/workflows/')

async def perform(task):
    repo, kind = task['repo'], task['kind']
    args = json.loads(task['args'])
    if kind == 'issue':
        result = await gh.create_issue(repo, args['title'], args['body'])
        return f"Issue #{result['number']} created: {result['url']}"
    if kind == 'index':
        result = await rag.index_repo(repo)
        return f"Indexed {result['indexed_files']} files / {result['indexed_chunks']} chunks"
    if kind == 'review':
        number = int(args['pr_number'])
        pr = await gh.github('GET', f'/repos/{repo}/pulls/{number}')
        if pr['state'] != 'open':
            raise ValueError('Review requires an open PR')
        # Use GitHub's PR files API for a concrete diff. GitHub may truncate
        # individual patches; don't pretend an incomplete review is exhaustive.
        changed_files = await gh.github('GET', f'/repos/{repo}/pulls/{number}/files',
                                        params={'per_page':100})
        patch_text = []
        for file in changed_files:
            patch_text.append(f"### {file.get('filename')} ({file.get('status')})\n{file.get('patch', '[binary or patch unavailable]')}")
        preview = '\n\n'.join(patch_text)[:250000]
        async with gh.checkout(repo) as (work, env):
            (work / 'QWEN_REVIEW_DIFF.txt').write_text(preview, encoding='utf-8')
            await gh.git('fetch','--depth','30','origin',f'pull/{number}/head',cwd=work,env=env)
            await gh.git('checkout','--detach','FETCH_HEAD',cwd=work,env=env)
            prompt = (f'Review GitHub PR #{number} titled {pr["title"]!r}. Read the code in the '
                      'workspace and QWEN_REVIEW_DIFF.txt carefully. The patch may be truncated. Return a Russian-language review with file/line references '
                      'where possible, focus on correctness, security, performance, and test gaps. '
                      'Do not modify files, execute commands, publish anything or claim tests ran. '
                      'Limit to concrete findings and explicitly state uncertainty.')
            review = await qwen_code(work, prompt, 'review')
        url = await gh.post_review(repo, number, '## AI Code Review (Qwen Code)\n\n' + review[:40000])
        return f'Review posted: {url}'
    if kind == 'code':
        description = args['task_description'].strip()
        if len(description) > 5000:
            raise ValueError('Task description too long')
        async with gh.checkout(repo) as (work, env):
            # repo.default_branch is not assumed to be 'main'.
            info = await gh.repo_info(repo)
            base = info['default_branch']
            branch = f'qwen/task-{int(time.time())}-{task["id"][:8]}'
            await gh.git('switch','-c',branch,cwd=work,env=env)
            prompt = ('Implement the following user-approved change in this repository. '
                      'Read relevant existing files, follow the project conventions and keep changes focused. '
                      'Use file editing tools only; no shell commands, no secret reading, no remote calls, '
                      'no modifications to .env, credentials, or GitHub workflows. '
                      'Never merge, push, or publish anything. The host will review your changed files. '
                      f'\nTask: {description}')
            explanation = await qwen_code(work, prompt, 'edit')
            changed = await gh.git('status','--porcelain','--untracked-files=all',cwd=work,env=env)
            if not changed:
                raise RuntimeError('Qwen Code made no changes; no PR created')
            # Paths after two status chars; rename entries are rejected conservatively.
            paths = [line[3:] for line in changed.splitlines()]
            if any(' -> ' in path or not safe_changed_path(path) for path in paths):
                raise RuntimeError('Changes include restricted paths. Refusing to publish')
            await gh.git('diff','--check',cwd=work,env=env)
            await gh.git('add','--all',cwd=work,env=env)
            await gh.git('-c','user.name=Qwen GitHub Agent','-c',
                         'user.email=qwen-agent@users.noreply.github.com',
                         'commit','-m',f'AI: {description[:70]}',cwd=work,env=env)
            await gh.git('push','--set-upstream','origin',branch,cwd=work,env=env)
            pr = await gh.open_pr(repo, f'AI: {description[:180]}',branch,
                '## Task\n' + description + '\n\n## Qwen Code summary\n' + explanation[:8000]
                + '\n\n**Draft PR. CI status must be checked before merging.**', base)
            return f"Draft PR #{pr['number']} created: {pr['url']}. CI is not yet verified."
    raise ValueError('Unrecognized task kind')

async def run_task(task_id):
    task = store.get_task(task_id)
    if not task or task['status'] != 'queued':
        return
    store.update_status(task_id, 'running')
    try:
        result = await perform(task)
    except Exception as exc:
        # Keep error type and a sanitized, truncated message only; no tokens.
        store.update_status(task_id, 'failed', f'{type(exc).__name__}: {str(exc)[:350]}')
    else:
        store.update_status(task_id, 'completed', result)
