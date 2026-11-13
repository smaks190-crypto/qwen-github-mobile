import json
from fastapi import APIRouter, Header, HTTPException, Request
from . import store
from .security import verify_webhook
from .notifications import notify

router = APIRouter()

@router.post('/webhook/github')
async def webhook(request: Request,
                  x_hub_signature_256: str | None = Header(None),
                  x_github_event: str | None = Header(None),
                  x_github_delivery: str | None = Header(None)):
    raw = await request.body()
    if len(raw) > 2_000_000:
        raise HTTPException(413, 'Webhook too large')
    if not verify_webhook(raw, x_hub_signature_256):
        raise HTTPException(403, 'Invalid webhook signature')
    if not x_github_delivery:
        raise HTTPException(400, 'Missing delivery ID')
    if not store.record_delivery(x_github_delivery):
        return {'status':'duplicate'}
    payload = json.loads(raw)
    repo = payload.get('repository',{}).get('full_name','')
    from .config import ALLOWED_REPOS
    if repo.lower() not in ALLOWED_REPOS:
        return {'status':'ignored'}
    event, action = x_github_event, payload.get('action')
    title = body = None
    if event == 'issues' and action in ('opened','closed'):
        item = payload.get('issue',{})
        title, body = 'Issue '+action, f"#{item.get('number')}: {item.get('title','')}"
    elif event == 'pull_request' and action in ('opened','closed','reopened'):
        pr = payload.get('pull_request',{})
        title = 'PR merged' if action=='closed' and pr.get('merged') else 'PR '+action
        body = f"#{pr.get('number')}: {pr.get('title','')}"
    elif event in ('check_suite','check_run','workflow_run') and action == 'completed':
        record = payload.get(event, {})
        if record.get('conclusion') in ('success','failure','cancelled'):
            title, body = 'CI '+record['conclusion'], f"{record.get('name', record.get('head_branch',''))}"
    elif event == 'push':
        title, body = 'New push', str(payload.get('ref',''))
    if title:
        await notify(repo, title, body, {'repo':repo, 'event':event or '', 'action':action or ''})
    return {'status':'ok'}
