# AutoML Research Lab — frontend

React + TypeScript + Vite + Tailwind + Recharts.

The browser talks to the **gateway only** via the Vite proxy (`/api` → `http://127.0.0.1:8000`).

## Stage B1

- Setup screen
- Research Control Center (timeline, score chart, best vs previous, budget, activity log, health strip, mock banner)
- Live agent graph is **planned** (Stage B2)

```bash
# Terminal 1 — gateway / stack
make up

# Terminal 2 — UI
cd frontend && npm install && npm run dev
# open http://127.0.0.1:5173
```
