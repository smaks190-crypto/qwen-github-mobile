import os
import tempfile
from pathlib import Path

os.environ['APP_API_TOKEN'] = 'test-secret-long'
os.environ['GITHUB_WEBHOOK_SECRET'] = 'test-webhook-secret'
os.environ['ALLOWED_REPOS'] = 'owner/repo'
os.environ['DB_PATH'] = str(Path(tempfile.gettempdir()) / 'qwen-gh-test.sqlite3')
