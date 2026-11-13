# Qwen GitHub Mobile — prototype 0.1.0

A mobile chat for GitHub with **the actual Qwen Code agent** (not regex-parsed code blocks).

## What is implemented
- Expo SDK 58 Android React Native UI: chat, repository selection, action previews, explicit confirmation, task status.
- FastAPI backend with a single-user bearer token (store it in Android SecureStore), repo allowlist, server-only GitHub & Qwen keys.
- Qwen API tool-routing for chat. Read-only: repository info, PR list, local full-text repository retrieval. Changes: create issue, review PR, draft code PR, index repository. **All operations that create a task require confirmation.**
- Real Qwen Code CLI in a Docker worker to read/modify cloned repositories. The worker never receives the GitHub token; host performs git operations.
- Webhook HMAC signature verification, delivery idempotency, CI/PR/issue/push notification routing to only the registered devices subscribed to that repository.
- SQLite task records and SQLite FTS5 chunk-based RAG; no heavy model installation for embeddings.
- GitHub draft PR, no automatic merge. CI results come later via GitHub Actions webhook.

## Important limitations
- **Prototype, not production-ready.** Single-server process, single-owner shared access secret, SQLite in-process task queue; no proper OAuth/GitHub App, multi-tenant tenancy or scalable workers. For deployment beyond your own use, replace with GitHub App and user OAuth, proper durable queue, Docker isolation hardening + egress controls, security audit, rate limits and retention controls.
- Draft PR creation is guarded by a confirmation, but the server is allowed to push a branch **after that confirmation**. Never run it against repositories you do not control.
- Qwen Code uses `--safe-mode --approval-mode auto-edit`, not dangerous YOLO. It may refuse operations it cannot do without an approved shell command. CI is **not** run synchronously in the worker; it must be verified in GitHub Actions.
- The review task posts a general issue comment, not line-level GitHub Reviews. It is AI analysis, not a guarantee that all bugs are found.
- RAG is local FTS5 lexical retrieval, not vector semantic embeddings. Index needs to be updated manually after repository changes.
- Android native FCM requires a Firebase project, `google-services.json`, a build with native code (development build / APK), and backend service-account credentials. **Expo Go alone is not sufficient.** iOS APNs delivery not implemented.
- No actual Qwen API or GitHub credentials were used to run end-to-end integration tests here.

## Setup: backend

Prerequisites: Python 3.11+, Git, Docker Engine, a non-root Docker runtime account, a GitHub token scoped to your repositories, and valid QwenCloud credentials.

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env: APP_API_TOKEN, GITHUB_TOKEN, ALLOWED_REPOS,
# GITHUB_WEBHOOK_SECRET, QWENCLOUD_API_KEY, MODEL/URL.
cd ..
docker build -t qwen-github-worker:local worker
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

For testing locally with HTTPS use a reverse proxy or temporary trusted HTTPS tunnel. Do not expose FastAPI directly to the public internet without proper TLS/auth/rate-limits. `APP_API_TOKEN` is a separate application access secret; it is **not** your GitHub token.

Test access:
```bash
curl -H "Authorization: Bearer YOUR_APP_API_TOKEN" https://YOUR_DOMAIN/repos
```

Webhooks: repository > Settings > Webhooks > Add; URL `https://YOUR_DOMAIN/webhook/github`, content type `application/json`, secret `GITHUB_WEBHOOK_SECRET`; events `issues`, `pull_request`, `push`, `check_run`, `check_suite`, `workflow_run` as needed. Webhook endpoint is public but HMAC-verified.

## Setup: Android

Prerequisites: Node.js 22.13+, Android build environment or EAS build.

```bash
cd mobile
npm install
npx expo install --fix
npx expo-doctor
```

Create a Firebase Android app with package name `com.example.qwengithubagent`, download its **client** file `google-services.json` into `mobile/`. Configure backend `FIREBASE_CREDENTIALS_PATH` to the server's **private** Firebase service-account JSON (never add that private file to version control or APK). Then build a native development APK:

```bash
npx expo run:android
# Or: use EAS development build with your own Expo project/credentials.
```

On first launch supply your **HTTPS backend URL** and **APP_API_TOKEN**. The UI stores the access secret using Expo SecureStore. Then select an allowlisted repo and chat: `Покажи открытые PR`, `Проверь PR #8`, `Добавь обработку ошибок и создай PR`, `Индексируй репозиторий`.

## Tests and validation

```bash
cd backend
python -m pytest -q
python -m compileall -q app
```

To run end-to-end tests, configure a disposable private GitHub repository, valid Qwen API key, an installed Docker daemon and Firebase test app. Confirm an issue, a review, a code task, and verify their effects on GitHub; check the Android build and webhook delivery history separately.

## Suggested production improvements
1. Replace single-owner APP_API_TOKEN with GitHub user OAuth PKCE and GitHub App installation tokens (short-lived and per repository).
2. Move queue to Redis/RQ or PostgreSQL durable workers, with cancellable jobs, worker concurrency limits and audit logs.
3. Limit egress from Qwen sandbox to the model endpoint and enforce prompt-injection/secret-scanning policies; require explicit human approval for sensitive changes.
4. Stream task logs via SSE/WebSocket, implement line-level reviews, apply CI workflow profiles, and add branch protection and manual merge.
5. Introduce SHA-aware incremental embedding RAG if necessary.

## Source references
- Qwen Code repo: https://github.com/QwenLM/qwen-code
- Qwen Code headless: https://github.com/QwenLM/qwen-code/blob/main/docs/users/features/headless.md
- Qwen authentication: https://github.com/QwenLM/qwen-code/blob/main/docs/users/configuration/auth.md
- Expo native notifications: https://docs.expo.dev/push-notifications/sending-notifications-custom/
- GitHub webhook security: https://docs.github.com/en/webhooks/using-webhooks/validating-webhook-deliveries


## Automatic Android APK on changes to main

GitHub Actions workflow [Android APK](https://github.com/smaks190-crypto/qwen-github-mobile/actions/workflows/android-apk.yml) runs on **every push to `main`**, including merged PRs. It can also be started manually via **Run workflow**.

The workflow generates the Android native project from Expo SDK 58, builds a **standalone release-variant test APK**, verifies its Android signature and uploads `app-release.apk` as a 30-day GitHub Actions artifact. Open the completed workflow run, scroll to **Artifacts**, download `qwen-github-mobile-apk-<run number>`, unzip it and install the APK. This workflow does not require Render, Expo EAS credentials or a continuously running server.

Optional Firebase notifications: add repository Actions secret `ANDROID_GOOGLE_SERVICES_JSON_B64` with the base64 encoding of the Android **client** `google-services.json`. If the secret is absent, the APK build runs without Firebase Cloud Messaging configuration; push notifications will not be available. Never put a Firebase **service-account private key** in the app or repository.

The APK is a **test build** that uses the Android project's default debug signing and is not a production-signed store release. The current mobile chat still expects a FastAPI backend; migration to a phone-local Termux/Qwen agent is not yet implemented. A successful Android build alone does not mean those features work without a server.
