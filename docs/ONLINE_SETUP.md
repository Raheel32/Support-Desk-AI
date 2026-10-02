# Run Support Desk AI fully online

Deploy the database first, the backend second, and the dashboard last. Once deployed, the project runs in those cloud services and does not require the computer at `D:\Support Desk AI` to stay on.

The package is ready for deployment; it does not create accounts, provision services, or include personal API keys. Start in rules mode. Enable optional Gemini explanations after the base workflow works.

## 1 Put the complete package in GitHub

Use the existing repository: https://github.com/Raheel32/Support-Desk-AI

Choose one way to upload the package.

### Existing Windows folder

1. Download and extract `Support-Desk-AI.zip` into a temporary folder.
2. Open the extracted `Support-Desk-AI` folder.
3. Copy its contents into `D:\Support Desk AI`, replacing the earlier starter files. Keep the existing `.git` and `.venv` folders. The ZIP contains neither of them.
4. Include the `.github`, `.devcontainer`, and `.streamlit` configuration folders from the archive.
5. Open PowerShell in `D:\Support Desk AI` and run:

```powershell
git status
git add backend frontend tests docs .github .devcontainer .streamlit/config.toml .streamlit/secrets.toml.example .env.example .gitignore main.py requirements.txt requirements-dev.txt render.yaml README.md
git diff --cached --stat
git commit -m "online Support Desk AI demo"
git push origin main
```

Stop if Git reports a conflict or rejected push. Fetch and integrate the remote changes without force-pushing.

### Browser only with GitHub Codespaces

1. Open the repository on GitHub. Choose **Code → Codespaces → Create codespace on main**.
2. In the browser editor, upload `Support-Desk-AI.zip` into the repository root through the Explorer's upload action or drag and drop.
3. In its terminal, run:

```bash
unzip -o Support-Desk-AI.zip -d /tmp/support-desk-package
cp -a /tmp/support-desk-package/Support-Desk-AI/. .
git status
git add backend frontend tests docs .github .devcontainer .streamlit/config.toml .streamlit/secrets.toml.example .env.example .gitignore main.py requirements.txt requirements-dev.txt render.yaml README.md
git diff --cached --stat
git commit -m "Add complete online Support Desk AI demo"
git push origin main
```

The ZIP itself is not selected by these commands. The supplied dev-container config can be applied using **Codespaces: Rebuild Container**, or install packages in the current container with `python -m pip install -r requirements-dev.txt`.

Codespaces is a development environment. Its stopped state does not keep an app available as a permanent public service. Use the hosting steps below for that.

## 2 Create the PostgreSQL database in Neon

1. Open https://neon.com and create or sign in to your account.
2. Create a project named `support-desk-ai` and a database for this demo.
3. Open **Connect** and copy the PostgreSQL connection string. Prefer the direct connection for this small demo and LangGraph checkpoint setup; disable connection pooling in the connection-string selector if it is enabled.
4. Keep the `sslmode=require` parameter and any other provider-required connection settings.
5. Store this value privately for the next step. It includes a database password.

The connection string has this structure; do not use these placeholder values:

```text
postgresql://USERNAME:PASSWORD@HOST/DATABASE?sslmode=require
```

No SQL needs to be pasted manually. On first startup, the backend creates its tables, checkpoint tables, and sample records. Use a dedicated demo database because the app creates and updates its own tables. The same database stores workflow checkpoints by default. A separate `CHECKPOINT_DATABASE_URL` is optional.

## 3 Host FastAPI on Render

1. Open https://render.com and sign in.
2. Connect the GitHub repository through Render's account flow.
3. Choose **New → Blueprint**, select `Raheel32/Support-Desk-AI`, and use `render.yaml` from `main`.
4. Review the selected plan and any charges shown by Render.
5. Set the prompted `DATABASE_URL` to the Neon connection string.
6. Deploy the blueprint. It generates a random `BACKEND_API_KEY` automatically.
7. Open the service's environment settings and privately copy that generated key for Streamlit. Do not post it in GitHub or chat.
8. Copy the public backend URL from Render, for example `https://YOUR-SERVICE.onrender.com`.
9. Open that URL followed by `/health`. Expect a JSON object containing `"status": "ok"` and `"simulation": true`.

If the Blueprint option is unavailable, create a Python **Web Service** with these settings:

| Setting | Value |
| --- | --- |
| Branch | `main` |
| Root directory | Leave blank |
| Build command | `pip install -r requirements.txt` |
| Start command | `uvicorn backend.main:app --host 0.0.0.0 --port $PORT --workers 1` |
| Health check path | `/health` |
| Python version | `3.12.14` |

Add these environment variables manually:

