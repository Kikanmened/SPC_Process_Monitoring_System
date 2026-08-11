# Runbook — bring up the local stack

## When

A reviewer or engineer needs a working API + dashboard + scheduler with no
cloud dependencies.

## Steps

```bash
git clone <repo> && cd SPC_Process_Monitoring_System
make install          # uv sync --frozen --all-groups
make stack            # docker compose up --build -d
curl -s http://localhost:8000/health
curl -s http://localhost:8000/ready
open http://localhost:8501
```

Without Docker, the lighter path remains:

```bash
make demo             # Streamlit only, in-process fakes
```

## Verify

| Check | Expect |
|---|---|
| `GET /health` | `{"status":"ok"}` |
| `GET /ready` | `status` is `ready` |
| Dashboard | Line overview loads |
| `GET /metrics` | Prometheus text (may be empty until jobs run) |

## Failure modes

| Symptom | Action |
|---|---|
| Port 8000/8501 busy | Stop the other process or change Compose ports |
| Image build fails on WeasyPrint libs | Rebuild; runtime stage installs pango/cairo |
| `/ready` not ready | Inspect API logs; confirm composition root started |
