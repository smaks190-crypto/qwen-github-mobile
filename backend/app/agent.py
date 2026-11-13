import asyncio
import json
import os
import pathlib
from . import config

async def qwen_code(workspace: pathlib.Path, prompt: str, mode: str):
    """Run the real Qwen Code CLI, not a one-shot code generator.

    Docker is required. The container sees only the checkout and Qwen API key,
    NEVER the GitHub token. Run this on a host with a restrictive Docker policy.
    """
    if not config.QWEN_API_KEY or config.QWEN_API_KEY.startswith('REPLACE_'):
        raise RuntimeError('QWENCLOUD_API_KEY not configured')
    if mode not in ('review', 'edit'):
        raise ValueError('Unrecognized agent mode')
    flags = ['--approval-mode', 'plan' if mode == 'review' else 'auto-edit']
    env = {'QWENCLOUD_API_KEY': config.QWEN_API_KEY,
           'OPENAI_BASE_URL': config.QWEN_BASE_URL, 'OPENAI_MODEL': config.QWEN_MODEL}
    cmd = ['docker', 'run', '--rm', '--init', '--read-only',
           '--cap-drop=ALL', '--security-opt=no-new-privileges',
           '--pids-limit=128', '--memory=2g', '--cpus=2',
           '--tmpfs=/tmp:rw,nosuid,size=256m',
           '--user', f'{os.getuid()}:{os.getgid()}',
           '--workdir=/workspace',
           '--mount', f'type=bind,src={workspace.resolve()},dst=/workspace',
           '-e', 'HOME=/tmp']
    for key in env:
        cmd += ['-e', key]
    cmd += [config.WORKER_IMAGE, 'qwen', '-p', prompt, '--safe-mode',
            *flags, '--max-wall-time', '8m', '--max-tool-calls', '40',
            '--output-format', 'json']
    proc = await asyncio.create_subprocess_exec(*cmd,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        env={**os.environ, **env})
    try:
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=520)
    except TimeoutError:
        proc.kill()
        await proc.communicate()
        raise RuntimeError('Qwen agent exceeded runtime limit')
    if proc.returncode:
        raise RuntimeError(f'Qwen agent exited with code {proc.returncode}; check server logs')
    result = stdout.decode('utf-8', errors='replace')
    try:
        parsed = json.loads(result)
        # Qwen Code headless JSON is an ARRAY of message objects.
        if isinstance(parsed, list):
            terminal = next((item for item in reversed(parsed)
                             if isinstance(item, dict) and item.get('type') == 'result'), None)
            if terminal:
                if terminal.get('is_error') or terminal.get('subtype') not in ('success', None):
                    raise RuntimeError('Qwen Code did not complete successfully')
                return str(terminal.get('result') or '')[:20000]
        if isinstance(parsed, dict):
            return str(parsed.get('response') or parsed.get('result') or result)[:20000]
    except ValueError:
        pass
    return result[:20000]
