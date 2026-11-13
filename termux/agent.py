#!/data/data/com.termux/files/usr/bin/python
"""On-demand Qwen Code runner for Android's Termux RUN_COMMAND.

Input: exactly one JSON object via stdin. Output: one JSON object on stdout.
Secrets are never embedded in command-line arguments or repository remotes.
No HTTP server, long-running listener or background scheduler is started.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import uuid

ROOT = Path.home() / ".local" / "share" / "qwen-github-mobile"
REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
ID_RE = re.compile(r"^[0-9a-f]{12}$")
MAX_INPUT = 120_000


def safe_repo(value: object) -> str:
    if not isinstance(value, str) or not REPO_RE.fullmatch(value):
        raise ValueError("Укажи репозиторий в формате owner/repo.")
    owner, name = value.split("/")
    if owner in (".", "..") or name in (".", ".."):
        raise ValueError("Некорректное имя репозитория")
    return value


def validate_id(value: object) -> str:
    if not isinstance(value, str) or not ID_RE.fullmatch(value):
        raise ValueError("Некорректный идентификатор задачи")
    return value


def redact(value: str, *keys: str) -> str:
    for key in keys:
        if key and len(key) >= 5:
            value = value.replace(key, "[скрыто]")
    return value


def git_env(token: str) -> tuple[dict[str, str], Path]:
    env = dict(os.environ)
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GITHUB_AGENT_TOKEN"] = token
    directory = ROOT / "private"
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, path = tempfile.mkstemp(prefix="git-askpass-", dir=directory)
    script = '#!/data/data/com.termux/files/usr/bin/sh\ncase "$1" in *Username*) printf x-access-token ;; *) printf %s "$GITHUB_AGENT_TOKEN" ;; esac\n'
    with os.fdopen(fd, "w", encoding="utf-8") as out:
        out.write(script)
    os.chmod(path, 0o700)
    env["GIT_ASKPASS"] = path
    return env, Path(path)


def git(args: list[str], cwd: Path | None, env: dict[str, str], timeout: int = 150) -> str:
    cp = subprocess.run(["git", *args], cwd=cwd, env=env, text=True,
                        capture_output=True, timeout=timeout, check=False)
    if cp.returncode:
        raise RuntimeError("Git: " + (cp.stderr.strip() or "операция не выполнена")[:450])
    return cp.stdout.strip()


def is_safe_file(path: str) -> bool:
    if not path or path.startswith(("/", "\\")) or ".." in Path(path).parts or "\\" in path:
        return False
    forbidden = {".env", ".npmrc", "id_rsa", "id_ed25519", "google-services.json"}
    for part in path.lower().split("/"):
        if (part in forbidden or part.startswith(".env.") or
            "secret" in part or "credential" in part or "service-account" in part or
            part.endswith((".pem", ".key", ".p12", ".pfx"))):
            return False
    return not path.startswith(".github/workflows/")


def prepare_workspace(repo: str, token: str, job_id: str, base: str | None = None) -> Path:
    directory = ROOT / "jobs" / job_id / "repository"
    if directory.exists():
        return directory
    directory.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    env, askpass = git_env(token)
    try:
        git(["clone", "--depth", "1", "https://github.com/" + repo + ".git", str(directory)], None, env)
    finally:
        askpass.unlink(missing_ok=True)
    return directory


def subprocess_qwen(path: Path, prompt: str, key: str, base_url: str, model: str,
                    mode: str, job_id: str, provider: str) -> str:
    if not shutil.which("qwen"):
        raise RuntimeError("Qwen Code не установлен в Termux. Запусти npm install -g @qwen-code/qwen-code")
    env = dict(os.environ)
    # Never give the coding agent a GitHub write token or the GIT_ASKPASS secret.
    for field in ("GITHUB_TOKEN", "GH_TOKEN", "GITHUB_AGENT_TOKEN", "GIT_ASKPASS"):
        env.pop(field, None)
    env.update(OPENAI_API_KEY=key, OPENAI_BASE_URL=base_url, OPENAI_MODEL=model,
               QWEN_MODEL=model, CI="1", NO_COLOR="1")
    if provider == "qwencloud":
        env["QWENCLOUD_API_KEY"] = key
    args = ["qwen", "-p", prompt, "--output-format", "text", "--safe-mode",
            "--approval-mode", "auto-edit" if mode == "edit" else "default"]
    pid_file = ROOT / "pids" / (job_id + ".pid")
    pid_file.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    process = subprocess.Popen(args, cwd=path, env=env, text=True,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               start_new_session=True)
    pid_file.write_text(str(process.pid), encoding="ascii")
    try:
        try:
            stdout, stderr = process.communicate(timeout=900)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGTERM)
            process.communicate(timeout=10)
            raise RuntimeError("Время работы агента истекло (15 минут).")
        if process.returncode:
            diagnostic = redact(stderr[-750:], key)
            raise RuntimeError("Qwen Code завершился с ошибкой: " + diagnostic)
        return redact(stdout[-60000:].strip(), key)
    finally:
        pid_file.unlink(missing_ok=True)


def changed_files(path: Path, env: dict[str, str]) -> list[str]:
    raw = git(["status", "--porcelain", "--untracked-files=all"], path, env)
    if not raw:
        return []
    files = [line[3:] for line in raw.splitlines()]
    if any(" -> " in item or not is_safe_file(item) for item in files):
        raise RuntimeError("Изменён закрытый или небезопасный файл. Публикация заблокирована.")
    return files


def run_task(data: dict) -> dict:
    repo = safe_repo(data.get("repo"))
    job_id = validate_id(data.get("job_id"))
    token = str(data.get("github_token") or "").strip()
    key = str(data.get("ai_key") or "").strip()
    prompt = str(data.get("prompt") or "").strip()
    mode = data.get("mode", "chat")
    if not token or not key or not prompt:
        raise ValueError("Сохрани оба токена и напиши сообщение")
    if len(prompt) > 5000 or mode not in ("chat", "edit"):
        raise ValueError("Некорректная задача")
    provider = data.get("provider", "qwencloud")
    base_url = str(data.get("base_url") or "").strip()
    model = str(data.get("model") or "").strip()
    if provider not in ("qwencloud", "openrouter", "custom"):
        raise ValueError("Неизвестный AI-провайдер")
    if not base_url.startswith("https://") or len(base_url) > 250 or not model or len(model) > 120:
        raise ValueError("Укажи HTTPS API URL и название модели")
    path = prepare_workspace(repo, token, job_id)
    env = dict(os.environ)
    base = git(["symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD"], path, env).split("/")[-1]
    branch = "qwen/task-" + job_id
    if mode == "edit":
        git(["switch", "-c", branch], path, env)
        instructions = ("Implement the requested change in this checked-out repository. "
                        "Read relevant source and make focused code edits. Do NOT read credentials or execute shell commands. "
                        "Do not push, merge, open PRs, or edit .github/workflows, .env or secrets. "
                        "Do not print secrets. Reply in Russian with a brief summary of changes.\n\nTask: " + prompt)
    else:
        instructions = ("Respond in Russian based on the repository files. Do not edit files, run shell "
                        "commands, access secrets, or take actions on GitHub.\n\nQuestion: " + prompt)
    answer = subprocess_qwen(path, instructions, key, base_url, model, mode, job_id, provider)
    files = changed_files(path, env)
    if mode == "chat":
        if files:
            raise RuntimeError("Qwen Code изменил файлы в режиме чтения; результат отклонён.")
        return {"message": answer or "Ответ пуст.", "prepared": False}
    if not files:
        return {"message": answer or "Изменений в коде нет.", "prepared": False}
    git(["diff", "--check"], path, env)
    git(["add", "--all"], path, env)
    git(["-c", "user.name=Qwen Android Agent", "-c",
         "user.email=qwen-agent@users.noreply.github.com", "commit", "-m", "AI: " + prompt[:65]], path, env)
    info = {"job_id": job_id, "repo": repo, "branch": branch, "base": base,
            "title": "AI: " + prompt[:160], "description": ("## Задача\n" + prompt + "\n\n## Результат Qwen\n" + answer)[:3200]}
    (path.parent / "prepared.json").write_text(json.dumps(info, ensure_ascii=False), encoding="utf-8")
    return {"message": answer or "Изменения подготовлены.", "prepared": True,
            "files": files, "branch": branch, "base": base, "job_id": job_id}


def push_task(data: dict) -> dict:
    job_id = validate_id(data.get("job_id"))
    token = str(data.get("github_token") or "").strip()
    if not token:
        raise ValueError("Не сохранён GitHub token")
    folder = ROOT / "jobs" / job_id
    info_file = folder / "prepared.json"
    if not info_file.is_file():
        raise ValueError("Подготовленная ветка не найдена")
    info = json.loads(info_file.read_text(encoding="utf-8"))
    if info["repo"] != safe_repo(data.get("repo")):
        raise ValueError("Репозиторий не совпадает")
    env, askpass = git_env(token)
    try:
        git(["push", "--set-upstream", "origin", info["branch"]], folder / "repository", env)
    finally:
        askpass.unlink(missing_ok=True)
    return {"message": "Ветка отправлена на GitHub. Проверь изменения и создай PR.",
            "prepared": True, "pushed": True, **info}


def cancel_task(data: dict) -> dict:
    job_id = validate_id(data.get("job_id"))
    file = ROOT / "pids" / (job_id + ".pid")
    if file.exists():
        pid = int(file.read_text(encoding="ascii"))
        try:
            os.killpg(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    return {"message": "Задание остановлено."}


def main() -> None:
    try:
        raw = sys.stdin.read(MAX_INPUT + 1)
        if len(raw) > MAX_INPUT:
            raise ValueError("Слишком большой запрос")
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("Ожидается JSON-объект")
        action = data.get("action", "task")
        if action == "cancel":
            result = cancel_task(data)
        elif action == "push":
            result = push_task(data)
        elif action == "task":
            result = run_task(data)
        else:
            raise ValueError("Неизвестное действие")
        print(json.dumps({"ok": True, **result}, ensure_ascii=False))
    except Exception as exc:
        # Never print input, traceback, environment variables, tokens or raw model output.
        print(json.dumps({"ok": False, "message": str(exc)[:900]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
