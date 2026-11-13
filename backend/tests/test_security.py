import hashlib
import hmac
import os
import tempfile
from pathlib import Path

os.environ['APP_API_TOKEN']='test-secret-long'
os.environ['GITHUB_WEBHOOK_SECRET']='test-webhook-secret'
os.environ['ALLOWED_REPOS']='owner/repo'
os.environ['DB_PATH']=str(Path(tempfile.gettempdir())/'qwen-gh-test.sqlite3')

from app.security import verify_webhook, ensure_repo
from app.tasks import safe_changed_path
from app import store
from fastapi import HTTPException


def test_valid_webhook_signature():
    body=b'{"test": 1}'
    sig='sha256='+hmac.new(b'test-webhook-secret',body,hashlib.sha256).hexdigest()
    assert verify_webhook(body,sig)
    assert not verify_webhook(body,None)
    assert not verify_webhook(body,'sha256=not-a-match')


def test_repo_allowlist():
    assert ensure_repo('owner/repo') == 'owner/repo'
    try:
        ensure_repo('attacker/repo')
        assert False
    except HTTPException as error:
        assert error.status_code == 403


def test_restricted_paths():
    assert safe_changed_path('src/main.py')
    assert not safe_changed_path('.env')
    assert not safe_changed_path('../secrets.txt')
    assert not safe_changed_path('.github/workflows/ci.yml')
    assert not safe_changed_path('service-account.json')


def test_task_confirmation_atomic():
    store.initialize()
    task=store.create_task('owner/repo','issue',{'title':'test', 'body':'test'})
    assert store.queue_task(task['id'])
    assert not store.queue_task(task['id'])


def test_nested_sensitive_paths():
    assert not safe_changed_path('backend/.env.production')
    assert not safe_changed_path('configs/secrets.yml')
    assert not safe_changed_path('android/google-services.json')
