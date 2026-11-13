import asyncio
import logging
from pathlib import Path
from . import config, store

log = logging.getLogger(__name__)
_app = None

def firebase_enabled():
    return Path(config.FIREBASE_CREDENTIALS_PATH).is_file()

def send_sync(repo, title, body, data):
    global _app
    if not firebase_enabled():
        return
    import firebase_admin
    from firebase_admin import credentials, messaging
    if _app is None:
        _app = firebase_admin.initialize_app(credentials.Certificate(config.FIREBASE_CREDENTIALS_PATH))
    for token in store.tokens_for_repo(repo):
        try:
            messaging.send(messaging.Message(token=token,
                notification=messaging.Notification(title=title, body=body[:350]),
                data={str(k):str(v) for k,v in data.items()}))
        except Exception:
            log.exception('FCM delivery failed for a registered device')

async def notify(repo, title, body, data):
    await asyncio.to_thread(send_sync, repo, title, body, data)
