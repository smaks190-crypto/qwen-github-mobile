/** A GitHub compare URL opens the official PR creation form, without a backend token. */
const REPO = /^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/;
const BRANCH = /^(?!\/)(?!.*\.\.)(?!.*\/$)(?!.*\/\/)[A-Za-z0-9._/-]+$/;

export function makePullRequestUrl({ repo, base, head, title, body }) {
  const repository = (repo || '').trim();
  const target = (base || '').trim();
  const source = (head || '').trim();
  const heading = (title || '').trim();
  if (!REPO.test(repository)) throw new Error('Выбери репозиторий в формате owner/repo');
  if (!BRANCH.test(target) || !BRANCH.test(source)) throw new Error('Укажи корректные названия веток');
  if (target === source) throw new Error('Ветки должны различаться');
  if (!heading) throw new Error('Укажи название PR');
  if (heading.length > 240) throw new Error('Слишком длинное название PR');
  if ((body || '').length > 3500) throw new Error('Описание слишком длинное для ссылки. Сократи его.');
  const compare = `${encodeURIComponent(target)}...${encodeURIComponent(source)}`;
  return `https://github.com/${repository}/compare/${compare}?quick_pull=1&title=${encodeURIComponent(heading)}&body=${encodeURIComponent(body || '')}`;
}

/** Only Qwen's completed and pushed code branch is eligible for an automatic panel. */
export function readPreparedPullRequest(task) {
  if (!task || task.kind !== 'code' || task.status !== 'completed') return null;
  try {
    const value = typeof task.result === 'string' ? JSON.parse(task.result) : task.result;
    if (value?.type !== 'pr_ready' || value.repo !== task.repo || !value.head || !value.base) return null;
    return {
      id: task.id,
      repo: value.repo,
      head: value.head,
      base: value.base,
      title: value.title || '',
      body: value.body || '',
    };
  } catch (_) {
    return null;
  }
}
