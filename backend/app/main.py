import asyncio
from contextlib import asynccontextmanager
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field
from . import config, store
from .security import require_auth, ensure_repo
from .chat import process_chat
from .tasks import run_task
from .webhooks import router as webhook_router

@asynccontextmanager
async def lifespan(_):
    store.initialize()
    # Recover queued tasks after a restart in this single-worker prototype.
    with store.db() as conn:
        queued = [r['id'] for r in conn.execute("SELECT id FROM tasks WHERE status='queued'")]
    for task_id in queued:
        asyncio.create_task(run_task(task_id))
    yield

app = FastAPI(title='Qwen GitHub Mobile', version='0.1.0', lifespan=lifespan)
app.include_router(webhook_router)

class ChatReq(BaseModel):
    message: str = Field(min_length=1, max_length=5000)
    history: list[dict] = Field(default_factory=list, max_length=30)

class DeviceReq(BaseModel):
    token: str = Field(min_length=20, max_length=4096)
    repos: list[str] = Field(min_length=1, max_length=50)

@app.get('/health')
def health():
    return {'status':'up','version':'0.1.0'}

@app.get('/repos', dependencies=[Depends(require_auth)])
def repos():
    return {'repos': sorted(config.ALLOWED_REPOS)}

@app.post('/chat', dependencies=[Depends(require_auth)])
async def chat(req: ChatReq):
    try:
        return await process_chat(req.message, req.history)
    except Exception as exc:
        raise HTTPException(502, f'Chat service unavailable: {type(exc).__name__}') from exc

@app.get('/tasks', dependencies=[Depends(require_auth)])
def tasks():
    return {'tasks':store.list_tasks()}

@app.get('/tasks/{task_id}', dependencies=[Depends(require_auth)])
def task(task_id: str):
    result = store.get_task(task_id)
    if not result:
        raise HTTPException(404,'Task not found')
    return result

@app.post('/tasks/{task_id}/confirm', dependencies=[Depends(require_auth)])
async def confirm(task_id: str, background: BackgroundTasks):
    existing = store.get_task(task_id)
    if not existing:
        raise HTTPException(404,'Task not found')
    ensure_repo(existing['repo'])
    if not store.queue_task(task_id):
        raise HTTPException(409,'Task was already approved or executed')
    background.add_task(run_task, task_id)
    return {'task_id':task_id,'status':'queued'}

@app.post('/devices', dependencies=[Depends(require_auth)])
def register_device(req: DeviceReq):
    if not all(isinstance(r,str) for r in req.repos):
        raise HTTPException(400,'Invalid repositories')
    repos = [ensure_repo(r) for r in req.repos]
    store.register_device(req.token, repos)
    return {'status':'registered','repos':repos}