| Name | Value |
| --- | --- |
| `APP_ENV` | `production` |
| `DATABASE_URL` | Your Neon PostgreSQL connection string |
| `BACKEND_API_KEY` | A unique random secret of at least 32 characters |
| `AI_MODE` | `rules` |
| `SEED_DEMO` | `true` |
| `PYTHON_VERSION` | `3.12.14` |

You can generate a key in your own Codespaces terminal using `python -c "import secrets; print(secrets.token_urlsafe(32))"`. Copy it directly into the hosting settings. Do not save it in tracked files.

Use one worker for this educational app. Investigations are synchronous and serialized for predictable behavior. The PostgreSQL advisory lock also protects mutations across briefly overlapping processes during a redeploy.

## 4 Host the Streamlit dashboard

1. Open https://share.streamlit.io and sign in with GitHub.
2. Create a new app from `Raheel32/Support-Desk-AI`.
3. Select branch `main`.
4. Set the main file path to `frontend/streamlit_app.py`.
5. In advanced settings, select Python **3.12** and add the secrets below.
6. Replace every placeholder with the actual value, preserving the quotation marks.
7. Deploy and open the dashboard URL provided by Streamlit.

```toml
API_BASE_URL = "https://YOUR-BACKEND.onrender.com"
BACKEND_API_KEY = "THE-SAME-KEY-AS-RENDER"
APP_PASSWORD = "A-SEPARATE-STRONG-WORKSPACE-PASSWORD"
```

Use `APP_PASSWORD` to sign in to the dashboard. It is different from your GitHub, Render, and Neon passwords. `BACKEND_API_KEY` is a server-to-server secret; it is not the login password.

The frontend's `requirements.txt` lives beside `streamlit_app.py`, so Community Cloud installs the dashboard dependencies. Streamlit secrets remain in the hosting settings; do not create a committed secrets file.

No browser CORS configuration is needed for this design: Streamlit's Python server calls FastAPI directly.

## 5 Verify the online workflow

1. Open **Ticket workspace** and select **TKT-1001**.
2. Click **Investigate ticket**. Expect **Awaiting Approval** with a PKR 2,500.00 proposal.
3. Refresh the browser. The investigation should still be there.
4. For a persistence check, restart the Render service while the proposal is pending, then reopen the ticket. It should still await approval.
5. Review evidence, enter a reviewer name, confirm review, and approve.
6. Expect **Resolved** and a simulated refund reference. The activity history records approval and execution.
7. Check **TKT-1003**. It should require manual review because a refund already exists.
8. Check and approve **TKT-1006**. It should report an intentional simulated gateway failure and remain unresolved.

## 6 Enable Gemini explanations optionally

1. Open https://aistudio.google.com and obtain a Gemini API key in your account.
2. Check model availability and any quota or billing requirements in that account.
3. In Render, add `GEMINI_API_KEY` and set `GEMINI_MODEL` to a model available to your account that supports `generateContent`.
4. Set `AI_MODE=gemini` and redeploy/restart.
5. Start a new investigation. Existing completed investigations keep their saved explanation.

The model ID is intentionally configurable. Consult the official model list rather than relying on a hardcoded default. Only fictional ticket and transaction evidence is sent to Gemini. If the provider fails, the app displays the deterministic policy finding and labels the fallback. The provider integration is tested with mocked responses; a live call requires your own credentials.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Backend fails to start | Neon URL, SSL parameters, database connectivity, and Render startup logs |
| Error about API key | Use a unique key of at least 32 characters in production |
| Dashboard says setup is incomplete | Add all three Streamlit secrets with the exact names above |
| Dashboard returns 401 | `BACKEND_API_KEY` must match on Render and Streamlit |
| First request is slow | Render's free web service can sleep after idle time; allow it to wake |
| Request timed out after approval | Refresh the ticket first; the backend may have completed the action |
| Investigation is interrupted | Click **Resume saved workflow**; it recovers checkpoint state |
| Gemini fallback warning | Check provider key, model access, quota, and provider availability |
| Ticket is already resolved | Create a new fictional ticket; already-refunded payments cannot be refunded twice |
| Data disappears after redeploy | Ensure production uses Neon PostgreSQL, not local SQLite |

## Hosting limits

Render's documented free web service sleeps after 15 minutes without inbound traffic and may take about a minute to wake. PostgreSQL persistence prevents this sleep from erasing tickets. Neon, Streamlit, Codespaces, and Gemini have separate account limits that may change. Review each provider's dashboard before enabling paid resources. This package promises no permanent free or always-on service.

## Official references

- Streamlit deployment: https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app
- Streamlit secrets: https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management
- FastAPI on Render: https://render.com/docs/deploy-fastapi
- Render free service behavior: https://render.com/docs/free
- Neon connections: https://neon.com/docs/connect/connect-from-any-app
- Codespaces: https://docs.github.com/en/codespaces/developing-in-a-codespace/creating-a-codespace-for-a-repository
- Gemini content generation: https://ai.google.dev/api/generate-content
