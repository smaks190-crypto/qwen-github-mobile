import hashlib
import hmac
import re
from fastapi import Header, HTTPException
from . import config

REPO_PATTERN = re.compile(r'^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$')

def require_auth(authorization: str | None = Header(default=None)) -> None:
    if not config.API_TOKEN or config.API_TOKEN.startswith('REPLACE_'):
        raise HTTPException(503, 'Server authentication is not configured')
    expected = f'Bearer {config.API_TOKEN}'
    if not authorization or not hmac.compare_digest(authorization, expected):
        raise HTTPException(401, 'Unauthorized')

def ensure_repo(repo: str) -> str:
    if not REPO_PATTERN.fullmatch(repo):
        raise HTTPException(400, 'Invalid repository name')
    if repo.lower() not in config.ALLOWED_REPOS:
        raise HTTPException(403, 'Repository is not allowed')
    return repo

def verify_webhook(body: bytes, signature: str | None) -> bool:
    if not config.WEBHOOK_SECRET or config.WEBHOOK_SECRET.startswith('REPLACE_') or not signature:
        return False
    expected = 'sha256=' + hmac.new(config.WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)
