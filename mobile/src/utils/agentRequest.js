const EDIT = /^(исправь|поправь|измени|добавь|удали|реализуй|внеси|сделай\s+(изменения|функцию|фикс|правки)|напиши\s+(код|функцию)|refactor|fix\b|implement\b|edit\b)/i;
const REPO = /^[\w.-]+\/[\w.-]+$/;

export function isEditRequest(message) {
  return EDIT.test((message || '').trim());
}

export function assertSettings(settings) {
  if (!REPO.test((settings.repo || '').trim())) throw new Error('Укажи репозиторий owner/repo');
  if (!(settings.githubToken || '').trim()) throw new Error('Добавь GitHub token в настройках');
  if (!(settings.aiKey || '').trim()) throw new Error('Добавь AI API key в настройках');
  if (!/^https:\/\//.test(settings.baseUrl || '')) throw new Error('API должен использовать HTTPS');
  if (!(settings.model || '').trim()) throw new Error('Укажи модель AI');
}

export function newJobId() {
  // Job ids separate concurrent workspaces; they are not security tokens.
  return Array.from({length: 12}, () => Math.floor(Math.random() * 16).toString(16)).join('');
}

export function parseAgentResponse(raw) {
  try {
    const result = JSON.parse(raw);
    if (!result || typeof result !== 'object' || typeof result.message !== 'string') {
      throw new Error('missing message');
    }
    if (!result.ok) throw new Error(result.message);
    return result;
  } catch (error) {
    if (error instanceof SyntaxError) throw new Error('Termux вернул некорректный результат. Проверь установку agent.py');
    throw error;
  }
}

export const PROVIDERS = {
  qwencloud: {name: 'QwenCloud', baseUrl: 'https://maas.qwencloudapi.com/compatible-mode/v1', model: 'qwen3.8-max'},
  openrouter: {name: 'OpenRouter', baseUrl: 'https://openrouter.ai/api/v1', model: 'qwen/qwen3-coder:free'},
  custom: {name: 'Другой OpenAI-совместимый', baseUrl: 'https://', model: ''},
};
