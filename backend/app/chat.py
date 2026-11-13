import asyncio
import json
from . import config, store, rag
from . import github_api as gh
from .security import ensure_repo

# Model suggests actions, but never decides authorization or executes mutations.
TOOLS = []
def tool(name, description, properties, required):
    TOOLS.append({'type':'function','function':{'name':name,'description':description,
                   'parameters':{'type':'object','properties':properties,'required':required,
                                 'additionalProperties':False}}})
S = lambda desc: {'type':'string','description':desc}
I = lambda desc: {'type':'integer','description':desc}
tool('repo_info','Read repository metadata',{'repo':S('owner/repo')},['repo'])
tool('list_prs','List open pull requests',{'repo':S('owner/repo')},['repo'])
tool('create_issue','Propose creation of GitHub Issue',{'repo':S('owner/repo'),'title':S('Issue title'),'body':S('Issue body')},['repo','title','body'])
tool('review_pr','Propose AI review and publish PR comment',{'repo':S('owner/repo'),'pr_number':I('Pull request number')},['repo','pr_number'])
tool('implement','Propose Qwen Code implementation and draft PR',{'repo':S('owner/repo'),'task_description':S('Change to implement')},['repo','task_description'])
tool('index_repo','Propose repository indexing for search',{'repo':S('owner/repo')},['repo'])
tool('search_repo','Search indexed code chunks',{'repo':S('owner/repo'),'query':S('Search query')},['repo','query'])

KINDS = {'create_issue':'issue','review_pr':'review','implement':'code','index_repo':'index'}

async def process_chat(message: str, history: list):
    if not config.QWEN_API_KEY or config.QWEN_API_KEY.startswith('REPLACE_'):
        return {'reply':'Set QWENCLOUD_API_KEY in backend .env first.', 'actions':[]}
    from openai import OpenAI
    client = OpenAI(api_key=config.QWEN_API_KEY, base_url=config.QWEN_BASE_URL, timeout=60)
    allow = ', '.join(sorted(config.ALLOWED_REPOS))
    messages = [{'role':'system','content':f'''You are a Russian-language GitHub development assistant.
Allowed repositories only: {allow}. Never invent success, PR creation, CI results or permissions.
Call an appropriate tool for repository actions. Changes are PROPOSALS and need explicit mobile confirmation.
If repo unspecified and only one is allowed, use it. Otherwise ask which repository.
Never output API tokens, developer secrets, or raw shell commands.''' }]
    for item in history[-12:]:
        if item.get('role') in ('user','assistant') and isinstance(item.get('content'),str):
            messages.append({'role':item['role'],'content':item['content'][:2500]})
    messages.append({'role':'user','content':message[:5000]})
    response = await asyncio.to_thread(client.chat.completions.create,
        model=config.QWEN_MODEL,messages=messages,tools=TOOLS,tool_choice='auto')
    msg = response.choices[0].message
    if not msg.tool_calls:
        return {'reply':msg.content or 'Не удалось определить действие.', 'actions':[]}
    actions = []
    for call in msg.tool_calls[:3]:
        name = call.function.name
        try:
            args = json.loads(call.function.arguments)
            repo = ensure_repo(args['repo'])
            if name == 'repo_info':
                value = await gh.repo_info(repo)
                actions.append({'type':'read','result':value})
            elif name == 'list_prs':
                value = await gh.pull_requests(repo)
                actions.append({'type':'read','result':value})
            elif name == 'search_repo':
                value = rag.search_repo(repo, args['query'])
                actions.append({'type':'read','result':value})
            elif name in KINDS:
                record = store.create_task(repo, KINDS[name], args)
                actions.append({'type':'confirmation_required', 'task_id':record['id'],
                                'kind':record['kind'],'repo':repo,'details':args})
            else:
                actions.append({'type':'error','message':'Unknown tool'})
        except Exception as exc:
            actions.append({'type':'error','message':f'{type(exc).__name__}: {str(exc)[:200]}'})
    return {'reply':'Вот результат запроса. Для изменений подтвердите действие ниже.', 'actions':actions}
