# Qwen GitHub Mobile — Android + Termux (v0.2)

**No Render, VPS or FastAPI server is required for the Android client.** The phone runs the Qwen Code CLI inside Termux on demand. The installed Android app shows a chat and a settings panel for **two credentials**: a GitHub fine-grained token and the API key of a chosen AI model provider. The agent returns its final response into the chat. Termux is launched with `RUN_COMMAND_BACKGROUND=true` (no terminal window).

> The model can be remote (QwenCloud, OpenRouter, etc.). **No remote app server** is used, but AI APIs can have usage limits or charges. OpenRouter free-tier availability depends on the model/provider. A successful APK build is not proof of an end-to-end run on your device.

## Features

- **Main screen:** conversation only, with a small settings button; no backend URL or APP_API_TOKEN.
- **Settings:** `GitHub PAT`, `AI API key`, provider, OpenAI-compatible HTTPS endpoint, model ID and selected repository. App settings including tokens use Android-backed Expo SecureStore; they are never committed to GitHub.
- **Chat:** the native `TermuxBridge` calls Termux's documented `RUN_COMMAND` intent, passing one JSON request on stdin and receiving a one-shot result by `PendingIntent`. No localhost HTTP service, port or daemon. Raw shell output is not shown in the UI.
- **Code changes:** confirm a detected edit request → Qwen Code edits in a local clone and creates a local Git commit → confirm **Send branch** → GitHub compare/Create PR panel opens → you explicitly create the PR on GitHub. No automatic merge and no implicit GitHub push.
- **App background:** best-effort cancel when leaving the foreground; Qwen tasks have a 15-minute limit. Force-killing the Android process can bypass lifecycle events. Running a GitHub Actions build is independent of the app and continues after closing it.

## First-time setup on your Android phone

1. Install **Termux** from [F-Droid](https://f-droid.org/en/packages/com.termux/) or the [official GitHub releases](https://github.com/termux/termux-app/releases). Termux `>=0.109` is required for stdin and result callbacks. Launch Termux once and let it initialize.
2. In the Termux terminal run:

   ```bash
   pkg update -y
   pkg install -y git
   git clone https://github.com/smaks190-crypto/qwen-github-mobile.git ~/qwen-github-mobile
   bash ~/qwen-github-mobile/termux/setup.sh
   ```

   The setup script installs Python, Git, Node.js and `@qwen-code/qwen-code`, copies the agent runner into `~/.local/bin/`, and enables `allow-external-apps=true` in `~/.termux/termux.properties`. You can inspect the setup script before running it. This is a one-time setup, **not a background service**.
3. Open **Android Settings → Apps → Qwen GitHub Agent → Permissions → Additional permissions**, enable **Run commands in Termux environment**. This special permission is mandatory; the APK does not bypass it. Some Android builds show this permission under a slightly different heading.
4. Install the APK from the [Android APK workflow](https://github.com/smaks190-crypto/qwen-github-mobile/actions/workflows/android-apk.yml) on GitHub. Select the latest **successful** run, then download its `qwen-github-mobile-apk-*` artifact ZIP and install `app-release.apk`.
5. On first launch, tap **Settings**, fill in **GitHub token** and **AI API key**, select provider, model and repository, then **Save**. Do not paste these tokens into chat messages.

The GitHub token should be a **fine-grained PAT** scoped to only repositories you want Qwen to work on, with **Contents: read and write** and **Pull requests: read and write** (optional: Issues read/write). To create it: https://github.com/settings/personal-access-tokens/new . QwenCloud API keys: https://home.qwencloud.com/api-keys . QwenCloud and other providers can charge per API usage. The app does not silently select a paid model.

## How to use

- `Покажи, как устроен этот проект` — read-only mode.
- `Исправь ошибку в обработке событий` — the app asks to approve edits before Qwen starts. The clone stays on the phone. The Qwen subprocess never receives the GitHub token; only the Git host wrapper can push.
- After Qwen reports prepared changes, tap **Отправить ветку и создать PR**. Confirm GitHub push, then review title, branches and description in the PR panel. GitHub itself performs the final PR creation.

**Runtime and security:** Android invokes an explicit `com.termux.app.RunCommandService`, specifying a fixed installed Python runner path (no arbitrary shell commands from the UI). Arguments do not contain credentials. The request body goes in Termux's stdin intent extra; Termux necessarily receives both tokens to execute work. On-device app/Termux security and the provider's policy still matter. Agent execution uses `--safe-mode --approval-mode auto-edit`; the Python wrapper rejects changed secret files and GitHub workflow files before committing. Test with a disposable repository before allowing write access to important ones.

## Development and CI

The root still contains the **legacy `backend/` and `worker/` prototype** as reference; neither is invoked by the Android client. Android builds on every push/merge to `main` via `.github/workflows/android-apk.yml`. Other checks include Python syntax/unit tests and Node tests.

```bash
python -m unittest discover -s termux -p 'test_*.py' -v
python -m py_compile termux/agent.py
cd mobile && node --test src/utils/*.test.mjs
```

The Android bridge is a local Expo Module at `mobile/modules/termux-bridge`. Its Kotlin service returns Termux's one-shot callback back to the JS promise. This requires a **native APK**; Expo Go does not have this module.

## Limitations

- Requires official Termux to be installed and configured separately. **Native integration has not yet been validated on a physical phone**; problems may appear with specific Android/Termux versions and need logs/diagnostics.
- Qwen Code must install and run on Termux's Node environment. Some Node/native dependencies may not support all Android variants.
- One task at a time. No long-running daemon, FCM push notifications, or background monitoring.
- Currently the app's command classifier recognizes common edit imperative verbs; ambiguous commands default to read-only. In edit mode, the human must approve changes and later approve a push.
- GitHub Actions builds the APK in the cloud, independently of where the Qwen agent runs.

Sources: [Termux RUN_COMMAND Intent](https://github.com/termux/termux-app/wiki/RUN_COMMAND-Intent), [Qwen Code headless](https://qwenlm.github.io/qwen-code-docs/en/users/features/headless/), [Qwen provider setup](https://qwenlm.github.io/qwen-code-docs/en/users/configuration/auth/), [Expo local modules](https://docs.expo.dev/modules/get-started/).
