from fastapi.testclient import TestClient
from app.main import app
from app import store


def test_auth_and_repositories():
    with TestClient(app) as client:
        assert client.get('/health').status_code == 200
        assert client.get('/repos').status_code == 401
        result = client.get('/repos', headers={'Authorization':'Bearer test-secret-long'})
        assert result.status_code == 200
        assert result.json()['repos'] == ['owner/repo']


def test_confirm_requires_auth():
    store.initialize()
    created = store.create_task('owner/repo','issue',{'title':'test','body':'test'})
    with TestClient(app) as client:
        assert client.post(f'/tasks/{created["id"]}/confirm').status_code == 401
