# Deployment — Streamlit Community Cloud

WorthApply is deployed on **Streamlit Community Cloud**, not Render or Vercel.

- **Live app:** https://worthapply-hack.streamlit.app/
- **Repo app entry:** `worthapply/app/ui/streamlit_app.py` (or project `main` entry used by the Cloud app)
- **Python:** see `runtime.txt` (`python-3.11.11`)
- **Dependencies:** `requirements.txt`
- **Streamlit config:** `.streamlit/config.toml` (headless server, no usage stats)

## Required secrets / env (Cloud)

Production must **not** depend on Ollama or a laptop GPU.

```
LLM_PROVIDER=xai
XAI_API_KEY=<secret>
XAI_MODEL=<your cloud model>
```

Optional:

```
SERPER_API_KEY=<secret>
BATCH_CONCURRENCY=2
```

Set these in the Streamlit Cloud app **Secrets** UI (equivalent to `.env` locally). Never commit real keys.

## Local vs deploy

| | Development | Streamlit Cloud |
|--|-------------|-----------------|
| LLM | Optional local `worthapply-dev` (Ollama) — **$0**, no API rate-limit pain | Cloud API only |
| Purpose | Iterate / test repeatedly | Real demos & submissions |
| Cost/task | $0 | ~$0.003/report typical sample (~8 LLM calls) |

## Why no Render/Vercel config

Hosting choice is Streamlit Cloud. `runtime.txt` + `requirements.txt` + `.streamlit/config.toml` are the deploy artifacts for this stack. Dockerfile/Procfile are unnecessary for the current deployment.
