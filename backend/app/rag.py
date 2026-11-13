import re
from pathlib import Path
from . import store
from .github_api import checkout

ALLOWED_EXT = {'.py', '.js', '.jsx', '.ts', '.tsx', '.json', '.md', '.txt',
               '.kt', '.kts', '.java', '.xml', '.gradle', '.yml', '.yaml', '.toml', '.sql', '.html', '.css'}
SKIP_DIRS = {'.git', 'node_modules', 'build', 'dist', '.gradle', '.next', '.expo', 'venv', '.venv', 'coverage'}
SENSITIVE = re.compile(r'(^|/)(\.env|.*\.pem|.*\.key|.*credentials.*|.*service-account.*|.*secret.*)(/|$)', re.I)

def index_directory(repo: str, root: Path):
    chunks = []
    count = 0
    for path in root.rglob('*'):
        if not path.is_file() or path.is_symlink():
            continue
        relative = path.relative_to(root).as_posix()
        if set(path.relative_to(root).parts) & SKIP_DIRS or SENSITIVE.search(relative):
            continue
        if path.suffix.lower() not in ALLOWED_EXT or path.stat().st_size > 200_000:
            continue
        try:
            content = path.read_text('utf-8')
        except (UnicodeError, OSError):
            continue
        count += 1
        # Simple chunking keeps code context bounded, unlike truncating whole files.
        for start in range(0, len(content), 4000):
            if len(chunks) >= 12000:
                break
            chunks.append((relative, content[start:start+4200]))
        if len(chunks) >= 12000:
            break
    store.store_index(repo, chunks)
    return {'indexed_files': count, 'indexed_chunks': len(chunks)}

async def index_repo(repo):
    async with checkout(repo) as (directory, _):
        return index_directory(repo, directory)

def search_repo(repo, query):
    terms = list(dict.fromkeys(re.findall(r'[\w]{2,}', query.lower())))[:12]
    if not terms:
        return []
    # Query comes from the user. Build FTS expression only from extracted word tokens.
    fts = ' OR '.join('"' + t.replace('"', '') + '"' for t in terms)
    return store.search_index(repo, fts)
