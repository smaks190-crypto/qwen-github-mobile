import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

API_TOKEN = os.getenv('APP_API_TOKEN', '')
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN', '')
WEBHOOK_SECRET = os.getenv('GITHUB_WEBHOOK_SECRET', '')
QWEN_API_KEY = os.getenv('QWENCLOUD_API_KEY', '')
QWEN_BASE_URL = os.getenv('OPENAI_BASE_URL', 'https://maas.qwencloudapi.com/compatible-mode/v1')
QWEN_MODEL = os.getenv('OPENAI_MODEL', 'qwen3.8-max')
WORKER_IMAGE = os.getenv('QWEN_WORKER_IMAGE', 'qwen-github-worker:local')
ALLOWED_REPOS = set(x.strip().lower() for x in os.getenv('ALLOWED_REPOS', '').split(',') if x.strip())
DB_PATH = Path(os.getenv('DB_PATH', './data/qwen_app.sqlite3'))
FIREBASE_CREDENTIALS_PATH = os.getenv('FIREBASE_CREDENTIALS_PATH', './firebase-service-account.json')
